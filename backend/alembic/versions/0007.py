"""admin setup and registration requests

Revision ID: 0007_admin_setup_and_registration_requests
Revises: 0006_tasktype_defaults
Create Date: 2026-03-17

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

registrationrequeststatus_enum = postgresql.ENUM(
    "pending", "approved", "rejected", name="registrationrequeststatus"
)
registrationrequeststatus_col = postgresql.ENUM(
    "pending", "approved", "rejected", name="registrationrequeststatus", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    registrationrequeststatus_enum.create(bind, checkfirst=True)

    op.add_column(
        "users",
        sa.Column("needs_password_setup", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "registration_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("hashed_password", sa.String(length=256), nullable=False),
        sa.Column(
            "status",
            registrationrequeststatus_col,
            nullable=False,
            server_default=sa.text("'pending'::registrationrequeststatus"),
        ),
        sa.Column(
            "reviewed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_registration_requests_username", "registration_requests", ["username"], unique=True)
    op.create_index("ix_registration_requests_status", "registration_requests", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_registration_requests_status", table_name="registration_requests")
    op.drop_index("ix_registration_requests_username", table_name="registration_requests")
    op.drop_table("registration_requests")

    op.drop_column("users", "needs_password_setup")

    bind = op.get_bind()
    registrationrequeststatus_enum.drop(bind, checkfirst=True)

