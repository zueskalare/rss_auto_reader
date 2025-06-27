import os
import json
from typing import List, Tuple, Dict


from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

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

def summarize_articles(
    items: List[Tuple[str, str, str, str]], users: List[Dict[str, List[str]]]
) -> List[Dict[str, object]]:
    """
    Summarize multiple articles and select recipients based on user interests.
    items: list of (title, link, published, feed_summary)
    users: list of {'username': ..., 'interests': [...]}
    Returns a list of dicts with keys: 'summary': str, 'recipients': List[str]
    """
    user_info = "\n".join(
        f"- {u['username']}: {', '.join(u['interests'])}" for u in users
    )
    content_lines = [
        "Users and their interests:",
        user_info,
        "For each of the following articles, provide a JSON array of objects", 
        "each with keys 'summary' (a concise summary) and 'recipients'", 
        "(a list of usernames matching interests).", 
        "Articles:",
    ]
    for title, link, published, feed_summary in items:
        content_lines.extend([
            f"---\nTitle: {title}",
            f"Link: {link}",
            f"Published: {published}",
            f"Feed summary: {feed_summary}",
        ])
    messages = [
        SystemMessage(content="You are a helpful assistant that summarizes articles and filters recipients."),
        HumanMessage(content="\n".join(content_lines)),
    ]
    resp = LLM(messages)
    try:
        results = json.loads(resp.content)
    except Exception:
        raise ValueError(f"Invalid JSON from summarizer: {resp.content}")
    return results

def summarize_article(title: str, link: str) -> str:
    """
    Backward-compatible single-article summary.
    """
    return summarize_articles([(title, link, "", "")], [])[0]['summary']