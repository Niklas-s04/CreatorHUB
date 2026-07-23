from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.models.asset import Asset, AssetKind, AssetOwnerType, AssetReviewState, AssetSource
from app.models.base import Base
from app.models.content import (
    ContentChecklistTemplate,
    ContentPlatformProfile,
    ContentTask,
    TaskStatus,
)
from app.models.user import User, UserRole
from app.models.workflow import WorkflowStatus
from app.schemas.content import (
    ContentChecklistTemplateCreate,
    ContentItemCreate,
    ContentItemUpdate,
    ContentPlatformProfileCreate,
    ContentTaskUpdate,
    ContentTemplateApplyRequest,
)
from app.services import content_defaults, content_service
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


def test_content_defaults_are_seeded_idempotently(service_db: Session) -> None:
    content_defaults.ensure_content_defaults(service_db)
    service_db.commit()
    content_defaults.ensure_content_defaults(service_db)
    service_db.commit()

    profiles = service_db.query(ContentPlatformProfile).all()
    templates = service_db.query(ContentChecklistTemplate).all()

    assert {profile.platform.value for profile in profiles} >= {
        "youtube",
        "instagram",
        "tiktok",
    }
    assert service_db.query(ContentPlatformProfile).count() == 3
    assert {template.name for template in templates} >= {
        "YouTube Review",
        "Short/Reel/TikTok",
        "Unboxing Video",
    }
    assert service_db.query(ContentChecklistTemplate).count() == 3
    assert all(template.items for template in templates)


def test_planning_view_reports_missing_required_base_and_platform_fields(
    service_db: Session,
) -> None:
    admin = _create_admin(service_db, username="planner_admin_base_fields")
    content_service.create_platform_profile(
        service_db,
        payload=ContentPlatformProfileCreate(
            platform="youtube",
            name="YouTube planning fields",
            schema_json={
                "required_base_fields": ["title", "publish_date", "description_md", "tags_csv"],
                "fields": [
                    {"key": "category", "required": True},
                    {"key": "visibility", "required": True},
                ],
            },
            is_active=True,
        ),
        actor=admin,
    )
    item = content_service.create_item(
        service_db,
        payload=ContentItemCreate(title="Video C", platform="youtube", type="review"),
        actor=admin,
    )

    planned_item, _, blockers, publish_ready = content_service.get_planning_view(
        service_db,
        item_id=item.id,
    )

    assert publish_ready is False
    assert planned_item.readiness_score < 100
    assert any("Missing required content fields" in blocker for blocker in blockers)
    assert any("publish_date" in blocker for blocker in blockers)
    assert any("Missing required platform fields" in blocker for blocker in blockers)
    assert any("category" in blocker for blocker in blockers)


def test_publish_guard_blocks_missing_required_fields_after_tasks_and_asset(
    service_db: Session,
) -> None:
    admin = _create_admin(service_db, username="planner_admin_publish_fields")
    content_service.create_platform_profile(
        service_db,
        payload=ContentPlatformProfileCreate(
            platform="youtube",
            name="YouTube publish fields",
            schema_json={
                "required_base_fields": ["description_md", "tags_csv"],
                "fields": [{"key": "category", "required": True}],
            },
            is_active=True,
        ),
        actor=admin,
    )
    item = content_service.create_item(
        service_db,
        payload=ContentItemCreate(
            title="Video D",
            platform="youtube",
            type="review",
            status="scheduled",
            planned_date=date.today(),
            publish_date=date.today(),
        ),
        actor=admin,
    )
    content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(
            workflow_status=WorkflowStatus.in_review,
            review_reason="Ready",
        ),
        actor=admin,
    )
    content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(
            workflow_status=WorkflowStatus.approved,
            review_reason="Approved",
        ),
        actor=admin,
    )
    for task in service_db.query(ContentTask).filter(ContentTask.content_item_id == item.id).all():
        content_service.update_task(
            service_db,
            task_id=task.id,
            payload=ContentTaskUpdate(status=TaskStatus.done),
            actor=admin,
        )

    approved_asset = Asset(
        owner_type=AssetOwnerType.content,
        owner_id=item.id,
        kind=AssetKind.image,
        source=AssetSource.upload,
        review_state=AssetReviewState.approved,
        local_path="/tmp/content-planning-publish.png",
        workflow_status=WorkflowStatus.approved,
        title="Cover",
    )
    service_db.add(approved_asset)
    service_db.commit()

    with pytest.raises(BusinessRuleViolation, match="Missing required content fields"):
        content_service.update_item(
            service_db,
            item_id=item.id,
            payload=ContentItemUpdate(
                status="published",
                primary_asset_id=approved_asset.id,
            ),
            actor=admin,
        )

    content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(
            description_md="Ready description",
            tags_csv="review, creatorhub",
            platform_meta_json={"category": "Review"},
        ),
        actor=admin,
    )
    content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(
            workflow_status=WorkflowStatus.approved,
            review_reason="Approved after metadata",
        ),
        actor=admin,
    )
    published = content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(
            status="published",
            primary_asset_id=approved_asset.id,
        ),
        actor=admin,
    )

    assert published.status.value == "published"


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


