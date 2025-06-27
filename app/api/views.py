import os
from datetime import datetime
from flask import Flask, request, jsonify, abort, render_template_string, redirect, url_for, flash
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.feed import Feed
from app.models.user import User
from app.models.article import Article, ArticleStatus

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secret123")
## FEED MANAGEMENT WEB PAGE ##
@app.route("/web/feeds", methods=["GET", "POST"])
def web_manage_feeds():
    session: Session = SessionLocal()
    feeds = session.query(Feed).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        url = request.form.get("url", "").strip()
        if not name or not url:
            flash("Both name and URL are required.", "danger")
        else:
            if session.query(Feed).filter_by(name=name).first():
                flash(f"Feed '{name}' already exists.", "danger")
            else:
                session.add(Feed(name=name, url=url))
                session.commit()
                flash(f"Added feed '{name}'.", "success")
                session.close()
                return redirect(url_for("web_manage_feeds"))
    session.close()
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
    session: Session = SessionLocal()
    deleted = session.query(Feed).filter_by(name=name).delete()
    session.commit()
    session.close()
    if deleted:
        flash(f"Feed '{name}' deleted.", "success")
    else:
        flash("Feed not found.", "danger")
    return redirect(url_for("web_manage_feeds"))

# ========== USER INTEREST MANAGEMENT WEB PAGE ==========
@app.route("/web/users", methods=["GET", "POST"])
def web_manage_users():
    session: Session = SessionLocal()
    users = session.query(User).all()
    if request.method == 'POST':
        username  = request.form.get('username', '').strip()
        webhook   = request.form.get('webhook', '').strip()
        interests = [it.strip() for it in request.form.get('interests', '').split(',') if it.strip()]
        if not username or not webhook or not interests:
            flash("Username, webhook, and interests (comma-separated) are all required.", "danger")
        else:
            session.add(User(username=username, webhook=webhook, interests=interests))
            session.commit()
            flash(f"Added user '{username}'.", "success")
            session.close()
            return redirect(url_for('web_manage_users'))
    session.close()
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
    session: Session = SessionLocal()
    deleted = session.query(User).filter_by(username=username).delete()
    session.commit()
    session.close()
    if deleted:
        flash(f"User '{username}' deleted.", "success")
    else:
        flash("User not found.", "danger")
    return redirect(url_for("web_manage_users"))

@app.route("/feeds", methods=["GET"])
def get_feeds():
    session: Session = SessionLocal()
    feeds = session.query(Feed).all()
    session.close()
    return jsonify([{"name": f.name, "url": f.url} for f in feeds])

@app.route("/feeds", methods=["POST"])
def add_feed():
    data = request.get_json()
    if not data or "name" not in data or "url" not in data:
        abort(400, "Request must include 'name' and 'url'")
    session: Session = SessionLocal()
    if session.query(Feed).filter_by(name=data["name"]).first():
        session.close()
        abort(400, f"Feed with name {data['name']} already exists")
    session.add(Feed(name=data["name"], url=data["url"]))
    session.commit()
    session.close()
    return jsonify({"name": data["name"], "url": data["url"]}), 201

@app.route("/feeds/<string:name>", methods=["PUT"])
def update_feed(name):
    data = request.get_json()
    if not data or "url" not in data:
        abort(400, "Request must include 'url'")
    session: Session = SessionLocal()
    feed = session.query(Feed).filter_by(name=name).first()
    if not feed:
        session.close()
        abort(404, f"Feed '{name}' not found")
    feed.url = data["url"]
    session.commit()
    session.close()
    return jsonify({"name": name, "url": feed.url})

@app.route("/feeds/<string:name>", methods=["DELETE"])
def delete_feed(name):
    session: Session = SessionLocal()
    deleted = session.query(Feed).filter_by(name=name).delete()
    session.commit()
    session.close()
    if not deleted:
        abort(404, f"Feed '{name}' not found")
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
        feeds = session.query(Feed).all()
        selected = feeds
        if names:
            selected = [f for f in feeds if f.name in names]
        for feed in selected:
            fetch_and_store(session, {"name": feed.name, "url": feed.url})
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