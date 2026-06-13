"""add mfa step-up expiry to auth sessions

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-13

"""

from alembic import op
import sqlalchemy as sa


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auth_sessions",
        sa.Column("mfa_step_up_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("auth_sessions", "mfa_step_up_expires_at")