def test_task_updates_and_deletes_recompute_readiness_after_flush(service_db: Session) -> None:
    admin = _create_admin(service_db, username="planner_readiness")
    item = content_service.create_item(
        service_db,
        payload=ContentItemCreate(title="Readiness", platform="youtube", type="review"),
        actor=admin,
    )
    service_db.query(ContentTask).filter(ContentTask.content_item_id == item.id).delete()
    blocking_task = ContentTask(
        content_item_id=item.id,
        title="Blocking task",
        status=TaskStatus.todo,
        required_for_publish=True,
        can_block_publish=True,
    )
    service_db.add(blocking_task)
    service_db.commit()
    content_service.refresh_item_readiness(service_db, item_id=item.id)
    service_db.commit()
    service_db.refresh(item)
    blocked_score = item.readiness_score

    content_service.update_task(
        service_db,
        task_id=blocking_task.id,
        payload=ContentTaskUpdate(status=TaskStatus.done),
        actor=admin,
    )
    service_db.refresh(item)
    assert item.readiness_score > blocked_score

    content_service.update_task(
        service_db,
        task_id=blocking_task.id,
        payload=ContentTaskUpdate(status=TaskStatus.todo),
        actor=admin,
    )
    service_db.refresh(item)
    assert item.readiness_score == blocked_score

    content_service.delete_task(
        service_db,
        task_id=blocking_task.id,
        actor=admin,
    )
    service_db.refresh(item)
    assert item.readiness_score > blocked_score


def test_optional_open_task_does_not_disagree_with_publish_guard(service_db: Session) -> None:
    admin = _create_admin(service_db, username="planner_optional_task")
    item = content_service.create_item(
        service_db,
        payload=ContentItemCreate(title="Optional task", platform="youtube", type="review"),
        actor=admin,
    )
    service_db.query(ContentTask).filter(ContentTask.content_item_id == item.id).delete()
    item.workflow_status = WorkflowStatus.approved
    service_db.add(
        ContentTask(
            content_item_id=item.id,
            title="Optional follow-up",
            status=TaskStatus.todo,
            required_for_publish=False,
            can_block_publish=False,
        )
    )
    service_db.add(
        Asset(
            owner_type=AssetOwnerType.content,
            owner_id=item.id,
            kind=AssetKind.image,
            source=AssetSource.upload,
            review_state=AssetReviewState.approved,
            local_path="/tmp/optional-task.png",
            workflow_status=WorkflowStatus.approved,
        )
    )
    service_db.commit()

    _, _, blockers, publish_ready = content_service.get_planning_view(
        service_db,
        item_id=item.id,
    )

    assert publish_ready is True
    assert blockers == []
    content_service._ensure_publish_ready(item, service_db)
