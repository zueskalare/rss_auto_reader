import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rss"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    """
    Create all tables in the target database. If it does not exist,
    attempt to connect to the default 'postgres' database, create it,
    and retry table creation.
    """
    from sqlalchemy.exc import OperationalError as SAOperationalError
    from sqlalchemy.engine.url import make_url
    import logging

    try:
        Base.metadata.create_all(bind=engine)
    except SAOperationalError:
        url = make_url(DATABASE_URL)
        default_url = url.set(database="postgres")
        db_name = url.database
        logging.warning(f"Database '{db_name}' not found; creating it...")
        default_engine = create_engine(default_url)
        with default_engine.connect() as conn:
            conn.execute("commit")
            conn.execute(f'CREATE DATABASE "{db_name}"')
        default_engine.dispose()
        Base.metadata.create_all(bind=engine)

