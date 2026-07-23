"""drop unique asset hash constraint

Revision ID: 0030
Revises: 0029
Create Date: 2026-07-24

"""

from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_assets_hash", "assets", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("uq_assets_hash", "assets", ["hash"])