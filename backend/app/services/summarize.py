import os
import json
from typing import List, Tuple, Dict
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import logging
import yaml




def summarize_article(
    items: Tuple[str, str, str, str], users: List[Dict[str, List[str]]]
) -> List[dict]:
    """
    Summarize multiple articles (title, link, published, feed_summary) and
    select recipients based on user interests. Returns structured results.
    """
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

    class SummarizationResult(BaseModel):
        summaries: str = Field(default_factory=str, description="Concise summary of the article in Markdown format")
        recipients: List[str] = Field(default_factory=list, description="List of users interested in the article")
    # print(f"Summarizing {len(items)} articles for {len(users)} users...")
    # Format user interests
    user_info = "\n".join(
        f"{u['username']}: \n\tUser's major or interest is areas about{', '.join(u['interests'])}" for u in users
    )

    # Format articles
    title, link, published, feed_summary = items
    article_line = f"Title: {title}\nLink: {link}\nPublished: {published}\nFeed Summary: {feed_summary}\n"

    # Instructions for format
    system_prompt = (
        '''You are an assistant that summarizes news articles and recommends them to users by matching each article to their topics of interest. If no one is interested in the article, Summarize the article, make recipients a empty list.
For the article:
- Write a concise **summary in Markdown format**.
- **Include the article link**.
- Highlight key parts of the summary that match a user's interests using **bold text**. that you think why you recommend this article to the user.'''
    )

    full_prompt = (
        f"Users and their interests:\n{user_info}\n\n"
        f"Article to summarize:\n{article_line}\n\n"
    )
    
    llm = LLM.with_structured_output(SummarizationResult)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=full_prompt)
    ]

    response = llm.invoke(messages)
    # print(f"LLM response: {response}")

    # Try parsing using the parser
    if response.summaries is None or response.summaries.strip() == "":
        raise ValueError("LLM did not return a valid summary. Please check the input data and model configuration.")
    try:
        
        return response.dict()  
    except Exception as e:
        raise ValueError(f"Model returned invalid structured output:\n{response}\n\nError: {e}")

