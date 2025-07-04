import os
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .base import Plugin
from app.models.article import Article, ArticleStatus
from app.core import load_users
import json
import requests
import yaml
import time



class DailySummaryPlugin(Plugin):
    """Daily plugin: summarize and highlight last day's summarized articles"""

    @property
    def name(self) -> str:
        return "daily_summary"

    # scheduling: run once per day at this HH:MM local time
    schedule_type:str = "daily"
    schedule_time:str = "8:30"  # HH:MM in local time
    schedule_interval:str = None

    def run(self, session: Session) -> None:
        
        from app.core import load_llm_config

        _llm_cfg = load_llm_config()
        MODEL_NAME = _llm_cfg.get(
            "model_name", os.getenv("MODEL_NAME", "gpt-4.1")
        )
        TEMPERATURE = float(
            _llm_cfg.get("model_temperature", os.getenv("MODEL_TEMPERATURE", 0.5))
        )
        MAX_TOKENS = int(
            _llm_cfg.get("model_max_tokens", os.getenv("MODEL_MAX_TOKENS", 4096))
        )
        OPENAI_API_BASE = _llm_cfg.get("openai_api_base") or os.getenv("OPENAI_API_BASE")

        _llm_kwargs = {"model_name": MODEL_NAME, "temperature": TEMPERATURE}
        if MAX_TOKENS:
            _llm_kwargs["max_tokens"] = MAX_TOKENS
        if OPENAI_API_BASE:
            _llm_kwargs["openai_api_base"] = OPENAI_API_BASE

        LLM = ChatOpenAI(**_llm_kwargs)
        
        
        # print(f"Running {self.name} plugin...")
        logging.info(f"Running {self.name} plugin at {datetime.utcnow()}, daily_summary")
        print((f"Running {self.name} plugin at {datetime.utcnow()}, daily_summary"))
        
        since = datetime.utcnow() - timedelta(days=1)
        users = load_users()
        for user in users:
            # Query articles delivered to this user in the last day
            arts = (
                session.query(Article)
                .filter(Article.sent == True)
                .filter(Article.updated_at >= since)
                .all()
            )
            # Filter by recipients for this user
            user_arts = [a for a in arts if user.username in json.loads(a.recipients or "[]")]
            if not user_arts:
                continue

            # Build personalized daily summary
            lines = [f"Daily summary of articles for {user.username}:"]
            for a in user_arts:
                lines.append(f"- {a.title}: {a.link}\n  {a.ai_summary}")

            messages = [
                SystemMessage(content='''You are an assistant that summarizes news articles and recommends them to users by matching each article to their topics of interest.
                - Write a concise **summary in Markdown format** for the articles.
                - **Include the article link**.
                - Highlight key parts of the summary that match a user's interests using **bold text**.'''),
                HumanMessage(content="\n".join(lines)),
            ]
            try:
                resp = LLM.invoke(messages)
                highlight = resp.content.strip()
                # remove think content wraped in <think></think>
                # find the </think> tag and remove everything before it
                if "<think>" in highlight:
                    think_start = highlight.index("<think>")
                    think_end = highlight.index("</think>") + len("</think>")
                    highlight = highlight[think_end:].strip()
                logging.warning(f"[DailySummary:{user.username}] {highlight}")
                webhook = getattr(user, 'webhook', None)
                # calclulate the length of the highlight
                highlight_length = len(highlight.split())
                if highlight_length > 2000:
                    logging.warning(f"[DailySummary:{user.username}] Highlight is too long: {highlight_length} words.")
                    for i in range(0,len(highlight.split()), 1500):
                        chunk = " ".join(highlight.split()[i:i+1500])
                        if i == 0:
                            payload = {"ai_summary": f'# Daily Summary: \n{chunk}'}
                        else:
                            payload = { "ai_summary": f'# Daily Summary (continued): \n{chunk}'}
                        try:
                            requests.post(webhook, json=payload, timeout=3600)
                            time.sleep(1)  # avoid hitting rate limits
                        except Exception as e:
                            logging.warning(f"[DailySummary] webhook failed for {user.username}: {e}")
                
                else:
                    # Send highlight to this user's webhook
                    logging.info(f"[DailySummary] Sending summary to webhook for {user.username}: {webhook}")
                    if webhook:
                        payload = {"ai_summary": f'# Daily Summary: \n{highlight}'}
                        try:
                            requests.post(webhook, json=payload, timeout=3600)
                            time.sleep(1)  # avoid hitting rate limits
                        except Exception as e:
                            logging.warning(f"[DailySummary] webhook failed for {user.username}: {e}")
            except Exception as e:
                logging.error(f"Error in daily summary plugin for {user.username}: {e}")


plugin = DailySummaryPlugin()