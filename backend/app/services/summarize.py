import os
import json
from typing import List, Tuple, Dict
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import logging

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1")
TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", 0.5))
MAX_TOKENS = int(os.getenv("MODEL_MAX_TOKENS", 4096))
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE") or None

_llm_kwargs = {"model_name": MODEL_NAME, "temperature": TEMPERATURE}
if MAX_TOKENS:
    _llm_kwargs["max_tokens"] = MAX_TOKENS
if OPENAI_API_BASE:
    _llm_kwargs["openai_api_base"] = OPENAI_API_BASE

LLM = ChatOpenAI(**_llm_kwargs)


def summarize_articles(
    items: List[Tuple[str, str, str, str]], users: List[Dict[str, List[str]]]
) -> List[dict]:
    """
    Summarize multiple articles (title, link, published, feed_summary) and
    select recipients based on user interests. Returns structured results.
    """

    class SummarizationResult(BaseModel):
        summary: str = Field(..., description="Concise summary of the article")
        recipients: List[str] = Field(default_factory=list, description="Usernames to send the summary to")


    # Format user interests
    user_info = "\n".join(
        f"- {u['username']}: {', '.join(u['interests'])}" for u in users
    )

    # Format articles
    article_lines = []
    for title, link, published, feed_summary in items:
        article_lines.append(
            f"Title: {title}\nLink: {link}\nPublished: {published}\nFeed Summary: {feed_summary}\n"
        )

    # Instructions for format
    system_prompt = (
        '''You are an assistant that summarizes news articles and recommends them to users by matching each article to their topics of interest.
For the article:
- Write a concise **summary in Markdown format**.
- **Include the article link**.
- Highlight key parts of the summary that match a user's interests using **bold text**. that you think why you recommend this article to the user.'''
    )

    full_prompt = (
        f"Users and their interests:\n{user_info}\n\n"
        f"Articles to summarize:\n{''.join(article_lines)}"
    )
    
    llm = LLM.with_structured_output(SummarizationResult)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=full_prompt)
    ]

    response = llm.invoke(messages)
    # print(f"LLM response: {response}")

    # Try parsing using the parser
    try:
        
        return [response.dict()]  # Because it's a single result
    except Exception as e:
        raise ValueError(f"Model returned invalid structured output:\n{response}\n\nError: {e}")

def summarize_article(title: str, link: str) -> str:
    """
    Backward-compatible single-article summary (returns only the summary text).
    """
    out = summarize_articles([(title, link, "", "")], [])
    return out[0].get('summary', '')