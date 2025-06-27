import threading
import os
import yaml

from flask import Flask, request, jsonify, abort, render_template_string, redirect, url_for, flash
from datetime import datetime
from sqlalchemy.orm import Session


from app.db import SessionLocal
from app.models.article import Article, ArticleStatus

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "feeds.yml")
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


# For flash messages in forms
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secret123")
# Web interface for feeds and users

# ========== FEED MANAGEMENT WEB PAGE ==========
@app.route("/web/feeds", methods=["GET", "POST"])
def web_manage_feeds():
    cfg, feeds, interval = read_config()
    message = None
    # Handle add new feed
    if request.method == "POST":
        name = request.form.get('name', '').strip()
        url = request.form.get('url', '').strip()
        if not name or not url:
            flash("Both name and URL are required.", "danger")
        else:
            # Prevent duplicates
            for f in feeds:
                if f.get("name") == name:
                    flash(f"Feed '{name}' already exists.", "danger")
                    break
            else:
                feeds.append({'name': name, 'url': url})
                cfg['feeds'] = feeds
                write_config(cfg)
                flash(f"Added feed '{name}'.", "success")
                return redirect(url_for('web_manage_feeds'))
    # HTML template as a string (simple, in-file)
    html = '''
    <html><head><title>Manage RSS Feeds</title></head><body>
    <h1>RSS Feeds</h1>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for cat, msg in messages %}<div style="color: {{'red' if cat=='danger' else 'green'}}">{{msg}}</div>{% endfor %}
      {% endif %}
    {% endwith %}
    <form method="post">
        <input name="name" placeholder="Feed name">
        <input name="url" placeholder="Feed URL">
        <button type="submit">Add Feed</button>
    </form>
    <table border="1" cellpadding="5">
    <tr><th>Name</th><th>URL</th><th>Action</th></tr>
    {% for feed in feeds %}
        <tr>
            <td>{{feed['name']}}</td>
            <td><a href="{{feed['url']}}" target="_blank">{{feed['url']}}</a></td>
            <td>
                <form action="{{url_for('delete_feed_web', name=feed['name'])}}" method="post" style="display:inline">
                    <button type="submit">Delete</button>
                </form>
            </td>
        </tr>
    {% endfor %}
    </table>
    <p><a href="/web/users">Manage User Interests</a></p>
    </body></html>
    '''
    return render_template_string(html, feeds=feeds)

# Feed delete via POST to avoid accidental GETs
@app.route("/web/feeds/delete/<string:name>", methods=["POST"])
def delete_feed_web(name):
    cfg, feeds, interval = read_config()
    feeds2 = [f for f in feeds if f.get("name") != name]
    if len(feeds2) < len(feeds):
        cfg['feeds'] = feeds2
        write_config(cfg)
        flash(f"Feed '{name}' deleted.", "success")
    else:
        flash("Feed not found.", "danger")
    return redirect(url_for('web_manage_feeds'))

# ========== USER INTEREST MANAGEMENT WEB PAGE ==========
@app.route("/web/users", methods=["GET", "POST"])
def web_manage_users():
    users_path = os.path.join(BASE_DIR, "config", "users.yml")
    # Load users config
    with open(users_path, 'r') as f:
        cfg = yaml.safe_load(f) or {}
    users = cfg.get('users', [])
    # Add user form POST
    if request.method == 'POST':
        username  = request.form.get('username', '').strip()
        webhook   = request.form.get('webhook', '').strip()
        interests = [it.strip() for it in request.form.get('interests', '').split(',') if it.strip()]
        if not username or not webhook or not interests:
            flash("Username, webhook, and interests (comma-separated) are all required.", "danger")
        elif any(u.get('username')==username for u in users):
            flash(f"Username {username} already exists.", "danger")
        else:
            users.append({'username': username, 'webhook': webhook, 'interests': interests})
            cfg['users'] = users
            with open(users_path, 'w') as f:
                yaml.safe_dump(cfg, f)
            flash(f"Added user '{username}'.", "success")
            return redirect(url_for('web_manage_users'))
    # Render web page
    html = '''
    <html><head><title>Manage User Interests</title></head><body>
    <h1>User Interests</h1>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for cat, msg in messages %}<div style="color: {{'red' if cat=='danger' else 'green'}}">{{msg}}</div>{% endfor %}
      {% endif %}
    {% endwith %}
    <form method="post">
        <input name="username" placeholder="Username">
        <input name="webhook" placeholder="Webhook URL">
        <input name="interests" placeholder="Interests comma separated">
        <button type="submit">Add User</button>
    </form>
    <table border="1" cellpadding="5">
    <tr><th>Username</th><th>Webhook</th><th>Interests</th><th>Action</th></tr>
    {% for user in users %}
        <tr>
            <td>{{user['username']}}</td>
            <td><a href="{{user['webhook']}}" target="_blank">link</a></td>
            <td>{{', '.join(user['interests'])}}</td>
            <td>
                <form action="{{url_for('delete_user_web', username=user['username'])}}" method="post" style="display:inline">
                    <button type="submit">Delete</button>
                </form>
            </td>
        </tr>
    {% endfor %}
    </table>
    <p><a href="/web/feeds">Back to Feed Management</a></p>
    </body></html>
    '''
    return render_template_string(html, users=users)

# User delete web (POST)
@app.route("/web/users/delete/<string:username>", methods=["POST"])
def delete_user_web(username):
    users_path = os.path.join(BASE_DIR, "config", "users.yml")
    with open(users_path, 'r') as f:
        cfg = yaml.safe_load(f) or {}
    users = cfg.get('users', [])
    users2 = [u for u in users if u.get('username') != username]
    if len(users2) < len(users):
        cfg['users'] = users2
        with open(users_path, 'w') as f:
            yaml.safe_dump(cfg, f)
        flash(f"User '{username}' deleted.", "success")
    else:
        flash("User not found.", "danger")
    return redirect(url_for('web_manage_users'))

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