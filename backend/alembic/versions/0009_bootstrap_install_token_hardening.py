"""bootstrap install token hardening

Revision ID: 0009_bootstrap_install_token_hardening
Revises: 0008_auth_sessions_security_hardening
Create Date: 2026-03-17

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_bootstrap_install_token_hardening"
down_revision = "0008_auth_sessions_security_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bootstrap_state",
        sa.Column("setup_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("setup_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("setup_completed_by", sa.String(length=64), nullable=True),
        sa.Column("install_token_hash", sa.String(length=128), nullable=True),
        sa.Column("install_token_consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("bootstrap_state")
