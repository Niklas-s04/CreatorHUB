from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers import email as email_router
from app.models.ai_settings import CreatorAiProfile, CreatorAiTone
from app.models.asset import Asset, AssetKind, AssetOwnerType, AssetReviewState, AssetSource
from app.models.audit import AuditLog
from app.models.content import (
    ContentItem,
    ContentItemRevision,
    ContentStatus,
    ContentTask,
    ContentTaskView,
    ContentType,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from app.models.deal import DealDraft, DealDraftStatus
from app.models.email import (
    EmailApprovalStatus,
    EmailDraft,
    EmailDraftSuggestion,
    EmailDraftVersion,
    EmailHandoffStatus,
    EmailIntent,
    EmailRiskLevel,
    EmailTemplate,
    EmailThread,
    EmailThreadMessage,
    EmailTone,
)
from app.models.knowledge import KnowledgeDoc, KnowledgeDocDraftLink, KnowledgeDocVersion
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
from app.schemas.email import (
    CreatorAiProfileInput,
    EmailDraftApprovalRequest,
    EmailDraftHandoffRequest,
    EmailDraftManualUpdateRequest,
    EmailTemplateCreate,
)
from app.schemas.knowledge import KnowledgeDocCreate, KnowledgeDocUpdate
from app.services import content_service, deal_service, knowledge_service
from app.services.errors import BusinessRuleViolation
from app.services.sales_workflow import finalize_product_sale

TEST_TABLES = [
    User.__table__,
    CreatorAiProfile.__table__,
    Product.__table__,
    Asset.__table__,
    KnowledgeDoc.__table__,
    KnowledgeDocVersion.__table__,
    KnowledgeDocDraftLink.__table__,
    ContentItem.__table__,
    ContentItemRevision.__table__,
    ContentTask.__table__,
    ContentTaskView.__table__,
    EmailThread.__table__,
    EmailThreadMessage.__table__,
    EmailTemplate.__table__,
    EmailDraft.__table__,
    EmailDraftVersion.__table__,
    EmailDraftSuggestion.__table__,
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
    assert doc.current_version == 1
    assert (
        service_db.query(KnowledgeDocVersion)
        .filter(KnowledgeDocVersion.knowledge_doc_id == doc.id)
        .count()
        == 1
    )

    updated = knowledge_service.update_doc(
        service_db,
        doc_id=doc.id,
        payload=KnowledgeDocUpdate(title="Policy v2", source_name="Official handbook"),
        actor=admin,
    )
    assert updated.title == "Policy v2"
    assert updated.current_version == 2
    assert (
        service_db.query(KnowledgeDocVersion)
        .filter(KnowledgeDocVersion.knowledge_doc_id == doc.id)
        .count()
        == 2
    )

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


def test_knowledge_service_requires_outdated_reason(service_db: Session) -> None:
    admin = _create_admin(service_db, username="admin_outdated")
    with pytest.raises(BusinessRuleViolation):
        knowledge_service.create_doc(
            service_db,
            payload=KnowledgeDocCreate(
                type="policy",
                title="Outdated Policy",
                content="Legacy guidance",
                is_outdated=True,
                outdated_reason="   ",
            ),
            actor=admin,
        )


def test_knowledge_service_links_docs_to_draft(service_db: Session) -> None:
    admin = _create_admin(service_db, username="admin_links")
    thread = _create_email_thread(service_db)
    draft = EmailDraft(thread_id=thread.id, tone=EmailTone.neutral, draft_body="Hello")
    service_db.add(draft)
    service_db.commit()
    service_db.refresh(draft)

    doc = knowledge_service.create_doc(
        service_db,
        payload=KnowledgeDocCreate(type="template", title="Template A", content="Hello {{name}}"),
        actor=admin,
    )

    knowledge_service.link_docs_to_draft(
        service_db,
        doc_ids=[doc.id, doc.id],
        email_draft_id=draft.id,
        actor=admin,
    )
    service_db.commit()

    links = (
        service_db.query(KnowledgeDocDraftLink)
        .filter(KnowledgeDocDraftLink.email_draft_id == draft.id)
        .all()
    )
    assert len(links) == 1
    assert links[0].knowledge_doc_id == doc.id
    assert links[0].linked_by_name == admin.username


def test_email_template_create_and_high_risk_approval_rules(service_db: Session) -> None:
    admin = _create_admin(service_db, username="email_admin")
    reviewer = _create_admin(service_db, username="email_reviewer")
    reviewer.role = UserRole.editor
    service_db.add(reviewer)
    service_db.commit()

    thread = _create_email_thread(service_db)
    template = email_router.create_template(
        payload=EmailTemplateCreate(
            name="Sponsor Reply",
            intent=EmailIntent.sponsoring,
            subject_template="AW: Sponsoring Anfrage",
            body_template="Danke fuer die Anfrage.",
            thread_id=thread.id,
        ),
        db=service_db,
        current_user=admin,
    )
    assert template.thread_id == thread.id
    assert template.name == "Sponsor Reply"

    draft = EmailDraft(
        thread_id=thread.id,
        template_id=template.id,
        tone=EmailTone.neutral,
        draft_subject="Antwort",
        draft_body="Wir melden uns.",
        risk_flags='["binding_promise", "contains_links"]',
        risk_score=4,
        risk_level=EmailRiskLevel.high,
        risk_summary="binding_promise, contains_links",
        approval_required=True,
        approval_status=EmailApprovalStatus.pending,
        handoff_status=EmailHandoffStatus.blocked,
    )
    service_db.add(draft)
    service_db.commit()

    with pytest.raises(HTTPException) as forbidden:
        email_router.set_draft_approval(
            draft_id=draft.id,
            payload=EmailDraftApprovalRequest(approved=True, reason="Looks good"),
            db=service_db,
            current_user=reviewer,
        )
    assert forbidden.value.status_code == 403

    with pytest.raises(HTTPException) as missing_reason:
        email_router.set_draft_approval(
            draft_id=draft.id,
            payload=EmailDraftApprovalRequest(approved=True, reason=None),
            db=service_db,
            current_user=admin,
        )
    assert missing_reason.value.status_code == 400

    approved = email_router.set_draft_approval(
        draft_id=draft.id,
        payload=EmailDraftApprovalRequest(approved=True, reason="Legal approved"),
        db=service_db,
        current_user=admin,
    )
    assert approved.approved is True
    assert approved.approval_status == EmailApprovalStatus.approved


def test_email_handoff_requires_ready_state_and_note(service_db: Session) -> None:
    admin = _create_admin(service_db, username="handoff_admin")
    thread = _create_email_thread(service_db)
    draft = EmailDraft(
        thread_id=thread.id,
        tone=EmailTone.neutral,
        draft_subject="AW: Anfrage",
        draft_body="Hier ist der Vorschlag.",
        risk_flags="[]",
        risk_score=0,
        risk_level=EmailRiskLevel.low,
        risk_summary="No relevant risks detected",
        approval_required=False,
        approval_status=EmailApprovalStatus.not_required,
        handoff_status=EmailHandoffStatus.draft,
    )
    service_db.add(draft)
    service_db.commit()

    ready = email_router.set_draft_handoff(
        draft_id=draft.id,
        payload=EmailDraftHandoffRequest(status=EmailHandoffStatus.ready_for_send),
        db=service_db,
        current_user=admin,
    )
    assert ready.handoff_status == EmailHandoffStatus.ready_for_send

    with pytest.raises(HTTPException) as missing_note:
        email_router.set_draft_handoff(
            draft_id=draft.id,
            payload=EmailDraftHandoffRequest(status=EmailHandoffStatus.handed_off),
            db=service_db,
            current_user=admin,
        )
    assert missing_note.value.status_code == 400

    handed_off = email_router.set_draft_handoff(
        draft_id=draft.id,
        payload=EmailDraftHandoffRequest(
            status=EmailHandoffStatus.handed_off,
            note="Sent to account manager for final send",
        ),
        db=service_db,
        current_user=admin,
    )
    assert handed_off.handoff_status == EmailHandoffStatus.handed_off
    assert handed_off.handed_off_by_name == admin.username
    assert handed_off.handed_off_at is not None


def test_ai_draft_requires_human_approval_by_default(
    service_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = _create_admin(service_db, username="hil_admin")

    def _fake_generate(*_args, **_kwargs):
        return {
            "intent": "sponsoring",
            "summary": "summary",
            "risk_flags": ["contains_links"],
            "questions_to_ask": [],
            "draft_subject": "AW",
            "draft_body": "Draft body",
            "knowledge_doc_ids": [],
        }

    monkeypatch.setattr(email_router, "generate_email_draft", _fake_generate)

    draft = email_router.create_draft(
        payload=email_router.EmailDraftRequest(
            subject="Hi",
            raw_body="Need your rates",
            tone=EmailTone.neutral,
        ),
        db=service_db,
        current_user=admin,
    )

    assert draft.approval_required is True
    assert draft.approval_status == EmailApprovalStatus.pending
    assert draft.handoff_status == EmailHandoffStatus.blocked


def test_creator_ai_settings_profile_preview_and_generation(
    service_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = _create_admin(service_db, username="ai_profile_admin")

    default_profile = email_router.upsert_global_default_profile(
        payload=CreatorAiProfileInput(
            profile_name="Global",
            clear_name="Default Klarname",
            artist_name="Default Artist",
            channel_link="https://example.com/default",
            themes=["default theme"],
            platforms=["youtube"],
            short_description="global profile",
            tone=CreatorAiTone.professional,
            target_audience="brands",
            language_code="de",
            content_focus=["sponsoring"],
        ),
        db=service_db,
        current_user=admin,
    )
    assert default_profile.is_global_default is True

    profile = email_router.create_creator_profile(
        payload=CreatorAiProfileInput(
            profile_name="Creator X",
            clear_name="Klara Creator",
            artist_name="CreatorX",
            channel_link="https://example.com/creatorx",
            themes=["beauty", "lifestyle"],
            platforms=["instagram", "youtube"],
            short_description="Focus on short-form video",
            tone=CreatorAiTone.energetic,
            target_audience="Gen Z",
            language_code="de",
            content_focus=["community", "storytelling"],
        ),
        db=service_db,
        current_user=admin,
    )

    preview = email_router.preview_creator_ai_settings(
        profile_id=profile.id,
        db=service_db,
        current_user=admin,
    )
    assert preview["source"] == "selected_profile"
    assert preview["profile_id"] == profile.id
    assert preview["applied_settings"]["artist_name"] == "CreatorX"
    assert "instagram" in preview["applied_settings"]["platforms"]

    def _fake_generate(*_args, **kwargs):
        settings = kwargs.get("creator_settings") or {}
        assert settings.get("artist_name") == "CreatorX"
        assert settings.get("language_code") == "de"
        return {
            "intent": "sponsoring",
            "summary": "summary",
            "risk_flags": ["contains_links"],
            "questions_to_ask": [],
            "draft_subject": "AW",
            "draft_body": "Draft body",
            "knowledge_doc_ids": [],
        }

    monkeypatch.setattr(email_router, "generate_email_draft", _fake_generate)

    draft = email_router.create_draft(
        payload=email_router.EmailDraftRequest(
            subject="Hi",
            raw_body="Need your rates",
            tone=EmailTone.neutral,
            creator_profile_id=profile.id,
        ),
        db=service_db,
        current_user=admin,
    )
    assert draft.thread_id is not None


def test_creator_ai_settings_preview_falls_back_to_global_default(service_db: Session) -> None:
    admin = _create_admin(service_db, username="ai_profile_fallback_admin")

    email_router.upsert_global_default_profile(
        payload=CreatorAiProfileInput(
            profile_name="Global",
            clear_name="Default Klarname",
            artist_name="Default Artist",
            channel_link="https://example.com/default",
            themes=["default theme"],
            platforms=["youtube"],
            short_description="global profile",
            tone=CreatorAiTone.professional,
            target_audience="brands",
            language_code="de",
            content_focus=["sponsoring"],
        ),
        db=service_db,
        current_user=admin,
    )

    preview = email_router.preview_creator_ai_settings(
        profile_id=None,
        db=service_db,
        current_user=admin,
    )
    assert preview["source"] in {"global_default", "user_profile"}
    assert preview["applied_settings"]["artist_name"]


def test_manual_draft_update_creates_new_revision_and_resets_approval(service_db: Session) -> None:
    admin = _create_admin(service_db, username="editor_admin")
    thread = _create_email_thread(service_db)
    draft = EmailDraft(
        thread_id=thread.id,
        tone=EmailTone.neutral,
        draft_subject="AW: Anfrage",
        draft_body="Original text",
        risk_flags="[]",
        risk_score=0,
        risk_level=EmailRiskLevel.low,
        approval_required=True,
        approval_status=EmailApprovalStatus.approved,
        approved=True,
        handoff_status=EmailHandoffStatus.ready_for_send,
    )
    service_db.add(draft)
    service_db.commit()
    email_router._append_draft_version(service_db, draft=draft, actor=admin, reason="Initial")
    service_db.commit()

    updated = email_router.update_draft_content(
        draft_id=draft.id,
        payload=EmailDraftManualUpdateRequest(
            draft_body="Edited text",
            change_reason="Tone adjusted",
        ),
        db=service_db,
        current_user=admin,
    )

    assert updated.draft_body == "Edited text"
    assert updated.approved is False
    assert updated.approval_status == EmailApprovalStatus.pending
    assert updated.handoff_status == EmailHandoffStatus.blocked
    version_count = (
        service_db.query(EmailDraftVersion).filter(EmailDraftVersion.draft_id == draft.id).count()
    )
    assert version_count >= 2


def test_thread_detail_includes_knowledge_evidence(service_db: Session) -> None:
    admin = _create_admin(service_db, username="knowledge_admin")
    thread = _create_email_thread(service_db)
    draft = EmailDraft(thread_id=thread.id, tone=EmailTone.neutral, draft_body="Hello")
    service_db.add(draft)
    service_db.commit()
    service_db.refresh(draft)

    doc = knowledge_service.create_doc(
        service_db,
        payload=KnowledgeDocCreate(type="policy", title="Policy", content="Rules"),
        actor=admin,
    )
    knowledge_service.link_docs_to_draft(
        service_db,
        doc_ids=[doc.id],
        email_draft_id=draft.id,
        actor=admin,
    )
    service_db.commit()

    detail = email_router.get_thread(thread_id=thread.id, db=service_db, _=admin)
    assert len(detail["knowledge_evidence"]) == 1
    assert detail["knowledge_evidence"][0]["knowledge_doc_id"] == doc.id


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


def test_content_service_tracks_item_revisions(service_db: Session) -> None:
    admin = _create_admin(service_db, username="content_revision_admin")
    item = content_service.create_item(
        service_db,
        payload=ContentItemCreate(title="Revision Flow"),
        actor=admin,
    )

    content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(title="Revision Flow v2", last_change_summary="Title update"),
        actor=admin,
    )

    revisions = (
        service_db.query(ContentItemRevision)
        .filter(ContentItemRevision.content_item_id == item.id)
        .order_by(ContentItemRevision.revision_number)
        .all()
    )
    assert len(revisions) >= 2
    assert revisions[-1].change_summary == "Title update"
    assert "title" in revisions[-1].changed_fields


def test_content_publish_requires_approved_workflow_tasks_and_asset(service_db: Session) -> None:
    admin = _create_admin(service_db, username="publish_guard_admin")
    item = content_service.create_item(
        service_db,
        payload=ContentItemCreate(type=ContentType.review, title="Publish Guard"),
        actor=admin,
    )

    item = content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(status=ContentStatus.draft),
        actor=admin,
    )
    item = content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(status=ContentStatus.recorded),
        actor=admin,
    )
    item = content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(status=ContentStatus.edited),
        actor=admin,
    )
    item = content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(
            status=ContentStatus.scheduled,
            planned_date=date.today(),
            publish_date=date.today(),
        ),
        actor=admin,
    )

    with pytest.raises(BusinessRuleViolation, match="approved"):
        content_service.update_item(
            service_db,
            item_id=item.id,
            payload=ContentItemUpdate(status=ContentStatus.published),
            actor=admin,
        )

    content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(
            workflow_status=WorkflowStatus.in_review,
            review_reason="Ready for review",
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

    with pytest.raises(BusinessRuleViolation, match="tasks"):
        content_service.update_item(
            service_db,
            item_id=item.id,
            payload=ContentItemUpdate(status=ContentStatus.published),
            actor=admin,
        )

    for task in service_db.query(ContentTask).filter(ContentTask.content_item_id == item.id).all():
        content_service.update_task(
            service_db,
            task_id=task.id,
            payload=ContentTaskUpdate(status=TaskStatus.done),
            actor=admin,
        )

    with pytest.raises(BusinessRuleViolation, match="approved content asset"):
        content_service.update_item(
            service_db,
            item_id=item.id,
            payload=ContentItemUpdate(status=ContentStatus.published),
            actor=admin,
        )

    approved_asset = Asset(
        owner_type=AssetOwnerType.content,
        owner_id=item.id,
        kind=AssetKind.image,
        source=AssetSource.upload,
        review_state=AssetReviewState.approved,
        local_path="/tmp/content-publish.png",
        workflow_status=WorkflowStatus.approved,
        title="Cover",
    )
    service_db.add(approved_asset)
    service_db.commit()

    published = content_service.update_item(
        service_db,
        item_id=item.id,
        payload=ContentItemUpdate(
            status=ContentStatus.published, primary_asset_id=approved_asset.id
        ),
        actor=admin,
    )
    assert published.status == ContentStatus.published
    assert published.published_at is not None
    assert published.primary_asset_id == approved_asset.id


def test_content_task_dependency_same_item_only(service_db: Session) -> None:
    admin = _create_admin(service_db, username="dependency_admin")
    item_a = content_service.create_item(
        service_db,
        payload=ContentItemCreate(type=ContentType.review, title="Item A"),
        actor=admin,
    )
    item_b = content_service.create_item(
        service_db,
        payload=ContentItemCreate(type=ContentType.review, title="Item B"),
        actor=admin,
    )

    blocker = content_service.create_task(
        service_db,
        payload=ContentTaskCreate(
            content_item_id=item_a.id,
            type=TaskType.script,
        ),
        actor=admin,
    )

    with pytest.raises(BusinessRuleViolation, match="same content item"):
        content_service.create_task(
            service_db,
            payload=ContentTaskCreate(
                content_item_id=item_b.id,
                type=TaskType.edit,
                blocked_by_task_id=blocker.id,
            ),
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
    assert (
        service_db.query(AuditLog).filter(AuditLog.action == "sales.workflow.finalized").count()
        == 1
    )


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
