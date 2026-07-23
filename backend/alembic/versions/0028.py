"""enforce one primary product image

Revision ID: 0028
Revises: 0027
Create Date: 2026-07-23

"""

import sqlalchemy as sa

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

PRIMARY_PRODUCT_IMAGE_PREDICATE = (
    "owner_type = 'product' AND kind = 'image' AND is_primary IS TRUE"
)
PRIMARY_PRODUCT_IMAGE_INDEX = "uq_assets_one_primary_product_image"


def upgrade() -> None:
    op.execute(
        """
        WITH ranked_primary_images AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY owner_id
                    ORDER BY
                        CASE WHEN review_state = 'approved' THEN 0 ELSE 1 END,
                        updated_at DESC,
                        created_at DESC,
                        id DESC
                ) AS primary_rank
            FROM assets
            WHERE owner_type = 'product'
              AND kind = 'image'
              AND is_primary IS TRUE
        )
        UPDATE assets
        SET is_primary = FALSE
        WHERE id IN (
            SELECT id
            FROM ranked_primary_images
            WHERE primary_rank > 1
        )
        """
    )
    op.create_index(
        PRIMARY_PRODUCT_IMAGE_INDEX,
        "assets",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text(PRIMARY_PRODUCT_IMAGE_PREDICATE),
    )


def downgrade() -> None:
    op.drop_index(PRIMARY_PRODUCT_IMAGE_INDEX, table_name="assets")
