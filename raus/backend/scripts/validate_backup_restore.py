from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uuid
from pathlib import Path
from tempfile import gettempdir

import psycopg
from sqlalchemy.engine import URL, make_url


def _run_command(command: list[str], env: dict[str, str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = "\n".join([part for part in [stdout, stderr] if part])
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{details}")


def _admin_url(url: URL) -> URL:
    return url.set(database="postgres")


def _build_pg_env(url: URL) -> dict[str, str]:
    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = str(url.password)
    return env


def _drop_and_create_restore_db(admin_url: URL, restore_db_name: str) -> None:
    with psycopg.connect(str(admin_url), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (restore_db_name,))
            cur.execute(f'DROP DATABASE IF EXISTS "{restore_db_name}"')
            cur.execute(f'CREATE DATABASE "{restore_db_name}"')


def _prepare_probe_row(source_url: URL, marker: str) -> None:
    with psycopg.connect(str(source_url), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS backup_restore_probe (
                    marker TEXT PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                INSERT INTO backup_restore_probe(marker)
                VALUES (%s)
                ON CONFLICT (marker) DO NOTHING
                """,
                (marker,),
            )


def _verify_probe_row(restore_url: URL, marker: str) -> None:
    with psycopg.connect(str(restore_url), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT marker FROM backup_restore_probe WHERE marker = %s",
                (marker,),
            )
            row = cur.fetchone()
            if not row or row[0] != marker:
                raise RuntimeError("Backup/restore verification failed: probe row not found in restored database")


def validate_backup_restore(database_url: str, backup_file: Path, keep_restore_db: bool = False) -> int:
    source_url = make_url(database_url)
    if not source_url.database:
        print("DATABASE_URL must include a database name", file=sys.stderr)
        return 2

    restore_db_name = f"{source_url.database}_restore_ci"
    restore_url = source_url.set(database=restore_db_name)
    admin_url = _admin_url(source_url)
    pg_env = _build_pg_env(source_url)

    marker = f"restore-check-{uuid.uuid4().hex}"
    backup_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"Preparing probe row in source database '{source_url.database}'...")
    _prepare_probe_row(source_url, marker)

    print(f"Creating backup at {backup_file}...")
    _run_command(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--file",
            str(backup_file),
            str(source_url),
        ],
        pg_env,
    )

    print(f"Recreating restore database '{restore_db_name}'...")
    _drop_and_create_restore_db(admin_url, restore_db_name)

    print("Restoring backup into restore database...")
    _run_command(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            str(restore_url),
            str(backup_file),
        ],
        pg_env,
    )

    print("Verifying restored data integrity...")
    _verify_probe_row(restore_url, marker)

    if not keep_restore_db:
        print(f"Cleaning up restore database '{restore_db_name}'...")
        with psycopg.connect(str(admin_url), autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (restore_db_name,))
                cur.execute(f'DROP DATABASE IF EXISTS "{restore_db_name}"')

    print("Backup/restore validation completed successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Postgres backup/restore roundtrip")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
        help="Database URL for source database",
    )
    parser.add_argument(
        "--backup-file",
        default=str(Path(gettempdir()) / "creatorhub-backup-restore.dump"),
        help="Path to backup dump file",
    )
    parser.add_argument(
        "--keep-restore-db",
        action="store_true",
        help="Keep restore database for debugging",
    )
    args = parser.parse_args()

    if not args.database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2

    return validate_backup_restore(
        database_url=args.database_url,
        backup_file=Path(args.backup_file),
        keep_restore_db=args.keep_restore_db,
    )


if __name__ == "__main__":
    raise SystemExit(main())
