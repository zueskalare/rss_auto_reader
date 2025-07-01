import os
import logging
import asyncio
import importlib
import threading
import time

import feedparser
import yaml

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models.article import Article, ArticleStatus
import json
import requests
from app.services.summarize import summarize_article
# from app.services.dispatcher import dispatch_summary 
from app.models.feed import Feed
from app.models.user import User

# --- User interest config/support ---
BASE_DIR = os.path.dirname(__file__)
USERS_CONFIG_PATH = os.path.join(BASE_DIR, "config", "users.yml")

def load_users():
    """Loads users from the database"""
    session = SessionLocal()
    try:
        return session.query(User).all()
    finally:
        session.close()


CONFIG_PATH = os.path.join(BASE_DIR, "config", "feeds.yml")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 300))

SUMMARIZE_INTERVAL = int(os.getenv("SUMMARIZE_INTERVAL", POLL_INTERVAL))

# LLM configuration file path for model parameters
LLM_CONFIG_PATH = os.path.join(BASE_DIR, "config", "llm.yml")

def load_config():
    """Loads polling interval and feed list from DB"""
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f) or {}
    interval = cfg.get("interval", POLL_INTERVAL)
    session = SessionLocal()
    try:
        feeds = [{"name": f.name, "url": f.url} for f in session.query(Feed).all()]
    finally:
        session.close()
    return feeds, int(interval)

def load_llm_config() -> dict:
    """Load LLM model parameters from YAML config."""
    try:
        with open(LLM_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}

def save_llm_config(cfg: dict) -> None:
    """Save LLM model parameters to YAML config."""
    with open(LLM_CONFIG_PATH, "w") as f:
        yaml.safe_dump(cfg, f)

def fetch_and_store(session: Session, feed: dict):
    """Fetch articles from a feed and store them in the database."""
    logging.info(f"Fetching articles from feed: {feed['name']} ({feed['url']})")
    parsed = feedparser.parse(feed["url"])
    for entry in parsed.entries:
        entry_id = entry.get("id") or entry.get("link")
        if session.query(Article).filter_by(feed_name=feed["name"], entry_id=entry_id).first():
            continue
        published = None
        if entry.get("published_parsed"):
            published = datetime(*entry.published_parsed[:6])
        article = Article(
            feed_name=feed["name"],
            entry_id=entry_id,
            title=entry.get("title"),
            link=entry.get("link"),
            published=published,
            summary=entry.get("summary"),
            status=ArticleStatus.new,
        )
        session.add(article)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        except Exception as e:
            logging.error(f"Error storing article {entry_id} from feed {feed['name']}: {e}")
            session.rollback()

def summarize_and_push(session: Session):
    logging.info(f"Summarizing new articles and preparing for dispatch")
    new_articles = session.query(Article).filter_by(status=ArticleStatus.new).all()
    users = load_users()
    user_data = [{"username": u.username, "interests": u.interests or []} for u in users]
    offset = 1
    for i in range(0, len(new_articles), offset):
        batch = new_articles[i:i+offset]
        
        for art in batch:
            try:
                inp = (art.title, art.link,
                    art.published.isoformat() if art.published else "",
                    art.summary or "")
                summaries = summarize_article(inp, user_data)
                art.ai_summary = summaries.get("Summary_of_article", '')
                art.recipients = json.dumps(summaries.get("Recommend_recipients", []))
                art.status = ArticleStatus.summarized
                art.sent = False
                session.commit()
    
            except Exception:
                # If summarization fails, leave articles as 'new' so they'll be retried later
                session.rollback()

def dispatch_pending(session: Session):
    logging.info(f"Dispatching articles to users via webhooks")
    unsent = session.query(Article).filter_by(status=ArticleStatus.summarized, sent=False).all()
    for art in unsent:
        recs = json.loads(art.recipients or "[]")
        success = True
        for uname in recs:
            u = session.query(User).filter_by(username=uname).first()
            if u and u.webhook:
                try:
                    # construct content for webhook
                    
                    content = f'# [{art.title}]({art.link})\n # AI Summary\n{art.ai_summary} \n# Abstract\n{art.summary}\n'
                    if len(content.split()) > 1500:
                        content = " ".join(content.split()[:1500]) + "..."
                    # dispatch to user webhook
                    response = requests.post(u.webhook, json={"ai_summary": content}, timeout=30)
                    logging.info(f"Dispatching article {art.link} to {uname} with status {response.status_code}")
                    time.sleep(2)  # Rate limit to avoid hitting webhook too fast
                except Exception:
                    success = False
            else:
                logging.info(f"User {uname} not found or has no webhook configured.")
                logging.warning(f"User {uname} not found or has no webhook configured.")
                success = False
        if success:
            art.sent = True
            art.status = ArticleStatus.sent
            session.commit()
            # dispatch_summary(art, art.ai_summary) # ! not necessary, if you want to use webhook, you can use the above code
            logging.info(f"Dispatched article {art.link} to {recs}")
            logging.info(f"Dispatched article {art.link} to {recs}")
        else:
            # session.rollback()
            art.sent = False
            art.status = ArticleStatus.new
            session.commit()

