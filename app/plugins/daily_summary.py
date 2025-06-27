import os
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .base import Plugin
from app.models.article import Article, ArticleStatus

# Default LLM settings for daily summary
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1")
TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", 0.5))
MAX_TOKENS = int(os.getenv("MODEL_MAX_TOKENS", 150))
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE") or None

_llm_kwargs = {"model_name": MODEL_NAME, "temperature": TEMPERATURE}
if MAX_TOKENS:
    _llm_kwargs["max_tokens"] = MAX_TOKENS
if OPENAI_API_BASE:
    _llm_kwargs["openai_api_base"] = OPENAI_API_BASE

LLM = ChatOpenAI(**_llm_kwargs)


class DailySummaryPlugin(Plugin):
    """Daily plugin: summarize and highlight last day's summarized articles"""

    @property
    def name(self) -> str:
        return "daily_summary"

    def run(self, session: Session) -> None:
        since = datetime.utcnow() - timedelta(days=1)
        arts = (
            session.query(Article)
            .filter(Article.status == ArticleStatus.summarized)
            .filter(Article.updated_at >= since)
            .all()
        )
        if not arts:
            return

        # Build prompt with titles and AI summaries
        lines = ["Daily summary of today's articles:"]
        for a in arts:
            lines.append(f"- {a.title}: {a.link}\n  {a.ai_summary}")

        messages = [
            SystemMessage(content="You are an assistant that composes a daily highlight of articles."),
            HumanMessage(content="\n".join(lines)),
        ]
        try:
            resp = LLM(messages)
            highlight = resp.content.strip()
            logging.info(f"[DailySummary] {highlight}")
        except Exception as e:
            logging.error(f"Error in daily summary plugin: {e}")


plugin = DailySummaryPlugin()