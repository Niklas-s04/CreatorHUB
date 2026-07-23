from __future__ import annotations

import uuid

import pytest
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Session

from app.models.content import ContentItem
from app.models.product import Product
from app.models.project import (
    Project,
    ProjectCategory,
    project_content_links,
    project_product_links,
)
from app.models.user import UserRole
from app.schemas.content import ContentItemCreate
from app.services import content_service, project_service
from tests.factories import create_tokens_for_user, create_user


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_project_full_lifecycle_with_inline_content_and_product(
    client, db_session: Session
) -> None:
    editor = create_user(db_session, username="project_editor", role=UserRole.editor)
    token, _ = create_tokens_for_user(db_session, user=editor)

    category_response = client.post(
        "/api/v1/projects/categories",
        json={
            "name": "YouTube Review",
            "color": "#7c5cff",
            "description": "Long-form product review projects",
        },
        headers=_auth(token),
    )
    assert category_response.status_code == 200
    category = category_response.json()

    project_response = client.post(
        "/api/v1/projects",
        json={
            "title": "Creator Camera Review",
            "category_id": category["id"],
            "status": "planning",
            "priority": "high",
            "goal": "Publish a complete camera review",
            "brief_md": "Compare image quality and creator workflow.",
            "requirements_md": "Include sample footage and disclosure.",
            "start_date": "2026-07-20",
            "due_date": "2026-08-10",
            "preview_required": True,
            "preview_due_date": "2026-08-05",
        },
        headers=_auth(token),
    )
    assert project_response.status_code == 200
    project = project_response.json()
    assert project["preview_status"] == "pending"
    assert project["content_count"] == 0
    assert project["product_count"] == 0

    content_response = client.post(
        f"/api/v1/projects/{project['id']}/content",
        json={
            "title": "Camera Review",
            "platform": "youtube",
            "type": "review",
            "status": "idea",
        },
        headers=_auth(token),
    )
    assert content_response.status_code == 200
    project = content_response.json()
    assert project["content_count"] == 1
    assert project["content_items"][0]["title"] == "Camera Review"

    product_response = client.post(
        f"/api/v1/projects/{project['id']}/products",
        json={"title": "Creator Camera", "brand": "Example", "current_value": 1299},
        headers=_auth(token),
    )
    assert product_response.status_code == 200
    project = product_response.json()
    assert project["product_count"] == 1
    assert project["products"][0]["title"] == "Creator Camera"

    content = db_session.query(ContentItem).filter(ContentItem.title == "Camera Review").one()
    product = db_session.query(Product).filter(Product.title == "Creator Camera").one()
    assert [linked.id for linked in content.projects] == [content.projects[0].id]
    assert content.projects[0].id.hex == project["id"].replace("-", "")
    assert product.projects[0].id == content.projects[0].id

    update_response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "status": "active",
            "progress_percent": 40,
            "preview_status": "requested",
        },
        headers=_auth(token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["progress_percent"] == 40
    assert update_response.json()["preview_attention_required"] is True


def test_project_and_category_names_reject_whitespace(client, db_session: Session) -> None:
    editor = create_user(db_session, username="project_blank_name_editor", role=UserRole.editor)
    token, _ = create_tokens_for_user(db_session, user=editor)

    project_response = client.post(
        "/api/v1/projects",
        json={"title": "   "},
        headers=_auth(token),
    )
    category_response = client.post(
        "/api/v1/projects/categories",
        json={"name": "   "},
        headers=_auth(token),
    )

    assert project_response.status_code == 422
    assert category_response.status_code == 422
    assert project_response.json()["code"] == "VALIDATION_ERROR"
    assert category_response.json()["code"] == "VALIDATION_ERROR"


def test_create_linked_content_rolls_back_content_when_link_audit_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    editor = create_user(
        db_session,
        username="project_atomic_content_editor",
        role=UserRole.editor,
    )
    project = Project(title="Atomic content project")
    db_session.add(project)
    db_session.commit()

    def _fail_link_audit(*_args, **_kwargs):
        raise RuntimeError("forced project link audit failure")

    monkeypatch.setattr(project_service, "record_audit_log", _fail_link_audit)

    with pytest.raises(RuntimeError, match="forced project link audit failure"):
        project_service.create_linked_content(
            db_session,
            project_id=project.id,
            payload=ContentItemCreate(title="Must roll back"),
            actor=editor,
        )

    db_session.expire_all()
    assert db_session.query(ContentItem).filter(ContentItem.title == "Must roll back").count() == 0
    persisted_project = db_session.query(Project).filter(Project.id == project.id).one()
    assert persisted_project.content_items == []


def test_content_create_keeps_standalone_commit_default(db_session: Session) -> None:
    editor = create_user(
        db_session,
        username="standalone_content_editor",
        role=UserRole.editor,
    )

    item = content_service.create_item(
        db_session,
        payload=ContentItemCreate(title="Standalone committed content"),
        actor=editor,
    )
    db_session.rollback()

    assert db_session.query(ContentItem).filter(ContentItem.id == item.id).one().title == item.title


def test_project_links_existing_records_and_supports_reciprocal_filters(
    client, db_session: Session
) -> None:
    editor = create_user(db_session, username="project_linker", role=UserRole.editor)
    token, _ = create_tokens_for_user(db_session, user=editor)
    product = Product(title="Existing microphone")
    content = ContentItem(title="Existing audio video")
    db_session.add_all([product, content])
    db_session.commit()

    response = client.post(
        "/api/v1/projects",
        json={
            "title": "Audio setup",
            "product_ids": [str(product.id)],
            "content_item_ids": [str(content.id)],
        },
        headers=_auth(token),
    )
    assert response.status_code == 200
    project_id = response.json()["id"]

    products_response = client.get(
        f"/api/v1/products?project_id={project_id}", headers=_auth(token)
    )
    assert products_response.status_code == 200
    assert [item["id"] for item in products_response.json()["items"]] == [str(product.id)]
    assert products_response.json()["items"][0]["project_ids"] == [project_id]

    content_response = client.get(
        f"/api/v1/content/items?project_id={project_id}", headers=_auth(token)
    )
    assert content_response.status_code == 200
    assert [item["id"] for item in content_response.json()["items"]] == [str(content.id)]
    assert content_response.json()["items"][0]["project_ids"] == [project_id]


def test_viewer_can_read_but_cannot_create_projects(client, db_session: Session) -> None:
    viewer = create_user(db_session, username="project_viewer", role=UserRole.viewer)
    token, _ = create_tokens_for_user(db_session, user=viewer)

    list_response = client.get("/api/v1/projects", headers=_auth(token))
    create_response = client.post(
        "/api/v1/projects", json={"title": "Forbidden"}, headers=_auth(token)
    )

    assert list_response.status_code == 200
    assert create_response.status_code == 403


def test_project_owner_must_exist_and_can_be_cleared(client, db_session: Session) -> None:
    editor = create_user(db_session, username="project_owner_editor", role=UserRole.editor)
    owner = create_user(db_session, username="project_owner", role=UserRole.viewer)
    token, _ = create_tokens_for_user(db_session, user=editor)

    invalid_create = client.post(
        "/api/v1/projects",
        json={
            "title": "Invalid owner",
            "owner_user_id": "00000000-0000-0000-0000-000000000001",
        },
        headers=_auth(token),
    )
    assert invalid_create.status_code == 400

    create_response = client.post(
        "/api/v1/projects",
        json={"title": "Owned project", "owner_user_id": str(owner.id)},
        headers=_auth(token),
    )
    assert create_response.status_code == 200
    project = create_response.json()
    assert project["owner_user_id"] == str(owner.id)

    invalid_update = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"owner_user_id": "00000000-0000-0000-0000-000000000001"},
        headers=_auth(token),
    )
    assert invalid_update.status_code == 400

    clear_response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"owner_user_id": None},
        headers=_auth(token),
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["owner_user_id"] is None


