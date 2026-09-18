"""
database.py
------------
Sets up the local database connection.

We use SQLite as a fallback because GATEMAN is meant to run on ONE local
machine (or one local network) that both the entry gate and exit gate
point to. If MySQL is configured (recommended for this project), both
gates talk to the SAME MySQL database, so a vehicle registered at entry
is IMMEDIATELY visible at the exit/checkout screen.

Reads connection info from .env, supporting two formats:
  1. One combined DATABASE_URL, e.g.
     DATABASE_URL=mysql+pymysql://root:pass@localhost:3306/gateman
  2. Separate DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD variables
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()  # reads variables from .env

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    db_host = os.getenv("DB_HOST")
    db_user = os.getenv("DB_USER")
    if db_host and db_user:
        db_port = os.getenv("DB_PORT", "3306")
        db_name = os.getenv("DB_NAME", "")
        db_password = os.getenv("DB_PASSWORD", "")
        DATABASE_URL = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else:
        DATABASE_URL = "sqlite:///./gateman.db"

# check_same_thread=False is required for SQLite when used with FastAPI's
# threaded request handling (multiple gate screens hitting it at once).
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,   # checks a connection is alive before using it
    pool_recycle=3600,    # recycles connections older than 1 hour — avoids
                            # "MySQL server has gone away" if the app sits
                            # idle overnight (MySQL closes stale connections
                            # on its own after a timeout).
)

# Print (with any password masked) which database we're actually using,
# so it's obvious at a glance instead of silently guessing wrong.
_visible_url = DATABASE_URL
if "@" in _visible_url and "://" in _visible_url:
    scheme, rest = _visible_url.split("://", 1)
    creds_and_host = rest.split("@", 1)
    if len(creds_and_host) == 2 and ":" in creds_and_host[0]:
        user = creds_and_host[0].split(":", 1)[0]
        _visible_url = f"{scheme}://{user}:****@{creds_and_host[1]}"
print(f"[GATEMAN] Using database: {_visible_url}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: gives each request its own DB session and
    always closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
