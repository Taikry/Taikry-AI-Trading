"""Small ordered migration registry for the project's existing migration scripts."""

import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, List, Tuple

from sqlalchemy import text

logger = logging.getLogger("taikry.database.versioned_migrations")
_POSTGRES_MIGRATION_LOCK_ID = 7401982310042

Migration = Tuple[str, str, Callable[[], None]]


def _migration_steps(database_engine) -> List[Migration]:
    from taikry.database.migrate_telegram_system import run_migration as telegram_system
    from taikry.database.migrate_lifecycle_events import run_migration as lifecycle_events
    from taikry.database.migrate_vip_subscriptions import run_vip_migration as vip_subscriptions
    from taikry.database.migrate_learning_metrics import run_learning_migration as learning_metrics
    from taikry.database.migrate_payment_models import run_payment_migration as payment_models
    from taikry.database.migrate_user_paper_trades import run_migration as user_paper_trades
    from taikry.database.migrate_user_trade_journal import run_migration as user_trade_journal
    from taikry.database.migrate_market_explorer import run_migration as market_explorer

    return [
        ("0001_telegram_system", "Telegram delivery and signal provenance schema", lambda: telegram_system(database_engine)),
        ("0002_lifecycle_events", "Signal lifecycle event ledger", lifecycle_events),
        ("0003_vip_subscriptions", "VIP subscription schema", vip_subscriptions),
        ("0004_learning_metrics", "Agent learning metrics schema", learning_metrics),
        ("0005_payment_models", "Payment metadata and invoice schema", payment_models),
        ("0006_user_paper_trades", "Per-user paper trade ownership", lambda: user_paper_trades(database_engine)),
        ("0007_user_trade_journal", "User trade journals and TP/SL notification preferences", lambda: user_trade_journal(database_engine)),
        ("0008_market_explorer", "Provider symbol registry, personal watchlists, and analysis jobs", lambda: market_explorer(database_engine)),
    ]


@contextmanager
def _migration_lock(database_engine):
    """Serialize startup migrations across workers sharing one database."""
    dialect = database_engine.dialect.name
    if dialect == "postgresql":
        connection = database_engine.connect()
        connection.execute(
            text("SELECT pg_advisory_lock(:lock_id)"),
            {"lock_id": _POSTGRES_MIGRATION_LOCK_ID},
        )
        connection.commit()
        try:
            yield
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": _POSTGRES_MIGRATION_LOCK_ID},
            )
            connection.commit()
            connection.close()
        return

    if dialect == "sqlite" and database_engine.url.database not in (None, ":memory:"):
        database_path = Path(database_engine.url.database).expanduser()
        if not database_path.is_absolute():
            database_path = Path.cwd() / database_path
        lock_path = database_path.with_name(database_path.name + ".migrations.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a+b") as lock_file:
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        return

    yield


def run_pending_migrations(database_engine) -> List[str]:
    """Run each registered migration once and record its version after success."""
    applied_now = []
    with _migration_lock(database_engine):
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "version VARCHAR(80) PRIMARY KEY, "
                    "description VARCHAR(255) NOT NULL, "
                    "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
            )

        for version, description, migration in _migration_steps(database_engine):
            with database_engine.connect() as connection:
                applied = connection.execute(
                    text("SELECT 1 FROM schema_migrations WHERE version = :version"),
                    {"version": version},
                ).first()
            if applied:
                continue

            logger.info("Applying database migration %s: %s", version, description)
            migration()
            with database_engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO schema_migrations (version, description) "
                        "VALUES (:version, :description) ON CONFLICT (version) DO NOTHING"
                    ),
                    {"version": version, "description": description},
                )
            applied_now.append(version)

    return applied_now