def _poll_job(feeds):
    jobid = time.asctime()
    logging.info(f"Starting poll job with feeds at {jobid}")
    session = SessionLocal()
    try:
        for f in feeds:
            fetch_and_store(session, f)
    finally:
        session.close()
    logging.info(f"Finished poll job at {jobid}")

def _summarize_job():
    jobid = time.asctime()
    logging.info(f"Starting summarize job at {jobid}")
    session = SessionLocal()
    try:
        summarize_and_push(session)
    finally:
        session.close()
    logging.info(f"Finished summarize job at {jobid}")

def _dispatch_job():
    jobid = time.asctime()
    logging.info(f"Starting dispatch job at {jobid}")
    session = SessionLocal()
    try:
        dispatch_pending(session)
    finally:
        session.close()
    logging.info(f"Finished dispatch job at {jobid}")
    
        
# --- Background tasks ---
async def poll_loop():
    while True:
        feeds, interval = load_config()
        await asyncio.to_thread(_poll_job, feeds)
        await asyncio.sleep(interval)

async def summarize_loop():
    while True:
        await asyncio.to_thread(_summarize_job)
        await asyncio.sleep(SUMMARIZE_INTERVAL)

async def dispatch_loop():
    interval = int(os.getenv("DISPATCH_INTERVAL", 300))
    while True:
        await asyncio.to_thread(_dispatch_job)
        await asyncio.sleep(interval)
        
        

async def _run_interval(plugin, interval: int):
    """Helper loop to run a plugin at a fixed interval (in seconds)."""
    while True:
        try:
            await asyncio.to_thread(plugin.run, SessionLocal())
        except Exception as e:
            logging.error(f"Error in plugin '{plugin.name}' interval run: {e}")
        await asyncio.sleep(interval)

async def _run_daily(plugin, time_str: str):
    """Helper loop to run a plugin once a day at the specified HH:MM local time."""
    hour, minute = map(int, time_str.split(':'))
    while True:
        now = datetime.now()
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
        try:
            await asyncio.to_thread(plugin.run, SessionLocal())
        except Exception as e:
            logging.error(f"Error in plugin '{plugin.name}' daily run: {e}")

async def plugin_loop():
    """Schedule all plugins declared in app.plugins.__all__ according to their schedule."""
    from app.plugins import __all__ as plugin_names

    for name in plugin_names:
        try:
            module = importlib.import_module(f"app.plugins.{name}")
            plugin = getattr(module, "plugin", None)
            if not plugin:
                continue
            ptype = getattr(plugin, "schedule_type", "interval")
            if ptype == "daily":
                time_str = plugin.schedule_time or "00:00"
                asyncio.create_task(_run_daily(plugin, time_str))
            else:
                interval = plugin.schedule_interval or int(os.getenv("PLUGIN_INTERVAL", 86400))
                asyncio.create_task(_run_interval(plugin, interval))
        except Exception as e:
            logging.error(f"Failed to schedule plugin '{name}': {e}")

def _initial_seed() -> None:
    session = SessionLocal()
    try:
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        for fdef in cfg.get("feeds", []):
            if not session.query(Feed).filter_by(name=fdef.get("name")).first():
                session.add(Feed(name=fdef.get("name"), url=fdef.get("url")))
        if os.path.exists(USERS_CONFIG_PATH):
            with open(USERS_CONFIG_PATH) as uf:
                ucfg = yaml.safe_load(uf) or {}
            for udef in ucfg.get("users", []):
                if not session.query(User).filter_by(username=udef.get("username")).first():
                    session.add(
                        User(
                            username=udef.get("username"),
                            webhook=udef.get("webhook"),
                            interests=udef.get("interests", []),
                        )
                    )
        session.commit()
    finally:
        session.close()

def _initial_fetch() -> None:
    session = SessionLocal()
    try:
        feeds, _ = load_config()
        for feed in feeds:
            fetch_and_store(session, feed)
    finally:
        session.close()