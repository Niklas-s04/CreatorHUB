from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.models.base import Base
from app.models.user import User, UserRole
from app.schemas.content import (
    ContentChecklistTemplateCreate,
    ContentItemCreate,
    ContentPlatformProfileCreate,
    ContentTemplateApplyRequest,
)
from app.services import content_service
from app.services.errors import BusinessRuleViolation

TEST_TABLES = list(Base.metadata.sorted_tables)


@pytest.fixture()
def service_db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    local_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = local_session()
    try:
        yield session
    finally:
        session.close()
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        engine.dispose()


def _create_admin(db: Session, username: str = "planner_admin") -> User:
    user = User(
        username=username,
        hashed_password="test",
        role=UserRole.admin,
        is_active=True,
        needs_password_setup=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_item_rejects_unknown_platform_meta_fields(service_db: Session) -> None:
    admin = _create_admin(service_db)
    content_service.create_platform_profile(
        service_db,
        payload=ContentPlatformProfileCreate(
            platform="youtube",
            name="YouTube default",
            schema_json={
                "fields": [
                    {"key": "title", "required": True},
                    {"key": "description", "required": False},
                ]
            },
            is_active=True,
        ),
        actor=admin,
    )

    with pytest.raises(BusinessRuleViolation, match="Unknown platform fields"):
        content_service.create_item(
            service_db,
            payload=ContentItemCreate(
                title="Video A",
                platform="youtube",
                type="review",
                platform_meta_json={"unknown_key": "x"},
            ),
            actor=admin,
        )


def test_apply_template_creates_required_tasks_and_planning_blockers(service_db: Session) -> None:
    admin = _create_admin(service_db, username="planner_admin_2")
    item = content_service.create_item(
        service_db,
        payload=ContentItemCreate(
            title="Video B",
            platform="youtube",
            type="review",
            status="draft",
        ),
        actor=admin,
    )

    template = content_service.create_checklist_template(
        service_db,
        payload=ContentChecklistTemplateCreate(
            name="YouTube Publish",
            applies_to_platform="youtube",
            applies_to_type="review",
            is_shared=True,
            items=[
                {
                    "title": "Finalize title",
                    "phase": "post_production",
                    "required": True,
                    "priority_default": "high",
                    "due_offset_days": 0,
                    "can_block_publish": True,
                    "sort_order": 0,
                },
                {
                    "title": "Upload metadata",
                    "phase": "upload",
                    "required": True,
                    "priority_default": "medium",
                    "due_offset_days": 0,
                    "can_block_publish": True,
                    "sort_order": 1,
                },
            ],
        ),
        actor=admin,
    )

    updated_item, created_count, warnings = content_service.apply_checklist_template(
        service_db,
        item_id=item.id,
        payload=ContentTemplateApplyRequest(template_id=template.id, merge_mode="replace"),
        actor=admin,
    )

    assert warnings == []
    assert created_count == 2
    assert updated_item.applied_template_snapshot_id is not None

    planned_item, planned_tasks, blockers, publish_ready = content_service.get_planning_view(
        service_db,
        item_id=item.id,
    )
    assert len(planned_tasks) == 2
    assert any(task.required_for_publish for task in planned_tasks)
    assert planned_item.readiness_score < 100
    assert publish_ready is False
    assert any("Required checklist tasks" in blocker for blocker in blockers)
