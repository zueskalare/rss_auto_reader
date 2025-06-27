import os
import logging
import asyncio

import feedparser
import yaml

from datetime import datetime
from sqlalchemy.orm import Session

from .db import SessionLocal, init_db
from .models.article import Article, ArticleStatus
from .api.views import app as flask_app
from .services.summarize import summarize_article
from .services.dispatcher import dispatch_summary
from .models.feed import Feed
from .models.user import User


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
    """Return True if article's title or summary matches any interests (case-insensitive substring)"""
    text = f"{article.title or ''} {article.summary or ''}".lower()
    for item in interests:
        if str(item).lower() in text:
            return True
    return False

import requests
def dispatch_to_user_webhooks(article, summary):
    users = load_users()
    for user in users:
        interests = user.get("interests", [])
        if interests and article_matches_interest(article, interests):
            webhook = user.get("webhook")
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
                    logging.warning(f"User webhook failed for {user.get('username')}: {e}")

BASE_DIR = os.path.dirname(__file__)

CONFIG_PATH = os.path.join(BASE_DIR, "config", "feeds.yml")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 300))

def load_config():
    """Loads polling interval from YAML and feeds from database"""
    with open(CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f) or {}
    interval = cfg.get("interval", POLL_INTERVAL)
    session = SessionLocal()
    try:
        feeds = [{"name": f.name, "url": f.url} for f in session.query(Feed).all()]
    finally:
        session.close()
    return feeds, int(os.getenv("POLL_INTERVAL", interval))


def fetch_and_store(session: Session, feed: dict):
    parsed = feedparser.parse(feed["url"])
    for entry in parsed.entries:
        entry_id = entry.get("id") or entry.get("link")
        exists = session.query(Article).filter_by(
            feed_name=feed["name"], entry_id=entry_id
        ).first()
        if not exists:
            published = None
            if entry.get("published_parsed"):
                published = datetime(*entry.published_parsed[:6])
            article = Article(
                feed_name=feed["name"],
                entry_id=entry_id,
                title=entry.get("title"),
                link=entry.get("link"),
                published=published,
                status=ArticleStatus.new,
            )
            session.add(article)
    session.commit()


def summarize_and_push(session: Session):
    articles = session.query(Article).filter_by(status=ArticleStatus.new).all()
    for article in articles:
        try:
            summary = summarize_article(article.title, article.link)
            article.summary = summary
            article.status = ArticleStatus.summarized
            session.commit()
            # Dispatch globally (legacy)
            dispatch_summary(article, summary)
            # Dispatch to any interested users
            dispatch_to_user_webhooks(article, summary)
        except Exception as e:
            session.rollback()
            article.status = ArticleStatus.error
            session.commit()
            logging.error(f"Error summarizing article {article.id}: {e}")


# ASGI and Gradio imports
import gradio as gr
from .gradio_ui import gr_interface
from starlette.applications import Starlette
from starlette.middleware.wsgi import WSGIMiddleware

# --- ASGI integration: wrap Flask app and schedule async polling ---
app = Starlette()
app.mount("/", WSGIMiddleware(flask_app))  # mount Flask app (Flask Web UI & API)


async def async_loop() -> None:
    """Background task: poll feeds and process articles asynchronously."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    init_db()
    # seed initial feed and user configs from YAML into DB
    session = SessionLocal()
    try:
        # seed feeds
        with open(CONFIG_PATH, "r") as f:
            cfg = yaml.safe_load(f) or {}
        for fdef in cfg.get("feeds", []):
            if not session.query(Feed).filter_by(name=fdef.get("name")).first():
                session.add(Feed(name=fdef.get("name"), url=fdef.get("url")))
        # seed users
        if os.path.exists(USERS_CONFIG_PATH):
            with open(USERS_CONFIG_PATH, "r") as uf:
                ucfg = yaml.safe_load(uf) or {}
            for udef in ucfg.get("users", []):
                if not session.query(User).filter_by(username=udef.get("username")).first():
                    session.add(User(username=udef.get("username"), webhook=udef.get("webhook"), interests=udef.get("interests", [])))
        session.commit()
    finally:
        session.close()
    while True:
        session = SessionLocal()
        try:
            feeds, interval = load_config()
            for feed in feeds:
                logging.info(f"Fetching feed: {feed['name']} ({feed['url']})")
                fetch_and_store(session, feed)
            summarize_and_push(session)
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
        finally:
            session.close()
        await asyncio.sleep(interval)

@app.on_event("startup")
async def on_startup() -> None:
    # launch background polling loop
    asyncio.create_task(async_loop())
    # launch Gradio admin UI in background
    ui_port = int(os.getenv("UI_PORT", 7860))
    gr_interface.launch(server_name="0.0.0.0", server_port=ui_port)
