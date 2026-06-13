from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def _revision_list(script: ScriptDirectory) -> list:
    # alembic returns heads -> base; reverse for base -> head execution.
    return list(reversed(list(script.walk_revisions())))


def _single_down_revision(revision) -> str:
    down = revision.down_revision
    if down is None:
        return "base"
    if isinstance(down, tuple):
        if len(down) == 0:
            return "base"
        return str(down[0])
    return str(down)


def validate_migrations(database_url: str, alembic_ini: Path) -> int:
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", database_url)

    script = ScriptDirectory.from_config(cfg)
    revisions = _revision_list(script)

    if not revisions:
        print("No Alembic revisions found.")
        return 1

    print(f"Found {len(revisions)} migration revisions.")

    # Start from a clean base to avoid false positives from pre-existing state.
    command.downgrade(cfg, "base")

    for rev in revisions:
        down_target = _single_down_revision(rev)
        print(f"[CHECK] upgrade -> {rev.revision}")
        command.upgrade(cfg, rev.revision)

        print(f"[CHECK] downgrade -> {down_target}")
        command.downgrade(cfg, down_target)

    # Return to latest so downstream jobs can reuse database state if needed.
    command.upgrade(cfg, "head")
    print("Migration upgrade/downgrade validation completed successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Alembic upgrade/downgrade reversibility")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
        help="Database URL used for migration validation",
    )
    parser.add_argument(
        "--alembic-ini",
        default="alembic.ini",
        help="Path to Alembic ini file (default: alembic.ini)",
    )
    args = parser.parse_args()

    if not args.database_url:
        print("DATABASE_URL is required for migration validation.", file=sys.stderr)
        return 2

    return validate_migrations(args.database_url, Path(args.alembic_ini))


if __name__ == "__main__":
    raise SystemExit(main())
