import os
import logging
import asyncio
import importlib
import threading

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

def summarize_and_push(session: Session):
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
                art.ai_summary = summaries.get("summaries", '')
                art.recipients = json.dumps(summaries.get("recipients", []))
                art.status = ArticleStatus.summarized
                art.sent = False
                session.commit()
    
            except Exception:
                # If summarization fails, leave articles as 'new' so they'll be retried later
                session.rollback()

def dispatch_pending(session: Session):
    unsent = session.query(Article).filter_by(status=ArticleStatus.summarized, sent=False).all()
    for art in unsent:
        recs = json.loads(art.recipients or "[]")
        success = True
        for uname in recs:
            u = session.query(User).filter_by(username=uname).first()
            if u and u.webhook:
                try:
                    requests.post(u.webhook, json={
                        "id": art.link, "feed_name": art.feed_name,
                        "title": art.title, "link": art.link,
                        "published": art.published.isoformat() if art.published else None,
                        "feed_summary": art.summary, "ai_summary": art.ai_summary,
                        "matched_interests": recs}, timeout=10)
                except Exception:
                    success = False
            else:
                print(f"User {uname} not found or has no webhook configured.")
                logging.warning(f"User {uname} not found or has no webhook configured.")
                success = False
        if success:
            art.sent = True
            art.status = ArticleStatus.sent
            session.commit()
            # dispatch_summary(art, art.ai_summary) # ! not necessary, if you want to use webhook, you can use the above code
            print(f"Dispatched article {art.link} to {recs}")
            logging.info(f"Dispatched article {art.link} to {recs}")
        else:
            session.rollback()

def _poll_job(session, feeds):
    for f in feeds:
        fetch_and_store(session, f)

def _summarize_job(session):
    summarize_and_push(session)

def _dispatch_job(session):
    dispatch_pending(session)
_poll_wake_event = threading.Event()

async def poll_loop():
    def _poll_thread_loop():
        session = SessionLocal()
        while True:
            feeds, interval = load_config()
            _poll_job(session, feeds)
            _poll_wake_event.wait(timeout=interval)
            _poll_wake_event.clear()

    await asyncio.to_thread(_poll_thread_loop)

_summarize_wake_event = threading.Event()

async def summarize_loop():
    def _summarize_thread_loop():
        session = SessionLocal()
        while True:
            _summarize_job(session)
            _summarize_wake_event.wait(timeout=SUMMARIZE_INTERVAL)
            _summarize_wake_event.clear()

    await asyncio.to_thread(_summarize_thread_loop)

_dispatch_wake_event = threading.Event()

async def dispatch_loop():
    def _dispatch_thread_loop():
        session = SessionLocal()
        interval = int(os.getenv("DISPATCH_INTERVAL", 300))
        while True:
            _dispatch_job(session)
            _dispatch_wake_event.wait(timeout=interval)
            _dispatch_wake_event.clear()

    await asyncio.to_thread(_dispatch_thread_loop)

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