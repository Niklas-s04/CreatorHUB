from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.content import ContentItem
from app.models.product import Product
from app.models.user import UserRole
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
