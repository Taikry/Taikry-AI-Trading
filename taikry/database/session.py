"""
Database Session Management for TAIKRY AI MARKET INTELLIGENCE PRO
"""
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from taikry.config import DATABASE_URL
from taikry.database.models import Base

logger = logging.getLogger("taikry.database.session")

# Normalize Render's postgres:// scheme to postgresql:// for SQLAlchemy 2.0
db_url = DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

connect_args = {}
engine_kwargs = {"pool_pre_ping": True}

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    # PostgreSQL / Cloud SQL production pooling configuration
    engine_kwargs.update({
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "300")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30"))
    })

engine = create_engine(
    db_url,
    connect_args=connect_args,
    **engine_kwargs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

def init_db():
    """Initializes tables idempotently and runs schema migrations."""
    Base.metadata.create_all(bind=engine)
    try:
        from taikry.database.migrate_lifecycle_events import run_migration
        run_migration()
    except Exception as exc:
        logger.exception("Lifecycle schema migration failed")
        raise RuntimeError("Lifecycle schema migration failed") from exc
    try:
        from taikry.database.migrate_vip_subscriptions import run_vip_migration
        run_vip_migration()
    except Exception as exc:
        logger.exception("VIP subscription schema migration failed")
        raise RuntimeError("VIP subscription schema migration failed") from exc
    try:
        from taikry.database.migrate_learning_metrics import run_learning_migration
        run_learning_migration()
    except Exception as exc:
        logger.exception("Agent-learning schema migration failed")
        raise RuntimeError("Agent-learning schema migration failed") from exc

# Auto-initialize database schema
init_db()

def get_db():
    """FastAPI dependency for DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
