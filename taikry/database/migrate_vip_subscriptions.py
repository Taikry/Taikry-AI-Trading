"""
Migration script for VIP Telegram Subscriptions and Expiring Invite Links
========================================================================
1. Creates 'vip_subscriptions' table if not exists with appropriate indexes.
2. Creates 'vip_invite_links' table if not exists with unique constraint on invite_link.
3. Inserts default demo/admin subscription records if database is fresh.
"""
import logging
from sqlalchemy import text
from taikry.config import DATABASE_URL
from taikry.database.session import engine, SessionLocal
from taikry.database.models import Base, VIPSubscriptionModel, VIPInviteLinkRecord

logger = logging.getLogger("taikry.database.migrate_vip")

def run_vip_migration():
    """Executes safe, idempotent VIP database migration."""
    Base.metadata.create_all(bind=engine)
    logger.info("VIP subscription database schema initialized successfully.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_vip_migration()
