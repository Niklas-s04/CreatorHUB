"""add registration request review metadata

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-15

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

TABLE_NAME = "registration_requests"

registrationrequeststatus_enum = postgresql.ENUM(
    "pending",
    "approved",
    "rejected",
    name="registrationrequeststatus",
)
registrationrequeststatus_col = postgresql.ENUM(
    "pending",
    "approved",
    "rejected",
    name="registrationrequeststatus",
    create_type=False,
)


def _create_registration_requests_table() -> None:
    registrationrequeststatus_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        TABLE_NAME,
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
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_registration_requests_username",
        TABLE_NAME,
        ["username"],
        unique=True,
    )
    op.create_index(
        "ix_registration_requests_status",
        TABLE_NAME,
        ["status"],
        unique=False,
    )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(TABLE_NAME):
        # Some installations were stamped past 0007 after tables had initially
        # been created through SQLAlchemy. Repair that historical schema drift
        # before applying the 0024 metadata additions.
        _create_registration_requests_table()
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns(TABLE_NAME)
    }
    if "reviewed_at" not in existing_columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "rejection_reason" not in existing_columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("rejection_reason", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(TABLE_NAME):
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns(TABLE_NAME)
    }
    if "rejection_reason" in existing_columns:
        op.drop_column(TABLE_NAME, "rejection_reason")
    if "reviewed_at" in existing_columns:
        op.drop_column(TABLE_NAME, "reviewed_at")
