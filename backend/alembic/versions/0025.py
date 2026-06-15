"""remove implicit admin role default

Revision ID: 0025
Revises: 0024
Create Date: 2026-06-15

"""

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")


def downgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'admin'::userrole")
