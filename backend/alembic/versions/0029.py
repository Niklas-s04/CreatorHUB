"""add knowledge document version type index

Revision ID: 0029
Revises: 0028
Create Date: 2026-07-24

"""

from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_knowledge_doc_versions_type",
        "knowledge_doc_versions",
        ["type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_doc_versions_type", table_name="knowledge_doc_versions")