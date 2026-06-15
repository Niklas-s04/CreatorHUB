"""expand mfa secret storage for encrypted values

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-15

"""

from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "mfa_secret",
        existing_type=sa.String(length=128),
        type_=sa.String(length=256),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "mfa_secret",
        existing_type=sa.String(length=256),
        type_=sa.String(length=128),
        existing_nullable=True,
    )
