import os
import logging
import requests

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

def dispatch_summary(article, summary: str) -> None:
    """
    Send the summarized article payload to the configured webhook endpoint.
    """
    if not WEBHOOK_URL:
        logging.warning("WEBHOOK_URL not set; skipping webhook push")
        return
    payload = {
        "id": article.id,
        "feed_name": article.feed_name,
        "title": article.title,
        "link": article.link,
        "published": article.published.isoformat() if article.published else None,
        "summary": summary,
    }
    try:
        requests.post(WEBHOOK_URL, json=payload).raise_for_status()
    except Exception as e:
        logging.error(f"Error dispatching summary for article {article.id}: {e}")