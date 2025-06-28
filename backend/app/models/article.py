import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Enum,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db import Base


class ArticleStatus(enum.Enum):
    new = "new"
    summarized = "summarized"
    sent = "sent"


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("feed_name", "entry_id", name="uix_feed_entry"),
    )

    feed_name = Column(String, index=True, nullable=False)
    entry_id = Column(String, index=True, nullable=False)
    title = Column(String, nullable=True)
    link = Column(String, primary_key=True, index=True, nullable=False)
    published = Column(DateTime, nullable=True)
    summary = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    recipients = Column(Text, nullable=True)
    sent = Column(Boolean, default=False, nullable=False)
    status = Column(Enum(ArticleStatus), default=ArticleStatus.new, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False
    )
