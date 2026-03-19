from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.audit import AuditLog
from app.models.content import ContentItem, ContentStatus, ContentTask, ContentType
from app.models.deal import DealDraft
from app.models.email import EmailThread
from app.models.knowledge import KnowledgeDoc
from app.models.user import User, UserRole
from app.schemas.content import ContentItemCreate, ContentItemUpdate, ContentTaskUpdate
from app.schemas.deal import DealDraftIntakeRequest, DealDraftUpdate
from app.schemas.knowledge import KnowledgeDocCreate, KnowledgeDocUpdate
from app.services import content_service, deal_service, knowledge_service
from app.services.errors import BusinessRuleViolation

TEST_TABLES = [
    User.__table__,
    KnowledgeDoc.__table__,
    ContentItem.__table__,
    ContentTask.__table__,
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
