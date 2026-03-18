"""extend task type enum

Revision ID: 0006_tasktype_defaults
Revises: 0005_deal_drafts
Create Date: 2026-03-04

"""
from __future__ import annotations

from alembic import op

# Revisionsdaten für Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

NEW_VALUES = ("script", "design", "publish")
OLD_VALUES = ("record", "edit", "thumbnail", "upload", "seo", "crosspost")


def upgrade() -> None:
    for value in NEW_VALUES:
        op.execute(f"ALTER TYPE tasktype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    op.execute("ALTER TABLE content_tasks ALTER COLUMN type DROP DEFAULT")
    op.execute("DELETE FROM content_tasks WHERE type::text IN ('script','design','publish')")
    op.execute("CREATE TYPE tasktype_old AS ENUM ('record','edit','thumbnail','upload','seo','crosspost')")
    op.execute("ALTER TABLE content_tasks ALTER COLUMN type TYPE tasktype_old USING type::text::tasktype_old")
    op.execute("DROP TYPE tasktype")
    op.execute("ALTER TYPE tasktype_old RENAME TO tasktype")
    op.execute("ALTER TABLE content_tasks ALTER COLUMN type SET DEFAULT 'record'::tasktype")

