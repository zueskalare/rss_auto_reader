import os
import yaml

import gradio as gr
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models.article import Article

BASE_DIR = os.path.dirname(__file__)
FEEDS_CONFIG = os.path.join(BASE_DIR, "config", "feeds.yml")
USERS_CONFIG = os.path.join(BASE_DIR, "config", "users.yml")

def load_full_config():
    if not os.path.exists(FEEDS_CONFIG):
        return {}
    with open(FEEDS_CONFIG, "r") as f:
        return yaml.safe_load(f) or {}

def save_full_config(cfg: dict):
    with open(FEEDS_CONFIG, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

def get_feeds_table():
    cfg = load_full_config()
    return [[f.get("name"), f.get("url")] for f in cfg.get("feeds", [])]

def add_feed(name: str, url: str):
    cfg = load_full_config()
    feeds = cfg.get("feeds", [])
    if name and url and not any(f.get("name")==name for f in feeds):
        feeds.append({"name": name, "url": url})
        cfg["feeds"] = feeds
        save_full_config(cfg)
    return ["", ""], feeds

def delete_feed(name: str):
    cfg = load_full_config()
    feeds = [f for f in cfg.get("feeds", []) if f.get("name") != name]
    cfg["feeds"] = feeds
    save_full_config(cfg)
    return feeds

def load_users():
    if not os.path.exists(USERS_CONFIG):
        return []
    with open(USERS_CONFIG, "r") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("users", [])

def save_users(users: list):
    with open(USERS_CONFIG, "w") as f:
        yaml.safe_dump({"users": users}, f, sort_keys=False)

def get_users_table():
    users = load_users()
    return [[u.get("username"), u.get("webhook"), ", ".join(u.get("interests", []))] for u in users]

def add_user(username: str, webhook: str, interests: str):
    users = load_users()
    if username and webhook and interests and not any(u.get("username")==username for u in users):
        items = [it.strip() for it in interests.split(',') if it.strip()]
        users.append({"username": username, "webhook": webhook, "interests": items})
        save_users(users)
    return ["", "", ""], users

def delete_user(username: str):
    users = [u for u in load_users() if u.get("username") != username]
    save_users(users)
    return users

def get_articles_table():
    session: Session = SessionLocal()
    try:
        arts = session.query(Article).order_by(Article.created_at.desc()).all()
        rows = []
        for a in arts:
            rows.append([
                a.id,
                a.feed_name,
                a.title,
                a.link,
                a.published.isoformat() if a.published else "",
                a.summary or "",
                a.status.value,
                a.created_at.isoformat(),
                a.updated_at.isoformat() if a.updated_at else "",
            ])
        return rows
    finally:
        session.close()

def build_interface():
    with gr.Blocks() as demo:
        gr.Markdown("# Admin UI: Articles, Feeds & Webhooks")

        gr.Markdown("## Articles")
        art_table = gr.Dataframe(
            headers=["ID","Feed","Title","Link","Published","Summary","Status","Created","Updated"],
            interactive=False)
        gr.Button("Refresh Articles").click(get_articles_table, None, art_table)

        gr.Markdown("## Feeds")
        feed_table = gr.Dataframe(headers=["Name","URL"], interactive=False)
        with gr.Row():
            name_in = gr.Textbox(label="Name")
            url_in = gr.Textbox(label="URL")
            gr.Button("Add Feed").click(add_feed, [name_in, url_in], [name_in, url_in, feed_table])
        gr.Textbox(label="Delete Feed by Name").change(lambda x: delete_feed(x), None, feed_table)
        gr.Button("Refresh Feeds").click(get_feeds_table, None, feed_table)

        gr.Markdown("## Users / Webhooks")
        user_table = gr.Dataframe(headers=["Username","Webhook","Interests"], interactive=False)
        with gr.Row():
            uname = gr.Textbox(label="Username")
            hook = gr.Textbox(label="Webhook URL")
            intr = gr.Textbox(label="Interests (comma-separated)")
            gr.Button("Add User").click(add_user, [uname, hook, intr], [uname, hook, intr, user_table])
        gr.Textbox(label="Delete User by Username").change(lambda x: delete_user(x), None, user_table)
        gr.Button("Refresh Users").click(get_users_table, None, user_table)

    return demo

gr_interface = build_interface()