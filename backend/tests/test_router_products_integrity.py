from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.product import Product, ProductStatus, ProductValueHistory
from tests.factories import create_user, login


def _csrf_headers(auth: dict) -> dict[str, str]:
    assert auth["csrf"]
    return {"x-csrf-token": str(auth["csrf"])}


def test_general_product_patch_rejects_status_transitions(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session, username="product_status_admin")
    auth = login(client, username=user.username)
    product = Product(title="Camera", status=ProductStatus.active)
    db_session.add(product)
    db_session.commit()

    response = client.patch(
        f"/api/v1/products/{product.id}",
        json={"status": "archived"},
        headers=_csrf_headers(auth),
    )

    assert response.status_code == 422
    db_session.refresh(product)
    assert product.status == ProductStatus.active


@pytest.mark.parametrize(
    "forbidden_initial_state",
    [
        {"status": "sold"},
        {"status": "archived"},
        {"workflow_status": "approved", "review_reason": "Pre-approved"},
        {"review_reason": "Bypass review workflow"},
    ],
)
def test_product_create_rejects_status_and_workflow_bypasses(
    client: TestClient,
    db_session: Session,
    forbidden_initial_state: dict[str, str],
) -> None:
    user = create_user(
        db_session,
        username=f"product_create_guard_{len(forbidden_initial_state)}_"
        f"{next(iter(forbidden_initial_state))}",
    )
    auth = login(client, username=user.username)

    response = client.post(
        "/api/v1/products",
        json={"title": "Guarded product", **forbidden_initial_state},
        headers=_csrf_headers(auth),
    )

    assert response.status_code == 422
    assert db_session.query(Product).count() == 0


def test_product_create_uses_initial_domain_states(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session, username="product_create_initial_states")
    auth = login(client, username=user.username)

    response = client.post(
        "/api/v1/products",
        json={"title": "Fresh product", "current_value": 123.45, "currency": "USD"},
        headers=_csrf_headers(auth),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert response.json()["workflow_status"] == "draft"
    assert response.json()["review_reason"] is None
    product = db_session.query(Product).filter(Product.title == "Fresh product").one()
    history = (
        db_session.query(ProductValueHistory)
        .filter(ProductValueHistory.product_id == product.id)
        .one()
    )
    assert float(history.value) == 123.45
    assert history.currency == "USD"
    assert history.date == product.created_at.date()


def test_historical_value_entry_does_not_replace_current_value(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session, username="product_value_admin")
    auth = login(client, username=user.username)
    product = Product(
        title="Camera",
        status=ProductStatus.active,
        current_value=100,
        currency="EUR",
    )
    db_session.add(product)
    db_session.commit()

    newest = client.post(
        f"/api/v1/products/{product.id}/value_history",
        json={"date": "2026-07-20", "value": 900, "currency": "EUR", "source": "manual"},
        headers=_csrf_headers(auth),
    )
    older = client.post(
        f"/api/v1/products/{product.id}/value_history",
        json={"date": "2025-01-01", "value": 50, "currency": "USD", "source": "manual"},
        headers=_csrf_headers(auth),
    )

    assert newest.status_code == 200
    assert older.status_code == 200
    db_session.refresh(product)
    assert product.current_value == 900
    assert product.currency == "EUR"
    assert date.fromisoformat(older.json()["date"]) < date.fromisoformat(newest.json()["date"])
