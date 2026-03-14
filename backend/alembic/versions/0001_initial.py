"""initial

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# PostgreSQL-Enums: *_enum legt Typen an/entfernt sie, *_col nutzt sie in Spalten ohne Neuanlage.

userrole_enum = postgresql.ENUM("admin", "editor", "viewer", name="userrole")
userrole_col = postgresql.ENUM("admin", "editor", "viewer", name="userrole", create_type=False)

productcondition_enum = postgresql.ENUM("new", "very_good", "good", "ok", "broken", name="productcondition")
productcondition_col = postgresql.ENUM("new", "very_good", "good", "ok", "broken", name="productcondition", create_type=False)

productstatus_enum = postgresql.ENUM("active", "sold", "gifted", "returned", "broken", "archived", name="productstatus")
productstatus_col = postgresql.ENUM("active", "sold", "gifted", "returned", "broken", "archived", name="productstatus", create_type=False)

transactiontype_enum = postgresql.ENUM("purchase", "sale", "gift", "return", "repair", name="transactiontype")
transactiontype_col = postgresql.ENUM("purchase", "sale", "gift", "return", "repair", name="transactiontype", create_type=False)

valuesource_enum = postgresql.ENUM("manual", "estimate", "import", name="valuesource")
valuesource_col = postgresql.ENUM("manual", "estimate", "import", name="valuesource", create_type=False)

assetownertype_enum = postgresql.ENUM("product", "content", "email", "deal", name="assetownertype")
assetownertype_col = postgresql.ENUM("product", "content", "email", "deal", name="assetownertype", create_type=False)

assetkind_enum = postgresql.ENUM("image", "pdf", "link", "video", name="assetkind")
assetkind_col = postgresql.ENUM("image", "pdf", "link", "video", name="assetkind", create_type=False)

assetsource_enum = postgresql.ENUM("upload", "web", name="assetsource")
assetsource_col = postgresql.ENUM("upload", "web", name="assetsource", create_type=False)

assetreviewstate_enum = postgresql.ENUM("pending", "approved", "rejected", name="assetreviewstate")
assetreviewstate_col = postgresql.ENUM("pending", "approved", "rejected", name="assetreviewstate", create_type=False)

contentplatform_enum = postgresql.ENUM("youtube", "shorts", "instagram", "tiktok", "x", "linkedin", name="contentplatform")
contentplatform_col = postgresql.ENUM("youtube", "shorts", "instagram", "tiktok", "x", "linkedin", name="contentplatform", create_type=False)

contenttype_enum = postgresql.ENUM("review", "short", "post", "story", name="contenttype")
contenttype_col = postgresql.ENUM("review", "short", "post", "story", name="contenttype", create_type=False)

contentstatus_enum = postgresql.ENUM("idea", "draft", "recorded", "edited", "scheduled", "published", name="contentstatus")
contentstatus_col = postgresql.ENUM("idea", "draft", "recorded", "edited", "scheduled", "published", name="contentstatus", create_type=False)

tasktype_enum = postgresql.ENUM("record", "edit", "thumbnail", "upload", "seo", "crosspost", name="tasktype")
tasktype_col = postgresql.ENUM("record", "edit", "thumbnail", "upload", "seo", "crosspost", name="tasktype", create_type=False)

taskstatus_enum = postgresql.ENUM("todo", "doing", "done", name="taskstatus")
taskstatus_col = postgresql.ENUM("todo", "doing", "done", name="taskstatus", create_type=False)

emailintent_enum = postgresql.ENUM("sponsoring", "support", "collab", "shipping", "refund", "unknown", name="emailintent")
emailintent_col = postgresql.ENUM("sponsoring", "support", "collab", "shipping", "refund", "unknown", name="emailintent", create_type=False)

emailtone_enum = postgresql.ENUM("short", "neutral", "friendly", "firm", name="emailtone")
emailtone_col = postgresql.ENUM("short", "neutral", "friendly", "firm", name="emailtone", create_type=False)

knowledgedoctype_enum = postgresql.ENUM("brand_voice", "policy", "template", "rate_card", name="knowledgedoctype")
knowledgedoctype_col = postgresql.ENUM("brand_voice", "policy", "template", "rate_card", name="knowledgedoctype", create_type=False)


ALL_ENUMS = [
    userrole_enum,
    productcondition_enum,
    productstatus_enum,
    transactiontype_enum,
    valuesource_enum,
    assetownertype_enum,
    assetkind_enum,
    assetsource_enum,
    assetreviewstate_enum,
    contentplatform_enum,
    contenttype_enum,
    contentstatus_enum,
    tasktype_enum,
    taskstatus_enum,
    emailintent_enum,
    emailtone_enum,
    knowledgedoctype_enum,
]


def upgrade() -> None:
    bind = op.get_bind()

    # Enums genau einmal anlegen.
    for enum in ALL_ENUMS:
        enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("hashed_password", sa.String(length=256), nullable=False),
        sa.Column("role", userrole_col, nullable=False, server_default=sa.text("'admin'::userrole")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("brand", sa.String(length=128)),
        sa.Column("model", sa.String(length=128)),
        sa.Column("category", sa.String(length=128)),
        sa.Column("condition", productcondition_col, nullable=False, server_default=sa.text("'good'::productcondition")),
        sa.Column("purchase_price", sa.Numeric(12, 2)),
        sa.Column("purchase_date", sa.Date()),
        sa.Column("current_value", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default=sa.text("'EUR'")),
        sa.Column("storage_location", sa.String(length=256)),
        sa.Column("serial_number", sa.String(length=128)),
        sa.Column("notes_md", sa.Text()),
        sa.Column("status", productstatus_col, nullable=False, server_default=sa.text("'active'::productstatus")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_products_title", "products", ["title"], unique=False)
    op.create_index("ix_products_updated_at", "products", ["updated_at"], unique=False)

    op.create_table(
        "product_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", transactiontype_col, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default=sa.text("'EUR'")),
        sa.Column("counterparty", sa.String(length=256)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_product_transactions_product_id", "product_transactions", ["product_id"], unique=False)

    op.create_table(
        "product_value_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default=sa.text("'EUR'")),
        sa.Column("source", valuesource_col, nullable=False, server_default=sa.text("'manual'::valuesource")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_product_value_history_product_id", "product_value_history", ["product_id"], unique=False)

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_type", assetownertype_col, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", assetkind_col, nullable=False, server_default=sa.text("'image'::assetkind")),
        sa.Column("source", assetsource_col, nullable=False, server_default=sa.text("'upload'::assetsource")),
        sa.Column("url", sa.Text()),
        sa.Column("local_path", sa.Text()),
        sa.Column("title", sa.String(length=256)),
        sa.Column("license_type", sa.String(length=64)),
        sa.Column("attribution", sa.Text()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("hash", sa.String(length=64)),
        sa.Column("review_state", assetreviewstate_col, nullable=False, server_default=sa.text("'approved'::assetreviewstate")),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("hash", name="uq_assets_hash"),
    )
    op.create_index("ix_assets_owner", "assets", ["owner_type", "owner_id"], unique=False)

    op.create_table(
        "content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("platform", contentplatform_col, nullable=False, server_default=sa.text("'youtube'::contentplatform")),
        sa.Column("type", contenttype_col, nullable=False, server_default=sa.text("'review'::contenttype")),
        sa.Column("status", contentstatus_col, nullable=False, server_default=sa.text("'idea'::contentstatus")),
        sa.Column("title", sa.String(length=256)),
        sa.Column("hook", sa.String(length=256)),
        sa.Column("script_md", sa.Text()),
        sa.Column("description_md", sa.Text()),
        sa.Column("tags_csv", sa.Text()),
        sa.Column("planned_date", sa.Date()),
        sa.Column("publish_date", sa.Date()),
        sa.Column("external_url", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_content_items_product_id", "content_items", ["product_id"], unique=False)

    op.create_table(
        "content_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "content_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", tasktype_col, nullable=False, server_default=sa.text("'record'::tasktype")),
        sa.Column("status", taskstatus_col, nullable=False, server_default=sa.text("'todo'::taskstatus")),
        sa.Column("due_date", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_content_tasks_content_item_id", "content_tasks", ["content_item_id"], unique=False)

    op.create_table(
        "email_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject", sa.String(length=256)),
        sa.Column("raw_body", sa.Text(), nullable=False),
        sa.Column("detected_intent", emailintent_col, nullable=False, server_default=sa.text("'unknown'::emailintent")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "email_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tone", emailtone_col, nullable=False, server_default=sa.text("'neutral'::emailtone")),
        sa.Column("draft_subject", sa.String(length=256)),
        sa.Column("draft_body", sa.Text(), nullable=False),
        sa.Column("questions_to_ask", sa.Text()),
        sa.Column("risk_flags", sa.Text()),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_email_drafts_thread_id", "email_drafts", ["thread_id"], unique=False)

    op.create_table(
        "knowledge_docs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", knowledgedoctype_col, nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_docs_type", "knowledge_docs", ["type"], unique=False)

    op.create_table(
        "ai_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("input_summary", sa.Text()),
        sa.Column("output_summary", sa.Text()),
        sa.Column("meta_json", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_runs_job_type", "ai_runs", ["job_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_runs_job_type", table_name="ai_runs")
    op.drop_table("ai_runs")

    op.drop_index("ix_knowledge_docs_type", table_name="knowledge_docs")
    op.drop_table("knowledge_docs")

    op.drop_index("ix_email_drafts_thread_id", table_name="email_drafts")
    op.drop_table("email_drafts")
    op.drop_table("email_threads")

    op.drop_index("ix_content_tasks_content_item_id", table_name="content_tasks")
    op.drop_table("content_tasks")

    op.drop_index("ix_content_items_product_id", table_name="content_items")
    op.drop_table("content_items")

    op.drop_index("ix_assets_owner", table_name="assets")
    op.drop_table("assets")

    op.drop_index("ix_product_value_history_product_id", table_name="product_value_history")
    op.drop_table("product_value_history")

    op.drop_index("ix_product_transactions_product_id", table_name="product_transactions")
    op.drop_table("product_transactions")

    op.drop_index("ix_products_updated_at", table_name="products")
    op.drop_index("ix_products_title", table_name="products")
    op.drop_table("products")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

    # Enums in umgekehrter Reihenfolge entfernen.
    bind = op.get_bind()
    for enum in reversed(ALL_ENUMS):
        enum.drop(bind, checkfirst=True)