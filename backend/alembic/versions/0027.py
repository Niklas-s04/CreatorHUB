"""enforce project integrity and reciprocal link indexes

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-23

"""

import sqlalchemy as sa

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM project_categories
                GROUP BY lower(name)
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Project category names collide when compared case-insensitively';
            END IF;
        END
        $$
        """
    )
    op.drop_index(
        "ix_project_categories_name",
        table_name="project_categories",
    )
    op.drop_constraint(
        "project_categories_name_key",
        "project_categories",
        type_="unique",
    )
    op.create_index(
        "ix_project_categories_name_ci",
        "project_categories",
        [sa.text("lower(name)")],
        unique=True,
    )
    op.execute(
        """
        UPDATE projects AS project
        SET owner_user_id = NULL
        WHERE project.owner_user_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM users
              WHERE users.id = project.owner_user_id
          )
        """
    )
    op.create_foreign_key(
        "fk_projects_owner_user_id_users",
        "projects",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_project_content_links_content_item_id",
        "project_content_links",
        ["content_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_product_links_product_id",
        "project_product_links",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_product_links_product_id",
        table_name="project_product_links",
    )
    op.drop_index(
        "ix_project_content_links_content_item_id",
        table_name="project_content_links",
    )
    op.drop_constraint(
        "fk_projects_owner_user_id_users",
        "projects",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_project_categories_name_ci",
        table_name="project_categories",
    )
    op.create_unique_constraint(
        "project_categories_name_key",
        "project_categories",
        ["name"],
    )
    op.create_index(
        "ix_project_categories_name",
        "project_categories",
        ["name"],
        unique=True,
    )
