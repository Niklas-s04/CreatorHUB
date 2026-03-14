"""add asset source & license fields

Revision ID: 0002_assets_source_fields
Revises: 0001_initial
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa


# Revisionsdaten für Alembic.
revision = "0002_assets_source_fields"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("source_name", sa.String(length=50), nullable=True))
    op.add_column("assets", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("assets", sa.Column("license_url", sa.Text(), nullable=True))
    op.add_column("assets", sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "fetched_at")
    op.drop_column("assets", "license_url")
    op.drop_column("assets", "source_url")
    op.drop_column("assets", "source_name")