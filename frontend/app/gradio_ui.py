import asyncio
import gradio as gr
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models.feed import Feed
from .models.user import User
from .models.article import Article

def get_feeds_table():
    session: Session = SessionLocal()
    try:
        feeds = session.query(Feed).order_by(Feed.name).all()
        return [[f.name, f.url] for f in feeds]
    finally:
        session.close()

def add_feed(name: str, url: str):
    session: Session = SessionLocal()
    try:
        if name and url and not session.query(Feed).filter_by(name=name).first():
            session.add(Feed(name=name, url=url))
            session.commit()
    finally:
        session.close()
    return "", "", get_feeds_table()

def delete_feed(name: str):
    session: Session = SessionLocal()
    try:
        session.query(Feed).filter_by(name=name).delete()
        session.commit()
    finally:
        session.close()
    return get_feeds_table()

def get_users_table():
    session: Session = SessionLocal()
    try:
        users = session.query(User).order_by(User.username).all()
        return [[u.username, u.webhook, ", ".join(u.interests or [])] for u in users]
    finally:
        session.close()

def add_user(username: str, webhook: str, interests: str):
    session: Session = SessionLocal()
    try:
        if username and webhook and interests and not session.query(User).filter_by(username=username).first():
            items = [it.strip() for it in interests.split(',') if it.strip()]
            session.add(User(username=username, webhook=webhook, interests=items))
            session.commit()
    finally:
        session.close()
    return "", "", "", get_users_table()

def delete_user(username: str):
    session: Session = SessionLocal()
    try:
        session.query(User).filter_by(username=username).delete()
        session.commit()
    finally:
        session.close()
    return get_users_table()

def get_articles_table():
    session: Session = SessionLocal()
    try:
        arts = session.query(Article).order_by(Article.created_at.desc()).all()
        return [
            [
                a.id,
                a.feed_name,
                a.title,
                a.link,
                a.published.isoformat() if a.published else "",
                a.summary or "",
                a.ai_summary or "",
                a.recipients or "",
                a.sent,
                a.status.value,
                a.created_at.isoformat(),
                a.updated_at.isoformat() if a.updated_at else "",
            ]
            for a in arts
        ]
    finally:
        session.close()

async def manual_fetch_and_summarize():
    """Fetch new entries for all feeds and summarize them immediately."""
    from .main import fetch_and_store, summarize_and_push

    def job():
        session = SessionLocal()
        try:
            feeds = session.query(Feed).all()
            for f in feeds:
                fetch_and_store(session, {"name": f.name, "url": f.url})
            summarize_and_push(session)
        finally:
            session.close()

    asyncio.create_task(asyncio.to_thread(job))
    return get_articles_table()

async def manual_dispatch():
    """Dispatch any pending summarized articles to configured webhooks now."""
    from .main import dispatch_pending

    def job():
        session = SessionLocal()
        try:
            dispatch_pending(session)
        finally:
            session.close()

    asyncio.create_task(asyncio.to_thread(job))
    return get_articles_table()

def build_interface():
    with gr.Blocks() as demo:
        gr.Markdown("# Admin UI: Articles, Feeds & Webhooks")

        gr.Markdown("## Articles")
        art_table = gr.Dataframe(
            headers=["ID","Feed","Title","Link","Published","Feed Summary","AI Summary","Recipients","Sent","Status","Created","Updated"],
            interactive=False,
        )
        with gr.Row():
            gr.Button("Refresh Articles").click(get_articles_table, None, art_table)
            gr.Button("Fetch & Summarize Now").click(manual_fetch_and_summarize, None, art_table)
            gr.Button("Dispatch Pending").click(manual_dispatch, None, art_table)

        gr.Markdown("## Feeds")
        feed_table = gr.Dataframe(headers=["Name","URL"], interactive=False)
        with gr.Row():
            name_in = gr.Textbox(label="Name")
            url_in = gr.Textbox(label="URL")
            gr.Button("Add Feed").click(add_feed, [name_in, url_in], [name_in, url_in, feed_table])
        del_feed = gr.Textbox(label="Delete Feed by Name")
        del_feed.change(delete_feed, del_feed, feed_table)
        gr.Button("Refresh Feeds").click(get_feeds_table, None, feed_table)

        gr.Markdown("## Users / Webhooks")
        user_table = gr.Dataframe(headers=["Username","Webhook","Interests"], interactive=False)
        with gr.Row():
            uname = gr.Textbox(label="Username")
            hook = gr.Textbox(label="Webhook URL")
            intr = gr.Textbox(label="Interests (comma-separated)")
            gr.Button("Add User").click(add_user, [uname, hook, intr], [uname, hook, intr, user_table])
        del_user = gr.Textbox(label="Delete User by Username")
        del_user.change(delete_user, del_user, user_table)
        gr.Button("Refresh Users").click(get_users_table, None, user_table)

    return demo

gr_interface = build_interface()