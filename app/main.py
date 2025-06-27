import os
import time
import logging

import feedparser
import yaml
import requests
import openai

from datetime import datetime
from sqlalchemy.orm import Session

from .db import SessionLocal, init_db
from .models import Article, ArticleStatus

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "feeds.yml")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 300))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
openai.api_key = os.getenv("OPENAI_API_KEY")


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
            prompt = (
                f"Please provide a concise summary for the following article:\n"
                f"Title: {article.title}\n"
                f"Link: {article.link}\n"
            )
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=prompt,
                max_tokens=150,
                temperature=0.5,
            )
            summary = response.choices[0].text.strip()
            article.summary = summary
            article.status = ArticleStatus.summarized
            session.commit()
            if WEBHOOK_URL:
                payload = {
                    "id": article.id,
                    "feed_name": article.feed_name,
                    "title": article.title,
                    "link": article.link,
                    "published": article.published.isoformat()
                    if article.published
                    else None,
                    "summary": summary,
                }
                requests.post(WEBHOOK_URL, json=payload).raise_for_status()
            else:
                logging.warning("WEBHOOK_URL not set; skipping webhook push")
        except Exception as e:
            session.rollback()
            article.status = ArticleStatus.error
            session.commit()
            logging.error(f"Error processing article {article.id}: {e}")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    init_db()
    feeds, interval = load_config()
    logging.info("Starting RSS polling loop")
    while True:
        session = SessionLocal()
        try:
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
