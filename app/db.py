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
    Ensure the target database exists and all tables are created.
    If the database itself is missing, connect to the default 'postgres' database
    and issue a CREATE DATABASE, then initialize tables.
    """
    from sqlalchemy.exc import OperationalError as SAOperationalError
    from sqlalchemy.engine.url import make_url
    import logging

    try:
        Base.metadata.create_all(bind=engine)
    except SAOperationalError as err:
        # Database may not exist; attempt to create it and retry
        url = make_url(DATABASE_URL)
        default_url = url.set(database="postgres")
        db_name = url.database
        logging.warning(f"Database '{db_name}' not found; creating it...")
        default_engine = create_engine(default_url)
        with default_engine.connect() as conn:
            conn.execute("commit")
            conn.execute(f'CREATE DATABASE "{db_name}"')
        default_engine.dispose()
        # Retry table creation on the target database
        Base.metadata.create_all(bind=engine)
