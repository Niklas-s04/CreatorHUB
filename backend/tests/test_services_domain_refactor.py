from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.asset import Asset, AssetKind, AssetOwnerType, AssetReviewState, AssetSource
from app.models.audit import AuditLog
from app.models.content import (
    ContentItem,
    ContentStatus,
    ContentTask,
    ContentTaskView,
    ContentType,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from app.models.deal import DealDraft, DealDraftStatus
from app.models.email import EmailThread
from app.models.knowledge import KnowledgeDoc
from app.models.product import Product
from app.models.user import User, UserRole
from app.models.workflow import WorkflowStatus
from app.schemas.content import (
    ContentItemCreate,
    ContentItemUpdate,
    ContentTaskCreate,
    ContentTaskFilterParams,
    ContentTaskUpdate,
    ContentTaskViewCreate,
)
from app.schemas.deal import DealDraftIntakeRequest, DealDraftUpdate
from app.schemas.knowledge import KnowledgeDocCreate, KnowledgeDocUpdate
from app.services import content_service, deal_service, knowledge_service
from app.services.errors import BusinessRuleViolation
from app.services.sales_workflow import finalize_product_sale

TEST_TABLES = [
    User.__table__,
    Product.__table__,
    Asset.__table__,
    KnowledgeDoc.__table__,
    ContentItem.__table__,
    ContentTask.__table__,
    ContentTaskView.__table__,
    EmailThread.__table__,
    DealDraft.__table__,
    AuditLog.__table__,
]


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


def _create_admin(db: Session, username: str = "admin") -> User:
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


def _create_email_thread(db: Session) -> EmailThread:
    thread = EmailThread(subject="Sponsoring", raw_body="Budget 2500 EUR, 1 reel")
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def test_knowledge_service_crud_and_audit(service_db: Session) -> None:
    admin = _create_admin(service_db)

    doc = knowledge_service.create_doc(
        service_db,
        payload=KnowledgeDocCreate(type="policy", title=" Policy ", content=" Keep data safe "),
        actor=admin,
    )
    assert doc.title == "Policy"
    assert doc.content == "Keep data safe"

    updated = knowledge_service.update_doc(
        service_db,
        doc_id=doc.id,
        payload=KnowledgeDocUpdate(title="Policy v2"),
        actor=admin,
    )
    assert updated.title == "Policy v2"

    knowledge_service.delete_doc(service_db, doc_id=doc.id, actor=admin)
    assert service_db.query(KnowledgeDoc).count() == 0

    actions = [log.action for log in service_db.query(AuditLog).order_by(AuditLog.created_at).all()]
    assert actions == [
        "settings.knowledge.create",
        "settings.knowledge.update",
        "settings.knowledge.delete",
    ]


def test_knowledge_service_rejects_blank_title(service_db: Session) -> None:
    admin = _create_admin(service_db, username="admin2")
    with pytest.raises(BusinessRuleViolation):
        knowledge_service.create_doc(
            service_db,
            payload=KnowledgeDocCreate(type="template", title="   ", content="Valid"),
            actor=admin,
        )


def test_content_service_creates_default_tasks_and_audit(service_db: Session) -> None:
    admin = _create_admin(service_db, username="admin3")

    item = content_service.create_item(
        service_db,
        payload=ContentItemCreate(type=ContentType.review, title="Video A"),
        actor=admin,
    )
    assert item.title == "Video A"

    task_count = (
        service_db.query(ContentTask).filter(ContentTask.content_item_id == item.id).count()
    )
    assert task_count > 0

    first_task = (
        service_db.query(ContentTask)
        .filter(ContentTask.content_item_id == item.id)
        .order_by(ContentTask.created_at)
        .first()
    )
    assert first_task is not None
    content_service.update_task(
        service_db,
        task_id=first_task.id,
        payload=ContentTaskUpdate(notes="done soon"),
        actor=admin,
    )

    assert service_db.query(AuditLog).filter(AuditLog.action == "content.item.create").count() == 1
    assert service_db.query(AuditLog).filter(AuditLog.action == "content.task.update").count() == 1


def test_content_service_rejects_invalid_status_transition(service_db: Session) -> None:
    admin = _create_admin(service_db, username="admin5")
    item = content_service.create_item(
        service_db,
        payload=ContentItemCreate(title="Video B"),
        actor=admin,
    )

    with pytest.raises(BusinessRuleViolation):
        content_service.update_item(
            service_db,
            item_id=item.id,
            payload=ContentItemUpdate(status=ContentStatus.published),
            actor=admin,
        )


def test_content_service_enforces_re_review_after_relevant_change(service_db: Session) -> None:
    admin = _create_admin(service_db, username="admin_review")
    item = content_service.create_item(
        service_db,
        payload=ContentItemCreate(title="Video Workflow"),
        actor=admin,
    )

    approved = content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(
            workflow_status=WorkflowStatus.in_review,
            review_reason="Ready for editorial review",
        ),
        actor=admin,
    )
    assert approved.workflow_status == WorkflowStatus.in_review

    approved = content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(
            workflow_status=WorkflowStatus.approved,
            review_reason="Editorially approved",
        ),
        actor=admin,
    )
    assert approved.workflow_status == WorkflowStatus.approved

    changed = content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(title="Video Workflow v2"),
        actor=admin,
    )
    assert changed.workflow_status == WorkflowStatus.in_review
    assert changed.review_reason is not None
    assert "changes" in changed.review_reason.lower()


