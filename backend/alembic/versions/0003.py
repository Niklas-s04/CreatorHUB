"""email thread messages log

Revision ID: 0003_email_thread_messages
Revises: 0002_assets_source_fields
Create Date: 2026-03-04

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Revisionsdaten für Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


message_role_enum = postgresql.ENUM("user", "assistant", "system", name="emailthreadmessagerole")
message_role_col = postgresql.ENUM(
    "user",
    "assistant",
    "system",
    name="emailthreadmessagerole",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    message_role_enum.create(bind, checkfirst=True)

    op.create_table(
        "email_thread_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            message_role_col,
            nullable=False,
            server_default=sa.text("'user'::emailthreadmessagerole"),
        ),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_email_thread_messages_thread_id",
        "email_thread_messages",
        ["thread_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_thread_messages_thread_id", table_name="email_thread_messages")
    op.drop_table("email_thread_messages")
    message_role_enum.drop(op.get_bind(), checkfirst=True)

