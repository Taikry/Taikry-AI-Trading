"""
Migration script for Signal Lifecycle Events and Idempotent Deduplication
========================================================================
1. Creates 'signal_lifecycle_events' table if not exists with unique constraint on idempotency_key.
2. Adds 'telegram_message_id' column to 'signal_lifecycles' table if missing.
3. Cleans up stale duplicate WAITING_CONFIRMATION rows in 'signal_lifecycles' table.
"""
import sqlite3
import datetime
import logging
from sqlalchemy import text
from taikry.config import DATABASE_URL
from taikry.database.session import engine, SessionLocal
from taikry.database.models import Base, SignalLifecycleModel
from taikry.trading.lifecycle import SignalState

logger = logging.getLogger("taikry.database.migration")


def run_migration():
    """Executes safe, idempotent migration."""
    # 1. Create tables according to current metadata
    Base.metadata.create_all(bind=engine)

    # 2. Add column to signal_lifecycles if missing
    db = SessionLocal()
    try:
        if DATABASE_URL.startswith("sqlite"):
            # Inspect table columns
            res = db.execute(text("PRAGMA table_info(signal_lifecycles);")).fetchall()
            col_names = [r[1] for r in res]
            if "telegram_message_id" not in col_names:
                logger.info("Adding missing column 'telegram_message_id' to signal_lifecycles table...")
                db.execute(text("ALTER TABLE signal_lifecycles ADD COLUMN telegram_message_id VARCHAR(64);"))
                db.commit()
                logger.info("Column 'telegram_message_id' successfully added.")

        # 3. Clean up stale / expired signals in WAITING_CONFIRMATION
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        all_waiting = db.query(SignalLifecycleModel).filter(
            SignalLifecycleModel.current_state == SignalState.WAITING_CONFIRMATION.value
        ).order_by(SignalLifecycleModel.created_at.desc()).all()

        seen_active_combos = set()
        stale_count = 0

        for sig in all_waiting:
            sig_exp = sig.expires_at
            if sig_exp and sig_exp.tzinfo is None:
                sig_exp = sig_exp.replace(tzinfo=datetime.timezone.utc)

            # Check if expired
            if sig_exp and now_dt > sig_exp:
                sig.current_state = SignalState.EXPIRED.value
                sig.invalidation_reason_en = "Signal expired during migration cleanup."
                sig.invalidation_reason_kh = "សញ្ញាផុតកំណត់ក្នុងអំឡុងពេលសម្អាតប្រព័ន្ធ។"
                stale_count += 1
                continue

            # Check if duplicate waiting setup
            combo = (sig.symbol, sig.direction)
            if combo in seen_active_combos:
                # Mark as CANCELLED to prevent repeated mass transitions
                sig.current_state = SignalState.INVALIDATED.value
                sig.invalidation_reason_en = "Superseded by newer lifecycle candidate during deduplication audit."
                sig.invalidation_reason_kh = "ត្រូវបានជំនួសដោយបេក្ខភាពថ្មីជាងអំឡុងពេលសវនកម្មកាត់បន្ថយសារស្ទួន។"
                stale_count += 1
            else:
                seen_active_combos.add(combo)

        if stale_count > 0:
            db.commit()
            logger.info(f"Cleaned up {stale_count} stale/duplicate WAITING_CONFIRMATION signals.")

    except Exception as e:
        logger.error(f"Migration error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migration()
    print("Lifecycle events migration completed successfully.")
