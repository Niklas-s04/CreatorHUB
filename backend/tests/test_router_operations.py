from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.asset import (
    Asset,
    AssetKind,
    AssetOwnerType,
    AssetReviewState,
    AssetSource,
)
from app.models.deal import DealDraft, DealDraftStatus
from app.models.product import Product
from tests.factories import create_user, login


def _pending_asset(db: Session, *, title: str, created_at: datetime) -> Asset:
    asset = Asset(
        owner_type=AssetOwnerType.product,
        owner_id=uuid.uuid4(),
        kind=AssetKind.image,
        source=AssetSource.upload,
        title=title,
        review_state=AssetReviewState.pending_review,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def test_operations_inbox_filters_before_global_pagination(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session, username="operations_admin")
    login(client, username=user.username)

    now = datetime.now(timezone.utc)
    ignored = _pending_asset(
        db_session,
        title="Microphone",
        created_at=now - timedelta(hours=3),
    )
    first = _pending_asset(
        db_session,
        title="Camera Alpha",
        created_at=now - timedelta(hours=2),
    )
    second = _pending_asset(
        db_session,
        title="Camera Beta",
        created_at=now - timedelta(hours=1),
    )

    response = client.get(
        "/api/v1/operations/inbox",
        params={"q": "camera", "limit": 1, "offset": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_open"] == 2
    assert [item["source_id"] for item in payload["items"]] == [str(second.id)]
    assert str(ignored.id) not in {item["source_id"] for item in payload["items"]}
    assert str(first.id) not in {item["source_id"] for item in payload["items"]}


def test_operations_deal_links_use_an_existing_frontend_route(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session, username="operations_route_admin")
    login(client, username=user.username)
    deal = DealDraft(
        brand_name="Example Brand",
        status=DealDraftStatus.review,
        checklist=[
            {
                "key": "budget_clarified",
                "label": "Budget clarified",
                "required": True,
                "done": False,
            }
        ],
    )
    db_session.add(deal)
    db_session.commit()

    response = client.get("/api/v1/operations/inbox", params={"limit": 10})

    assert response.status_code == 200
    item = next(entry for entry in response.json()["items"] if entry["source_id"] == str(deal.id))
    assert item["kind"] == "deal_checklist"
    assert item["source_route"] == "/email"


def test_operations_inbox_supports_deep_global_offsets(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session, username="operations_offset_admin")
    login(client, username=user.username)

    base_time = datetime.now(timezone.utc) - timedelta(hours=2)
    assets = [
        Asset(
            owner_type=AssetOwnerType.product,
            owner_id=uuid.uuid4(),
            kind=AssetKind.image,
            source=AssetSource.upload,
            title=f"Paged Camera {index:03d}",
            review_state=AssetReviewState.pending_review,
            created_at=base_time + timedelta(seconds=index),
            updated_at=base_time + timedelta(seconds=index),
        )
        for index in range(130)
    ]
    db_session.add_all(assets)
    db_session.commit()

    response = client.get(
        "/api/v1/operations/inbox",
        params={"q": "paged camera", "limit": 5, "offset": 120},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_open"] == 130
    assert [item["source_id"] for item in payload["items"]] == [
        str(asset.id) for asset in assets[120:125]
    ]


def test_operations_product_query_count_does_not_scale_per_product(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session, username="operations_query_admin")
    login(client, username=user.username)
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            Product(
                title=f"Query Scale Product {index:03d}",
                created_at=now + timedelta(seconds=index),
                updated_at=now + timedelta(seconds=index),
            )
            for index in range(150)
        ]
    )
    db_session.commit()

    select_count = 0

    def _capture_select(*args: object) -> None:
        nonlocal select_count
        statement = str(args[2]).lstrip().upper()
        if statement.startswith("SELECT"):
            select_count += 1

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", _capture_select)
    try:
        response = client.get(
            "/api/v1/operations/inbox",
            params={"q": "query scale product", "limit": 10},
        )
    finally:
        event.remove(engine, "before_cursor_execute", _capture_select)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_open"] == 150
    assert len(payload["items"]) == 10
    assert select_count <= 20
