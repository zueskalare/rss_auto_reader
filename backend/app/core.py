import os
import logging
import asyncio
import pkgutil
import importlib

import feedparser
import yaml

from datetime import datetime
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.article import Article, ArticleStatus
import json
import requests
from app.services.summarize import summarize_article, summarize_articles
from app.services.dispatcher import dispatch_summary
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

def article_matches_interest(article, interests):
    """Return True if article's title or summary matches any interests"""
    text = f"{article.title or ''} {article.summary or ''}".lower()
    for item in interests:
        if str(item).lower() in text:
            return True
    return False

def dispatch_to_user_webhooks(article, summary):
    users = load_users()
    for user in users:
        interests = user.interests or []
        if interests and article_matches_interest(article, interests):
            webhook = user.webhook
            if webhook:
                payload = {
                    "id": article.id,
                    "feed_name": article.feed_name,
                    "title": article.title,
                    "link": article.link,
                    "published": article.published.isoformat() if article.published else None,
                    "summary": summary,
                    "matched_interests": interests
                }
                try:
                    requests.post(webhook, json=payload, timeout=10)
                except Exception as e:
                    logging.warning(f"User webhook failed for {user.username}: {e}")

CONFIG_PATH = os.path.join(BASE_DIR, "config", "feeds.yml")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 300))
SUMMARIZE_INTERVAL = int(os.getenv("SUMMARIZE_INTERVAL", POLL_INTERVAL))

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

def fetch_and_store(session: Session, feed: dict):
    parsed = feedparser.parse(feed["url"])
    for entry in parsed.entries:
        entry_id = entry.get("id") or entry.get("link")
        if not session.query(Article).filter_by(feed_name=feed["name"], entry_id=entry_id).first():
            published = None
            if entry.get("published_parsed"):
                published = datetime(*entry.published_parsed[:6])
            article = Article(
                feed_name=feed["name"], entry_id=entry_id,
                title=entry.get("title"), link=entry.get("link"),
                published=published, summary=entry.get("summary"),
                status=ArticleStatus.new)
            session.add(article)
    session.commit()

def summarize_and_push(session: Session):
    new_articles = session.query(Article).filter_by(status=ArticleStatus.new).all()
    users = load_users()
    user_data = [{"username": u.username, "interests": u.interests or []} for u in users]
    for i in range(0, len(new_articles), 10):
        batch = new_articles[i:i+10]
        inputs = [(a.title, a.link,
                   a.published.isoformat() if a.published else "",
                   a.summary or "") for a in batch]
        try:
            results = summarize_articles(inputs, user_data)
            for art, res in zip(batch, results):
                art.ai_summary = res.get("summary", "")
                art.recipients = json.dumps(res.get("recipients", []))
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
                        "id": art.id, "feed_name": art.feed_name,
                        "title": art.title, "link": art.link,
                        "published": art.published.isoformat() if art.published else None,
                        "feed_summary": art.summary, "ai_summary": art.ai_summary,
                        "matched_interests": recs}, timeout=10)
                except Exception:
                    success = False
            else:
                success = False
        if success:
            art.sent = True
            art.status = ArticleStatus.sent
            session.commit()
            dispatch_summary(art, art.ai_summary)
        else:
            session.rollback()

def _poll_job(feeds):
    session = SessionLocal()
    try:
        for f in feeds:
            fetch_and_store(session, f)
    finally:
        session.close()

def _summarize_job():
    session = SessionLocal()
    try:
        summarize_and_push(session)
    finally:
        session.close()

def _dispatch_job():
    session = SessionLocal()
    try:
        dispatch_pending(session)
    finally:
        session.close()

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
    interval = int(os.getenv("DISPATCH_INTERVAL", 3600))
    while True:
        await asyncio.to_thread(_dispatch_job)
        await asyncio.sleep(interval)

async def plugin_loop():
    interval = int(os.getenv("PLUGIN_INTERVAL", 86400))
    path = os.path.join(BASE_DIR, "plugins")
    while True:
        for _, name, _ in pkgutil.iter_modules([path]):
            module = importlib.import_module(f"app.plugins.{name}")
            plugin = getattr(module, "plugin", None)
            if plugin:
                await asyncio.to_thread(plugin.run, SessionLocal())
        await asyncio.sleep(interval)

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