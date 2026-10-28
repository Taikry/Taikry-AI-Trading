"""
Database Session Management for TAIKRY AI MARKET INTELLIGENCE PRO
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from taikry.config import DATABASE_URL
from taikry.database.models import Base

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes tables idempotently and runs schema migrations."""
    Base.metadata.create_all(bind=engine)
    try:
        from taikry.database.migrate_lifecycle_events import run_migration
        run_migration()
    except Exception:
        pass
    try:
        from taikry.database.migrate_vip_subscriptions import run_vip_migration
        run_vip_migration()
    except Exception:
        pass

# Auto-initialize database schema
init_db()

def get_db():
    """FastAPI dependency for DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
