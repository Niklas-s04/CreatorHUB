from __future__ import annotations

from collections.abc import Generator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.api.routers import search
from app.core.web_security import CsrfProtectionMiddleware
from app.models.asset import Asset, AssetKind, AssetOwnerType, AssetReviewState, AssetSource
from app.models.content import ContentItem, ContentPlatform, ContentStatus, ContentType
from app.models.knowledge import KnowledgeDoc, KnowledgeDocType
from app.models.product import Product, ProductCondition, ProductStatus
from app.models.user import User, UserRole
from tests.factories import create_user

TEST_TABLES = [
    User.__table__,
    Product.__table__,
    Asset.__table__,
    ContentItem.__table__,
    KnowledgeDoc.__table__,
]


def _test_app(db_session: Session, current_user: User) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CsrfProtectionMiddleware,
        auth_cookie_name="creatorhub_access",
        csrf_cookie_name="creatorhub_csrf",
    )
    app.include_router(search.router, prefix="/api/search")

    def _get_db_override() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[deps.get_db] = _get_db_override
    app.dependency_overrides[deps.get_current_user] = lambda: current_user
    return app


def _seed_search_entities(db: Session) -> None:
    primary_product = Product(
        title="Canon R6",
        brand="Canon",
        model="R6",
        category="camera",
        condition=ProductCondition.very_good,
        status=ProductStatus.active,
    )
    secondary_product = Product(
        title="Mirrorless Body",
        brand="Canon",
        model="M50",
        category="camera",
        condition=ProductCondition.good,
        status=ProductStatus.active,
    )
    db.add(primary_product)
    db.add(secondary_product)
    db.flush()

    db.add(
        Asset(
            owner_type=AssetOwnerType.product,
            owner_id=primary_product.id,
            kind=AssetKind.image,
            source=AssetSource.web,
            title="Canon Produktfoto",
            review_state=AssetReviewState.approved,
            source_name="Unsplash",
        )
    )
    db.add(
        ContentItem(
            product_id=primary_product.id,
            platform=ContentPlatform.youtube,
            type=ContentType.review,
            status=ContentStatus.draft,
            title="Canon Review Script",
            hook="Canon low-light Test",
        )
    )
    db.add(
        KnowledgeDoc(
            type=KnowledgeDocType.policy,
            title="Canon Koop-Policy",
            content="Regeln für Canon Sponsorings",
        )
    )
    db.commit()


def test_global_search_returns_grouped_results_and_ranking() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = testing_session()

    try:
        admin = create_user(db, username="canon_admin", role=UserRole.admin)
        _seed_search_entities(db)

        app = _test_app(db, admin)
        with TestClient(app) as client:
            response = client.get("/api/search/?q=canon&per_type=5")

        assert response.status_code == 200
        payload = response.json()
        groups = {group["type"]: group for group in payload["groups"]}

        assert {"product", "asset", "content", "knowledge", "user"}.issubset(set(groups.keys()))
        assert groups["product"]["hits"][0]["title"] == "Canon R6"
        assert groups["product"]["hits"][0]["score"] > groups["product"]["hits"][1]["score"]
    finally:
        db.close()
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        engine.dispose()


def test_global_search_hides_user_group_without_user_read_permission() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = testing_session()

    try:
        viewer = create_user(db, username="canon_viewer", role=UserRole.viewer)
        create_user(db, username="canon_target_user", role=UserRole.editor)
        _seed_search_entities(db)

        app = _test_app(db, viewer)
        with TestClient(app) as client:
            response = client.get("/api/search/?q=canon&per_type=5")

        assert response.status_code == 200
        payload = response.json()
        group_types = {group["type"] for group in payload["groups"]}

        assert "user" not in group_types
        assert {"product", "asset", "content", "knowledge"}.issubset(group_types)
    finally:
        db.close()
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        engine.dispose()
