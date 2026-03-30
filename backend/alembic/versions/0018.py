"""email governance, templates, and draft traceability

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-30

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


emailrisklevel = sa.Enum("low", "medium", "high", "critical", name="emailrisklevel")
emailapprovalstatus = sa.Enum(
    "not_required", "pending", "approved", "rejected", name="emailapprovalstatus"
)
emailhandoffstatus = sa.Enum(
    "draft", "blocked", "ready_for_send", "handed_off", name="emailhandoffstatus"
)
emaildraftsource = sa.Enum("ai_generate", "ai_refine", "template", "manual", name="emaildraftsource")
emaildraftsuggestiontype = sa.Enum(
    "ai_draft",
    "ai_refine",
    "risk_assessment",
    "template_applied",
    "approval_decision",
    "handoff_decision",
    "system_note",
    name="emaildraftsuggestiontype",
)


def upgrade() -> None:
    bind = op.get_bind()
    emailrisklevel.create(bind, checkfirst=True)
    emailapprovalstatus.create(bind, checkfirst=True)
    emailhandoffstatus.create(bind, checkfirst=True)
    emaildraftsource.create(bind, checkfirst=True)
    emaildraftsuggestiontype.create(bind, checkfirst=True)

    op.create_table(
        "email_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "intent",
            postgresql.ENUM(
                "sponsoring",
                "support",
                "collab",
                "shipping",
                "refund",
                "unknown",
                name="emailintent",
                create_type=False,
            ),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("subject_template", sa.String(length=256), nullable=True),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_name", sa.String(length=128), nullable=True),
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
        sa.ForeignKeyConstraint(["thread_id"], ["email_threads.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_email_templates_thread_id", "email_templates", ["thread_id"], unique=False)
    op.create_index("ix_email_templates_created_by_id", "email_templates", ["created_by_id"], unique=False)

    op.add_column("email_drafts", sa.Column("parent_draft_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("email_drafts", sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "email_drafts", sa.Column("version_number", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "email_drafts",
        sa.Column(
            "source",
            postgresql.ENUM(
                "ai_generate",
                "ai_refine",
                "template",
                "manual",
                name="emaildraftsource",
                create_type=False,
            ),
            nullable=False,
            server_default="ai_generate",
        ),
    )
    op.add_column(
        "email_drafts",
        sa.Column(
            "risk_level",
            postgresql.ENUM(
                "low",
                "medium",
                "high",
                "critical",
                name="emailrisklevel",
                create_type=False,
            ),
            nullable=False,
            server_default="low",
        ),
    )
    op.add_column("email_drafts", sa.Column("risk_summary", sa.Text(), nullable=True))
    op.add_column(
        "email_drafts",
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "email_drafts",
        sa.Column(
            "approval_status",
            postgresql.ENUM(
                "not_required",
                "pending",
                "approved",
                "rejected",
                name="emailapprovalstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="not_required",
        ),
    )
    op.add_column(
        "email_drafts",
        sa.Column(
            "handoff_status",
            postgresql.ENUM(
                "draft",
                "blocked",
                "ready_for_send",
                "handed_off",
                name="emailhandoffstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
    )
    op.add_column("email_drafts", sa.Column("handoff_note", sa.Text(), nullable=True))
    op.add_column("email_drafts", sa.Column("handed_off_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("email_drafts", sa.Column("handed_off_by_name", sa.String(length=128), nullable=True))
    op.add_column("email_drafts", sa.Column("handed_off_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_email_drafts_parent_draft_id", "email_drafts", ["parent_draft_id"], unique=False)
    op.create_index("ix_email_drafts_template_id", "email_drafts", ["template_id"], unique=False)
    op.create_index("ix_email_drafts_handed_off_by_id", "email_drafts", ["handed_off_by_id"], unique=False)

    op.create_foreign_key(
        "fk_email_drafts_parent_draft_id",
        "email_drafts",
        "email_drafts",
        ["parent_draft_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_email_drafts_template_id",
        "email_drafts",
        "email_templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "email_draft_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("draft_subject", sa.String(length=256), nullable=True),
        sa.Column("draft_body", sa.Text(), nullable=False),
        sa.Column(
            "tone",
            postgresql.ENUM(
                "short",
                "neutral",
                "friendly",
                "firm",
                name="emailtone",
                create_type=False,
            ),
            nullable=False,
            server_default="neutral",
        ),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_by_name", sa.String(length=128), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["draft_id"], ["email_drafts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_email_draft_versions_draft_id", "email_draft_versions", ["draft_id"], unique=False)
    op.create_index(
        "ix_email_draft_versions_changed_by_id", "email_draft_versions", ["changed_by_id"], unique=False
    )

    op.create_table(
        "email_draft_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "suggestion_type",
            postgresql.ENUM(
                "ai_draft",
                "ai_refine",
                "risk_assessment",
                "template_applied",
                "approval_decision",
                "handoff_decision",
                "system_note",
                name="emaildraftsuggestiontype",
                create_type=False,
            ),
            nullable=False,
            server_default="system_note",
        ),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("summary", sa.String(length=256), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("decided", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_by_name", sa.String(length=128), nullable=True),
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
        sa.ForeignKeyConstraint(["draft_id"], ["email_drafts.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_email_draft_suggestions_draft_id", "email_draft_suggestions", ["draft_id"], unique=False
    )
    op.create_index(
        "ix_email_draft_suggestions_decided_by_id",
        "email_draft_suggestions",
        ["decided_by_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_draft_suggestions_decided_by_id", table_name="email_draft_suggestions")
    op.drop_index("ix_email_draft_suggestions_draft_id", table_name="email_draft_suggestions")
    op.drop_table("email_draft_suggestions")

    op.drop_index("ix_email_draft_versions_changed_by_id", table_name="email_draft_versions")
    op.drop_index("ix_email_draft_versions_draft_id", table_name="email_draft_versions")
    op.drop_table("email_draft_versions")

    op.drop_constraint("fk_email_drafts_template_id", "email_drafts", type_="foreignkey")
    op.drop_constraint("fk_email_drafts_parent_draft_id", "email_drafts", type_="foreignkey")
    op.drop_index("ix_email_drafts_handed_off_by_id", table_name="email_drafts")
    op.drop_index("ix_email_drafts_template_id", table_name="email_drafts")
    op.drop_index("ix_email_drafts_parent_draft_id", table_name="email_drafts")

    op.drop_column("email_drafts", "handed_off_at")
    op.drop_column("email_drafts", "handed_off_by_name")
    op.drop_column("email_drafts", "handed_off_by_id")
    op.drop_column("email_drafts", "handoff_note")
    op.drop_column("email_drafts", "handoff_status")
    op.drop_column("email_drafts", "approval_status")
    op.drop_column("email_drafts", "approval_required")
    op.drop_column("email_drafts", "risk_summary")
    op.drop_column("email_drafts", "risk_level")
    op.drop_column("email_drafts", "source")
    op.drop_column("email_drafts", "version_number")
    op.drop_column("email_drafts", "template_id")
    op.drop_column("email_drafts", "parent_draft_id")

    op.drop_index("ix_email_templates_created_by_id", table_name="email_templates")
    op.drop_index("ix_email_templates_thread_id", table_name="email_templates")
    op.drop_table("email_templates")

    bind = op.get_bind()
    emaildraftsuggestiontype.drop(bind, checkfirst=True)
    emaildraftsource.drop(bind, checkfirst=True)
    emailhandoffstatus.drop(bind, checkfirst=True)
    emailapprovalstatus.drop(bind, checkfirst=True)
    emailrisklevel.drop(bind, checkfirst=True)