def test_deleting_project_owner_sets_reference_to_null(client, db_session: Session) -> None:
    editor = create_user(db_session, username="project_owner_delete_editor", role=UserRole.editor)
    owner = create_user(db_session, username="project_owner_delete", role=UserRole.viewer)
    token, _ = create_tokens_for_user(db_session, user=editor)
    response = client.post(
        "/api/v1/projects",
        json={"title": "Owner deletion", "owner_user_id": str(owner.id)},
        headers=_auth(token),
    )
    assert response.status_code == 200
    project_id = uuid.UUID(response.json()["id"])

    db_session.delete(owner)
    db_session.commit()
    db_session.expire_all()

    project = db_session.query(Project).filter(Project.id == project_id).one()
    assert project.owner_user_id is None


def test_reciprocal_project_link_columns_are_indexed() -> None:
    content_indexes = {index.name for index in project_content_links.indexes}
    product_indexes = {index.name for index in project_product_links.indexes}

    assert "ix_project_content_links_content_item_id" in content_indexes
    assert "ix_project_product_links_product_id" in product_indexes


def test_project_category_name_has_case_insensitive_unique_index() -> None:
    indexes = {index.name: index for index in ProjectCategory.__table__.indexes}
    name_index = indexes["ix_project_categories_name_ci"]

    assert name_index.unique is True
    assert "lower(" in str(name_index.expressions[0]).lower()
    assert not any(
        isinstance(constraint, UniqueConstraint)
        for constraint in ProjectCategory.__table__.constraints
    )