def test_deal_service_upsert_and_update(
    monkeypatch: pytest.MonkeyPatch, service_db: Session
) -> None:
    admin = _create_admin(service_db, username="admin4")
    thread = _create_email_thread(service_db)

    def _fake_extract(*_args, **_kwargs) -> dict[str, str | None]:
        return {
            "brand_name": "BrandX",
            "contact_name": "Alex",
            "contact_email": "alex@example.com",
            "budget": "2500 EUR",
            "deliverables": "1 reel",
            "usage_rights": "organic",
            "deadlines": "next week",
            "notes": "initial",
        }

    monkeypatch.setattr(deal_service, "extract_deal_intake", _fake_extract)

    created = deal_service.create_or_update_from_email(
        service_db,
        payload=DealDraftIntakeRequest(thread_id=thread.id, auto_extract=True),
        actor=admin,
    )
    assert created.brand_name == "BrandX"

    updated = deal_service.update_deal_draft(
        service_db,
        deal_id=created.id,
        payload=DealDraftUpdate(notes="updated notes"),
        actor=admin,
    )
    assert updated.notes == "updated notes"

    assert service_db.query(DealDraft).count() == 1
    assert service_db.query(AuditLog).filter(AuditLog.action == "deals.draft.create").count() == 1
    assert service_db.query(AuditLog).filter(AuditLog.action == "deals.draft.update").count() == 1


def test_deal_service_blocks_negotiating_when_required_checklist_open(
    monkeypatch: pytest.MonkeyPatch, service_db: Session
) -> None:
    admin = _create_admin(service_db, username="admin_deal_check")
    thread = _create_email_thread(service_db)

    def _fake_extract(*_args, **_kwargs) -> dict[str, str | None]:
        return {
            "brand_name": "BrandY",
            "contact_name": "Jordan",
            "contact_email": "jordan@example.com",
            "budget": "1200 EUR",
            "deliverables": "1 post",
            "usage_rights": "organic",
            "deadlines": "soon",
            "notes": "intake",
        }

    monkeypatch.setattr(deal_service, "extract_deal_intake", _fake_extract)

    draft = deal_service.create_or_update_from_email(
        service_db,
        payload=DealDraftIntakeRequest(thread_id=thread.id, auto_extract=True),
        actor=admin,
    )

    with pytest.raises(BusinessRuleViolation, match="required checklist items missing"):
        deal_service.update_deal_draft(
            service_db,
            deal_id=draft.id,
            payload=DealDraftUpdate(status=DealDraftStatus.negotiating),
            actor=admin,
        )


def test_sales_finalize_archives_linked_entities(service_db: Session) -> None:
    admin = _create_admin(service_db, username="admin_sales")
    product = Product(title="Phone", status="active")
    service_db.add(product)
    service_db.commit()
    service_db.refresh(product)

    deal = DealDraft(product_id=product.id, status=DealDraftStatus.review)
    content = ContentItem(product_id=product.id, title="Review", status=ContentStatus.draft)
    asset = Asset(
        owner_type=AssetOwnerType.product,
        owner_id=product.id,
        kind=AssetKind.image,
        source=AssetSource.upload,
        review_state=AssetReviewState.approved,
        local_path="/tmp/a.png",
        workflow_status=WorkflowStatus.approved,
    )
    service_db.add_all([deal, content, asset])
    service_db.commit()

    finalize_product_sale(
        service_db,
        product=product,
        sold_date=content.created_at.date(),
        actor=admin,
        reason="Sold and closed",
    )
    service_db.commit()

    service_db.refresh(deal)
    service_db.refresh(content)
    service_db.refresh(asset)

    assert deal.status == DealDraftStatus.won
    assert deal.workflow_status == WorkflowStatus.archived
    assert content.workflow_status == WorkflowStatus.archived
    assert asset.workflow_status == WorkflowStatus.archived
    assert service_db.query(AuditLog).filter(AuditLog.action == "sales.workflow.finalized").count() == 1


def test_content_task_assignment_and_personal_worklist(service_db: Session) -> None:
    admin = _create_admin(service_db, username="owner_admin")
    editor = _create_admin(service_db, username="worker_editor")
    editor.role = UserRole.editor
    service_db.add(editor)
    service_db.commit()

    item = content_service.create_item(
        service_db,
        payload=ContentItemCreate(type=ContentType.review, title="Personal Task Flow"),
        actor=admin,
    )

    task = content_service.create_task(
        service_db,
        payload=ContentTaskCreate(
            content_item_id=item.id,
            type=TaskType.script,
            status=TaskStatus.todo,
            priority=TaskPriority.high,
            assignee_user_id=editor.id,
            due_date=date.today(),
        ),
        actor=admin,
    )

    assert task.priority == TaskPriority.high
    assert task.assignee_user_id == editor.id
    assert task.notified_at is not None

    personal = content_service.list_personal_tasks(
        service_db,
        user=editor,
        filters=ContentTaskFilterParams(priority=TaskPriority.high),
    )
    assert any(entry.id == task.id for entry in personal)


def test_content_task_saved_views(service_db: Session) -> None:
    admin = _create_admin(service_db, username="view_owner")

    created_view = content_service.create_task_view(
        service_db,
        user=admin,
        payload=ContentTaskViewCreate(
            name="Meine High Priority",
            filters={"priority": "high", "overdue_only": True},
        ),
    )
    assert created_view.name == "Meine High Priority"
    assert created_view.filters.get("priority") == "high"

    listed = content_service.list_task_views(service_db, user=admin)
    assert any(entry.id == created_view.id for entry in listed)

    content_service.delete_task_view(service_db, view_id=created_view.id, user=admin)
    listed_after = content_service.list_task_views(service_db, user=admin)
    assert all(entry.id != created_view.id for entry in listed_after)
