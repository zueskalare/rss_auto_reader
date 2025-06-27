import os
from typing import List, Tuple


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

def summarize_articles(items: List[Tuple[str, str]]) -> List[str]:
    """
    Summarize multiple articles. Each item is a (title, link) tuple.
    Returns a list of summaries in the same order.
    """
    summaries: List[str] = []
    for title, link in items:
        messages = [
            SystemMessage(content="You are a helpful assistant that summarizes articles."),
            HumanMessage(
                content=(
                    f"Title: {title}\n"
                    f"Link: {link}\n"
                    "Please provide a concise summary for the article."
                )
            ),
        ]
        resp = LLM(messages)
        summaries.append(resp.content.strip())
    return summaries

def summarize_article(title: str, link: str) -> str:
    """
    Summarize a single article.
    """
    return summarize_articles([(title, link)])[0]