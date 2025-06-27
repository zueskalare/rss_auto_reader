import os
import time
import logging
import threading

import feedparser
import yaml

from datetime import datetime
from sqlalchemy.orm import Session

from .db import SessionLocal, init_db
from .models import Article, ArticleStatus
from .api import start_api
from .llm import summarize_article
from .dispatcher import dispatch_summary

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "feeds.yml")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 300))

def load_config():
    with open(CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f)
    feeds = cfg.get("feeds", [])
    interval = cfg.get("interval", POLL_INTERVAL)
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
            dispatch_summary(article, summary)
        except Exception as e:
            session.rollback()
            article.status = ArticleStatus.error
            session.commit()
            logging.error(f"Error summarizing article {article.id}: {e}")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    init_db()
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    logging.info("Starting RSS polling loop")
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
        time.sleep(interval)


if __name__ == "__main__":
    main()
