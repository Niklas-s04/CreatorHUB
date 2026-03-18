"""track when product status changes

Revision ID: 0011_product_status_changed_at
Revises: 0010_asset_upload_security_review_states
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa


# Revisionsdaten für Alembic.
revision = "0011_product_status_changed_at"
down_revision = "0010_asset_upload_security_review_states"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE products SET status_changed_at = COALESCE(updated_at, created_at, timezone('utc', now()))")
    op.alter_column(
        "products",
        "status_changed_at",
        nullable=False,
        server_default=sa.text("timezone('utc', now())"),
    )


def downgrade() -> None:
    op.drop_column("products", "status_changed_at")
