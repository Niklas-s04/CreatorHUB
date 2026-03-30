"""creator ai settings profiles and defaults

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-30

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


creatoraitone = sa.Enum(
    "neutral",
    "friendly",
    "professional",
    "energetic",
    "direct",
    name="creatoraitone",
)


def upgrade() -> None:
    bind = op.get_bind()
    creatoraitone.create(bind, checkfirst=True)

    op.create_table(
        "creator_ai_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("profile_name", sa.String(length=128), nullable=False),
        sa.Column("is_global_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("clear_name", sa.String(length=128), nullable=False),
        sa.Column("artist_name", sa.String(length=128), nullable=False),
        sa.Column("channel_link", sa.Text(), nullable=False),
        sa.Column("themes", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("platforms", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column(
            "tone",
            postgresql.ENUM(
                "neutral",
                "friendly",
                "professional",
                "energetic",
                "direct",
                name="creatoraitone",
                create_type=False,
            ),
            nullable=False,
            server_default="neutral",
        ),
        sa.Column("target_audience", sa.String(length=256), nullable=True),
        sa.Column("language_code", sa.String(length=16), nullable=False, server_default="de"),
        sa.Column("content_focus", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_name", sa.String(length=128), nullable=True),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_name", sa.String(length=128), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_index(
        "ix_creator_ai_profiles_owner_user_id",
        "creator_ai_profiles",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_creator_ai_profiles_created_by_id",
        "creator_ai_profiles",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        "ix_creator_ai_profiles_updated_by_id",
        "creator_ai_profiles",
        ["updated_by_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_creator_ai_profiles_updated_by_id", table_name="creator_ai_profiles")
    op.drop_index("ix_creator_ai_profiles_created_by_id", table_name="creator_ai_profiles")
    op.drop_index("ix_creator_ai_profiles_owner_user_id", table_name="creator_ai_profiles")
    op.drop_table("creator_ai_profiles")

    bind = op.get_bind()
    creatoraitone.drop(bind, checkfirst=True)
