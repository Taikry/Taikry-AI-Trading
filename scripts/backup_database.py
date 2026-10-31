"""Create a consistent SQLite or PostgreSQL database backup."""

import argparse
import datetime
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from taikry.config import DATABASE_URL


def create_backup(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    parsed = make_url(DATABASE_URL)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if parsed.get_backend_name() == "sqlite":
        source_name = parsed.database
        if not source_name or source_name == ":memory:":
            raise RuntimeError("A file-backed SQLite database is required for backups.")
        source = Path(source_name)
        if not source.is_absolute():
            source = Path.cwd() / source
        if not source.exists():
            raise FileNotFoundError(f"SQLite database file not found: {source}")
        backup_path = output_dir / f"taikry_backup_{stamp}.sqlite3"
        temporary_path = backup_path.with_suffix(".sqlite3.partial")
        try:
            with sqlite3.connect(source) as source_db, sqlite3.connect(temporary_path) as target_db:
                source_db.backup(target_db)
                check = target_db.execute("PRAGMA integrity_check").fetchone()
                if not check or check[0] != "ok":
                    raise RuntimeError(f"SQLite backup integrity check failed: {check}")
            temporary_path.replace(backup_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        return backup_path

    if parsed.get_backend_name() != "postgresql":
        raise RuntimeError(f"Unsupported database backend: {parsed.get_backend_name()}")

    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise RuntimeError("pg_dump was not found. Install PostgreSQL client tools to back up PostgreSQL.")
    backup_path = output_dir / f"taikry_backup_{stamp}.dump"
    temporary_path = backup_path.with_suffix(".dump.partial")
    command = [pg_dump, "--format=custom", "--no-owner", "--file", str(temporary_path)]
    if parsed.host:
        command.extend(["--host", parsed.host])
    if parsed.port:
        command.extend(["--port", str(parsed.port)])
    if parsed.username:
        command.extend(["--username", parsed.username])
    if parsed.database:
        command.extend(["--dbname", parsed.database])

    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    if parsed.query:
        sslmode = parsed.query.get("sslmode")
        if sslmode:
            env["PGSSLMODE"] = sslmode
    try:
        subprocess.run(command, check=True, env=env, capture_output=True, text=True)
        if not temporary_path.exists() or temporary_path.stat().st_size == 0:
            raise RuntimeError("pg_dump completed without writing a backup file.")
        temporary_path.replace(backup_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return backup_path


def prune_backups(output_dir: Path, retention_days: int) -> int:
    if retention_days <= 0:
        return 0
    cutoff = datetime.datetime.now(datetime.timezone.utc).timestamp() - retention_days * 86400
    removed = 0
    for path in output_dir.glob("taikry_backup_*"):
        if path.suffix not in (".sqlite3", ".dump") or not path.is_file():
            continue
        if path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=os.getenv("DATABASE_BACKUP_DIR", "backups"))
    parser.add_argument("--retention-days", type=int, default=int(os.getenv("DATABASE_BACKUP_RETENTION_DAYS", "14")))
    args = parser.parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    try:
        backup = create_backup(output_dir)
        removed = prune_backups(output_dir, args.retention_days)
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1
    print(f"Backup created: {backup}")
    print(f"Old backups removed: {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
