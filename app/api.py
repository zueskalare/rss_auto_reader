import threading
import os
import yaml

from flask import Flask, request, jsonify, abort
from datetime import datetime
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Article, ArticleStatus

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "feeds.yml")
config_lock = threading.Lock()

def read_config():
    with config_lock:
        with open(CONFIG_PATH, "r") as f:
            cfg = yaml.safe_load(f) or {}
        feeds = cfg.get("feeds", [])
        interval = cfg.get("interval")
    return cfg, feeds, interval

def write_config(cfg):
    with config_lock:
        with open(CONFIG_PATH, "w") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)

app = Flask(__name__)

@app.route("/feeds", methods=["GET"])
def get_feeds():
    cfg, feeds, interval = read_config()
    return jsonify({"feeds": feeds, "interval": interval})

@app.route("/feeds", methods=["POST"])
def add_feed():
    data = request.get_json()
    if not data or "name" not in data or "url" not in data:
        abort(400, "Request must include 'name' and 'url'")
    cfg, feeds, interval = read_config()
    for f in feeds:
        if f.get("name") == data["name"]:
            abort(400, f"Feed with name {data['name']} already exists")
    feeds.append({"name": data["name"], "url": data["url"]})
    cfg["feeds"] = feeds
    write_config(cfg)
    return jsonify({"name": data["name"], "url": data["url"]}), 201

@app.route("/feeds/<string:name>", methods=["PUT"])
def update_feed(name):
    data = request.get_json()
    if not data or "url" not in data:
        abort(400, "Request must include 'url'")
    cfg, feeds, interval = read_config()
    for f in feeds:
        if f.get("name") == name:
            f["url"] = data["url"]
            write_config(cfg)
            return jsonify(f)
    abort(404, f"Feed '{name}' not found")

@app.route("/feeds/<string:name>", methods=["DELETE"])
def delete_feed(name):
    cfg, feeds, interval = read_config()
    new_feeds = [f for f in feeds if f.get("name") != name]
    if len(new_feeds) == len(feeds):
        abort(404, f"Feed '{name}' not found")
    cfg["feeds"] = new_feeds
    write_config(cfg)
    return "", 204

@app.route("/articles", methods=["GET"])
def get_articles():
    since = request.args.get("since")
    status = request.args.get("status")
    limit = request.args.get("limit", type=int)
    session: Session = SessionLocal()
    try:
        query = session.query(Article)
        if status:
            statuses = [ArticleStatus[s.strip()] for s in status.split(",")]
            query = query.filter(Article.status.in_(statuses))
        if since:
            try:
                dt = datetime.fromisoformat(since)
            except ValueError:
                abort(400, "Invalid 'since' datetime format")
            query = query.filter(Article.updated_at >= dt)
        query = query.order_by(Article.updated_at.desc())
        if limit:
            query = query.limit(limit)
        results = query.all()
        response = []
        for art in results:
            response.append({
                "id": art.id,
                "feed_name": art.feed_name,
                "entry_id": art.entry_id,
                "title": art.title,
                "link": art.link,
                "published": art.published.isoformat() if art.published else None,
                "summary": art.summary,
                "status": art.status.value,
                "created_at": art.created_at.isoformat(),
                "updated_at": art.updated_at.isoformat() if art.updated_at else None,
            })
        return jsonify(response)
    finally:
        session.close()

@app.route("/fetch", methods=["POST"])
def trigger_fetch():
    data = request.get_json(silent=True) or {}
    names = data.get("feeds")
    from .main import fetch_and_store, summarize_and_push
    session: Session = SessionLocal()
    try:
        cfg, feeds, interval = read_config()
        selected = feeds
        if names:
            selected = [f for f in feeds if f.get("name") in names]
        for feed in selected:
            fetch_and_store(session, feed)
        summarize_and_push(session)
        return "", 204
    finally:
        session.close()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

def start_api():
    port = int(os.getenv("API_PORT", 8000))
    app.run(host="0.0.0.0", port=port)