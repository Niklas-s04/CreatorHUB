"""knowledge transparency, versioning, and draft links

Revision ID: 0016
Revises: 0015
Create Date: 2026-03-30

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


knowledgesourcetype = sa.Enum(
    "internal",
    "external",
    "customer",
    "legal",
    "other",
    name="knowledgesourcetype",
)
knowledgesourcereviewstatus = sa.Enum(
    "pending",
    "approved",
    "rejected",
    "needs_update",
    name="knowledgesourcereviewstatus",
)
knowledgetrustlevel = sa.Enum(
    "low",
    "medium",
    "high",
    "verified",
    name="knowledgetrustlevel",
)


def upgrade() -> None:
    bind = op.get_bind()
    knowledgesourcetype.create(bind, checkfirst=True)
    knowledgesourcereviewstatus.create(bind, checkfirst=True)
    knowledgetrustlevel.create(bind, checkfirst=True)

    op.add_column("knowledge_docs", sa.Column("source_name", sa.String(length=256), nullable=True))
    op.add_column("knowledge_docs", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column(
        "knowledge_docs",
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "internal",
                "external",
                "customer",
                "legal",
                "other",
                name="knowledgesourcetype",
                create_type=False,
            ),
            nullable=False,
            server_default="internal",
        ),
    )
    op.add_column(
        "knowledge_docs",
        sa.Column(
            "source_review_status",
            postgresql.ENUM(
                "pending",
                "approved",
                "rejected",
                "needs_update",
                name="knowledgesourcereviewstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column("knowledge_docs", sa.Column("source_review_note", sa.Text(), nullable=True))
    op.add_column("knowledge_docs", sa.Column("origin_summary", sa.Text(), nullable=True))
    op.add_column(
        "knowledge_docs",
        sa.Column(
            "trust_level",
            postgresql.ENUM(
                "low",
                "medium",
                "high",
                "verified",
                name="knowledgetrustlevel",
                create_type=False,
            ),
            nullable=False,
            server_default="medium",
        ),
    )
    op.add_column(
        "knowledge_docs",
        sa.Column("is_outdated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("knowledge_docs", sa.Column("outdated_reason", sa.Text(), nullable=True))
    op.add_column("knowledge_docs", sa.Column("outdated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "knowledge_docs",
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "knowledge_doc_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("knowledge_doc_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "brand_voice",
                "policy",
                "template",
                "rate_card",
                name="knowledgedoctype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "workflow_status",
            postgresql.ENUM(
                "draft",
                "in_review",
                "approved",
                "rejected",
                name="workflowstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("source_name", sa.String(length=256), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "internal",
                "external",
                "customer",
                "legal",
                "other",
                name="knowledgesourcetype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "source_review_status",
            postgresql.ENUM(
                "pending",
                "approved",
                "rejected",
                "needs_update",
                name="knowledgesourcereviewstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("source_review_note", sa.Text(), nullable=True),
        sa.Column("origin_summary", sa.Text(), nullable=True),
        sa.Column(
            "trust_level",
            postgresql.ENUM(
                "low",
                "medium",
                "high",
                "verified",
                name="knowledgetrustlevel",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("is_outdated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("outdated_reason", sa.Text(), nullable=True),
        sa.Column("outdated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_by_name", sa.String(length=128), nullable=True),
        sa.Column("change_note", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["knowledge_doc_id"], ["knowledge_docs.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_knowledge_doc_versions_knowledge_doc_id",
        "knowledge_doc_versions",
        ["knowledge_doc_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_doc_versions_changed_by_id",
        "knowledge_doc_versions",
        ["changed_by_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_doc_draft_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("knowledge_doc_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("linked_by_name", sa.String(length=128), nullable=True),
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
        sa.ForeignKeyConstraint(["knowledge_doc_id"], ["knowledge_docs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["email_draft_id"], ["email_drafts.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_knowledge_doc_draft_links_knowledge_doc_id",
        "knowledge_doc_draft_links",
        ["knowledge_doc_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_doc_draft_links_email_draft_id",
        "knowledge_doc_draft_links",
        ["email_draft_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_doc_draft_links_email_draft_id", table_name="knowledge_doc_draft_links")
    op.drop_index("ix_knowledge_doc_draft_links_knowledge_doc_id", table_name="knowledge_doc_draft_links")
    op.drop_table("knowledge_doc_draft_links")

    op.drop_index("ix_knowledge_doc_versions_changed_by_id", table_name="knowledge_doc_versions")
    op.drop_index("ix_knowledge_doc_versions_knowledge_doc_id", table_name="knowledge_doc_versions")
    op.drop_table("knowledge_doc_versions")

    op.drop_column("knowledge_docs", "current_version")
    op.drop_column("knowledge_docs", "outdated_at")
    op.drop_column("knowledge_docs", "outdated_reason")
    op.drop_column("knowledge_docs", "is_outdated")
    op.drop_column("knowledge_docs", "trust_level")
    op.drop_column("knowledge_docs", "origin_summary")
    op.drop_column("knowledge_docs", "source_review_note")
    op.drop_column("knowledge_docs", "source_review_status")
    op.drop_column("knowledge_docs", "source_type")
    op.drop_column("knowledge_docs", "source_url")
    op.drop_column("knowledge_docs", "source_name")

    bind = op.get_bind()
    knowledgetrustlevel.drop(bind, checkfirst=True)
    knowledgesourcereviewstatus.drop(bind, checkfirst=True)
    knowledgesourcetype.drop(bind, checkfirst=True)
