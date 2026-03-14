"""add perceptual hash to assets

Revision ID: 0004_asset_perceptual_hash
Revises: 0003_email_thread_messages
Create Date: 2026-03-04

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# Revisionsdaten für Alembic.
revision = "0004_asset_perceptual_hash"
down_revision = "0003_email_thread_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("perceptual_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "perceptual_hash")
