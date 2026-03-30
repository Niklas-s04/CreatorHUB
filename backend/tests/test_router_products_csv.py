from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.product import Product, ProductCondition, ProductStatus
from app.models.user import UserRole
from tests.factories import create_tokens_for_user, create_user


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_csv_import_route_requires_privileged_role(client, db_session: Session) -> None:
    viewer = create_user(db_session, username="csv_viewer", role=UserRole.viewer)
    token, _ = create_tokens_for_user(db_session, user=viewer)

    response = client.post(
        "/api/products/import/csv",
        json={
            "csv_text": "title;currency\nPhone;EUR",
            "delimiter": ";",
            "quotechar": '"',
            "column_map": {"title": "title", "currency": "currency"},
            "dry_run": True,
        },
        headers=_auth_header(token),
    )

    assert response.status_code == 403


def test_csv_import_route_accepts_editor(client, db_session: Session) -> None:
    editor = create_user(db_session, username="csv_editor", role=UserRole.editor)
    token, _ = create_tokens_for_user(db_session, user=editor)

    response = client.post(
        "/api/products/import/csv",
        json={
            "csv_text": "title;currency\nPhone;EUR",
            "delimiter": ";",
            "quotechar": '"',
            "column_map": {"title": "title", "currency": "currency"},
            "dry_run": True,
        },
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rows_total"] == 1
    assert body["ready"] == 1
    assert body["inserted"] == 0
    assert body["summary"]["status"] == "success"
    assert body["idempotency"]["mode"] == "skip_existing"
    assert "quality_issues" in body


def test_csv_export_products_respects_filters(client, db_session: Session) -> None:
    editor = create_user(db_session, username="csv_export_editor", role=UserRole.editor)
    token, _ = create_tokens_for_user(db_session, user=editor)

    db_session.add(
        Product(
            title="Canon R6",
            brand="Canon",
            category="camera",
            condition=ProductCondition.good,
            status=ProductStatus.active,
            currency="EUR",
        )
    )
    db_session.add(
        Product(
            title="Nintendo Switch",
            brand="Nintendo",
            category="console",
            condition=ProductCondition.good,
            status=ProductStatus.archived,
            currency="EUR",
        )
    )
    db_session.commit()

    response = client.get(
        "/api/products/export/csv?dataset=products&q=canon&status=active",
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    assert "Canon R6" in response.text
    assert "Nintendo Switch" not in response.text
