import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.feed import Feed
from app.models.article import Article, ArticleStatus
from app.models.user import User

# Pydantic schemas for request/response models
from pydantic import BaseModel


class FeedIn(BaseModel):
    name: str
    url: str


class FeedUpdate(BaseModel):
    url: str


class FetchIn(BaseModel):
    feeds: Optional[List[str]] = None


class UserIn(BaseModel):
    username: str
    webhook: str
    interests: List[str]


def get_db():
    """Dependency: create and close DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter()


@router.get("/feeds", response_model=List[FeedIn])
def list_feeds(db: Session = Depends(get_db)):
    """List all RSS feeds"""
    feeds = db.query(Feed).all()
    return [{"name": f.name, "url": f.url} for f in feeds]


@router.post("/feeds", response_model=FeedIn, status_code=status.HTTP_201_CREATED)
def create_feed(feed: FeedIn, db: Session = Depends(get_db)):
    """Add a new feed"""
    if db.query(Feed).filter_by(name=feed.name).first():
        raise HTTPException(status_code=400, detail=f"Feed '{feed.name}' already exists")
    new = Feed(name=feed.name, url=feed.url)
    db.add(new)
    db.commit()
    return {"name": new.name, "url": new.url}


@router.put("/feeds/{name}", response_model=FeedIn)
def update_feed(name: str, feed: FeedUpdate, db: Session = Depends(get_db)):
    """Update an existing feed's URL"""
    existing = db.query(Feed).filter_by(name=name).first()
    if not existing:
        raise HTTPException(status_code=404, detail=f"Feed '{name}' not found")
    existing.url = feed.url
    db.commit()
    return {"name": existing.name, "url": existing.url}


@router.delete("/feeds/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed(name: str, db: Session = Depends(get_db)):
    """Delete a feed by name"""
    deleted = db.query(Feed).filter_by(name=name).delete()
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Feed '{name}' not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users", response_model=List[UserIn])
def list_users(db: Session = Depends(get_db)):
    """List all registered users"""
    users = db.query(User).all()
    return [{"username": u.username, "webhook": u.webhook, "interests": u.interests} for u in users]


@router.post("/users", response_model=UserIn, status_code=status.HTTP_201_CREATED)
def create_user(user: UserIn, db: Session = Depends(get_db)):
    """Register a new user webhook and interests"""
    if db.query(User).filter_by(username=user.username).first():
        raise HTTPException(status_code=400, detail=f"User '{user.username}' already exists")
    new = User(username=user.username, webhook=user.webhook, interests=user.interests)
    db.add(new)
    db.commit()
    return {"username": new.username, "webhook": new.webhook, "interests": new.interests}


@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(username: str, db: Session = Depends(get_db)):
    """Delete a user by username"""
    deleted = db.query(User).filter_by(username=username).delete()
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/articles")
def get_articles(
    since: Optional[datetime] = None,
    status: Optional[str] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """List stored articles with optional filtering"""
    query = db.query(Article)
    if status:
        try:
            statuses = [ArticleStatus[s.strip()] for s in status.split(",")]
        except KeyError:
            raise HTTPException(status_code=400, detail="Invalid status value")
        query = query.filter(Article.status.in_(statuses))
    if since:
        query = query.filter(Article.updated_at >= since)
    query = query.order_by(Article.updated_at.desc())
    if limit:
        query = query.limit(limit)
    results = query.all()
    return [
        {
            "id": art.id,
            "feed_name": art.feed_name,
            "entry_id": art.entry_id,
            "title": art.title,
            "link": art.link,
            "published": art.published.isoformat() if art.published else None,
            "summary": art.summary,
            "ai_summary": art.ai_summary,
            "recipients": json.loads(art.recipients) if art.recipients else [],
            "sent": art.sent,
            "status": art.status.value,
            "created_at": art.created_at.isoformat(),
            "updated_at": art.updated_at.isoformat() if art.updated_at else None,
        }
        for art in results
    ]


@router.post("/fetch", status_code=status.HTTP_204_NO_CONTENT)
def trigger_fetch(fetch_in: Optional[FetchIn] = None, db: Session = Depends(get_db)):
    """Trigger immediate fetch and summarization for all or specified feeds"""
    from app.main import fetch_and_store, summarize_and_push

    feeds = db.query(Feed).all()
    selected = feeds
    if fetch_in and fetch_in.feeds:
        selected = [f for f in feeds if f.name in fetch_in.feeds]
    for f in selected:
        fetch_and_store(db, {"name": f.name, "url": f.url})
    summarize_and_push(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/dispatch", status_code=status.HTTP_204_NO_CONTENT)
def trigger_dispatch(db: Session = Depends(get_db)):
    """Trigger immediate dispatch of any pending summarized articles"""
    from app.main import dispatch_pending

    dispatch_pending(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/health")
def health() -> dict:
    """Health check endpoint"""
    return {"status": "ok"}