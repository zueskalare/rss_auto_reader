import os
import requests
import gradio as gr

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000/api")

def get_feeds_table():
    resp = requests.get(f"{API_BASE}/feeds")
    resp.raise_for_status()
    return [[f['name'], f['url']] for f in resp.json()]

def add_feed(name: str, url: str):
    resp = requests.post(
        f"{API_BASE}/feeds",
        json={"name": name, "url": url},
    )
    resp.raise_for_status()
    return "", "", get_feeds_table()

def delete_feed(name: str):
    resp = requests.delete(f"{API_BASE}/feeds/{name}")
    resp.raise_for_status()
    return get_feeds_table()

def get_users_table():
    resp = requests.get(f"{API_BASE}/users")
    resp.raise_for_status()
    return [[u['username'], u['webhook'], ", ".join(u.get('interests', []))] for u in resp.json()]

def add_user(username: str, webhook: str, interests: str):
    items = [it.strip() for it in interests.split(',') if it.strip()]
    resp = requests.post(
        f"{API_BASE}/users",
        json={"username": username, "webhook": webhook, "interests": items},
    )
    resp.raise_for_status()
    return "", "", "", get_users_table()

def delete_user(username: str):
    resp = requests.delete(f"{API_BASE}/users/{username}")
    resp.raise_for_status()
    return get_users_table()

def get_llm_settings():
    resp = requests.get(f"{API_BASE}/llm-config")
    resp.raise_for_status()
    cfg = resp.json()
    return (
        cfg.get("model_name", ""),
        str(cfg.get("model_temperature", "")),
        str(cfg.get("model_max_tokens", "")),
        cfg.get("openai_api_base", ""),
    )

def save_llm_settings(model_name: str, temperature: str, max_tokens: str, openai_api_base: str):
    payload = {
        "model_name": model_name,
        "model_temperature": float(temperature) if temperature else 0.0,
        "model_max_tokens": int(max_tokens) if max_tokens else 0,
        "openai_api_base": openai_api_base,
    }
    resp = requests.put(f"{API_BASE}/llm-config", json=payload)
    resp.raise_for_status()
    return get_llm_settings()

def get_articles_table():
    resp = requests.get(f"{API_BASE}/articles")
    resp.raise_for_status()
    data = resp.json()
    return [
        [
            art.get('id'),
            art.get('feed_name'),
            art.get('title'),
            art.get('link'),
            art.get('published') or "",
            art.get('summary') or "",
            art.get('ai_summary') or "",
            ", ".join(art.get('recipients', [])),
            art.get('sent'),
            art.get('status'),
            art.get('created_at'),
            art.get('updated_at') or "",
        ]
        for art in data
    ]

def manual_fetch_and_summarize():
    resp = requests.post(f"{API_BASE}/fetch")
    resp.raise_for_status()
    return get_articles_table()

def manual_dispatch():
    resp = requests.post(f"{API_BASE}/dispatch")
    resp.raise_for_status()
    return get_articles_table()

def build_interface():
    with gr.Blocks(css="frontend/style.css") as demo:
        gr.Markdown("# Admin UI: Articles, Feeds & Webhooks")

        gr.Markdown("## Articles")
        art_table = gr.Dataframe(
            headers=[
                "ID", "Feed", "Title", "Link", "Published",
                "Feed Summary", "AI Summary", "Recipients",
                "Sent", "Status", "Created", "Updated"
            ],
            interactive=False,
        )
        with gr.Row():
            gr.Button("Refresh Articles").click(get_articles_table, None, art_table)
            gr.Button("Fetch & Summarize Now").click(manual_fetch_and_summarize, None, art_table)
            gr.Button("Dispatch Pending").click(manual_dispatch, None, art_table)

        gr.Markdown("## Feeds")
        feed_table = gr.Dataframe(headers=["Name", "URL"], interactive=False)
        with gr.Row():
            name_in = gr.Textbox(label="Name")
            url_in = gr.Textbox(label="URL")
            gr.Button("Add Feed").click(add_feed, [name_in, url_in], [name_in, url_in, feed_table])
        del_feed = gr.Textbox(label="Delete Feed by Name")
        del_feed.change(delete_feed, del_feed, feed_table)
        gr.Button("Refresh Feeds").click(get_feeds_table, None, feed_table)

        gr.Markdown("## Users / Webhooks")
        user_table = gr.Dataframe(headers=["Username", "Webhook", "Interests"], interactive=False)
        with gr.Row():
            uname = gr.Textbox(label="Username")
            hook = gr.Textbox(label="Webhook URL")
            intr = gr.Textbox(label="Interests (comma-separated)")
            gr.Button("Add User").click(add_user, [uname, hook, intr], [uname, hook, intr, user_table])
        del_user = gr.Textbox(label="Delete User by Username")
        del_user.change(delete_user, del_user, user_table)
        gr.Button("Refresh Users").click(get_users_table, None, user_table)

        gr.Markdown("## LLM Settings")
        llm_model = gr.Textbox(label="Model Name")
        llm_temp = gr.Textbox(label="Temperature")
        llm_max = gr.Textbox(label="Max Tokens")
        llm_base = gr.Textbox(label="OpenAI API Base URL")
        with gr.Row():
            gr.Button("Save LLM Settings").click(
                save_llm_settings,
                [llm_model, llm_temp, llm_max, llm_base],
                [llm_model, llm_temp, llm_max, llm_base],
            )
            gr.Button("Refresh LLM Settings").click(
                get_llm_settings,
                None,
                [llm_model, llm_temp, llm_max, llm_base],
            )

    return demo

gr_interface = build_interface()