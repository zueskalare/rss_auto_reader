import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Enum,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db import Base


class ArticleStatus(enum.Enum):
    new = "new"
    summarized = "summarized"
    error = "error"


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("feed_name", "entry_id", name="uix_feed_entry"),
    )

    id = Column(Integer, primary_key=True, index=True)
    feed_name = Column(String, index=True, nullable=False)
    entry_id = Column(String, index=True, nullable=False)
    title = Column(String, nullable=True)
    link = Column(String, nullable=True)
    published = Column(DateTime, nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(Enum(ArticleStatus), default=ArticleStatus.new, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False
    )
