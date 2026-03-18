"""asset upload security review states

Revision ID: 0010_asset_upload_security_review_states
Revises: 0009_bootstrap_install_token_hardening
Create Date: 2026-03-17

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE assetreviewstate ADD VALUE IF NOT EXISTS 'quarantine'")
    op.execute("ALTER TYPE assetreviewstate ADD VALUE IF NOT EXISTS 'pending_review'")
    op.execute("ALTER TYPE assetreviewstate ADD VALUE IF NOT EXISTS 'needs_review'")
    op.alter_column(
        "assets",
        "review_state",
        existing_type=sa.Enum(name="assetreviewstate"),
        server_default=sa.text("'pending_review'::assetreviewstate"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "assets",
        "review_state",
        existing_type=sa.Enum(name="assetreviewstate"),
        server_default=sa.text("'approved'::assetreviewstate"),
        existing_nullable=False,
    )

