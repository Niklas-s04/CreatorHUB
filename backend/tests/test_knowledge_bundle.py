from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.knowledge import (
    KnowledgeDoc,
    KnowledgeDocType,
    KnowledgeSourceReviewStatus,
    KnowledgeSourceType,
    KnowledgeTrustLevel,
)
from app.models.workflow import WorkflowStatus
from app.seed import (
    DEFAULT_BRAND_VOICE,
    DEFAULT_POLICY,
    SYSTEM_DEFAULT_SOURCE_NAME,
    ensure_default_knowledge_docs,
)
from app.services.knowledge_service import (
    get_knowledge_bundle,
    get_knowledge_bundle_with_doc_ids,
)


def _knowledge_doc(
    *,
    title: str,
    doc_type: KnowledgeDocType = KnowledgeDocType.policy,
    workflow_status: WorkflowStatus = WorkflowStatus.approved,
    source_review_status: KnowledgeSourceReviewStatus = KnowledgeSourceReviewStatus.approved,
    is_outdated: bool = False,
) -> KnowledgeDoc:
    return KnowledgeDoc(
        id=uuid.uuid4(),
        type=doc_type,
        title=title,
        content=f"{title} content",
        workflow_status=workflow_status,
        source_review_status=source_review_status,
        is_outdated=is_outdated,
        current_version=1,
    )


def test_knowledge_bundle_only_uses_approved_current_prompt_content(
    db_session: Session,
) -> None:
    approved = _knowledge_doc(title="Approved policy")
    published = _knowledge_doc(
        title="Published template",
        doc_type=KnowledgeDocType.template,
        workflow_status=WorkflowStatus.published,
    )
    draft = _knowledge_doc(title="Draft policy", workflow_status=WorkflowStatus.draft)
    rejected_source = _knowledge_doc(
        title="Rejected source",
        source_review_status=KnowledgeSourceReviewStatus.rejected,
    )
    pending_source = _knowledge_doc(
        title="Pending source",
        source_review_status=KnowledgeSourceReviewStatus.pending,
    )
    outdated = _knowledge_doc(title="Outdated policy", is_outdated=True)
    rate_card = _knowledge_doc(title="Rate card", doc_type=KnowledgeDocType.rate_card)
    db_session.add_all(
        [approved, published, draft, rejected_source, pending_source, outdated, rate_card]
    )
    db_session.commit()

    bundle, evidence_ids = get_knowledge_bundle_with_doc_ids(db_session)
    bundle_without_ids = get_knowledge_bundle(db_session)

    assert "Approved policy content" in bundle["policy"]
    assert "Published template content" in bundle["templates"]
    assert bundle_without_ids == bundle
    excluded_titles = {
        "Draft policy",
        "Rejected source",
        "Pending source",
        "Outdated policy",
        "Rate card",
    }
    assert all(title not in "\n".join(bundle.values()) for title in excluded_titles)
    assert set(evidence_ids) == {approved.id, published.id}


def test_fresh_system_defaults_are_trusted_and_prompt_ready(db_session: Session) -> None:
    ensure_default_knowledge_docs(db_session)
    db_session.commit()

    docs = db_session.query(KnowledgeDoc).order_by(KnowledgeDoc.type).all()
    assert len(docs) == 2
    assert {doc.type for doc in docs} == {
        KnowledgeDocType.brand_voice,
        KnowledgeDocType.policy,
    }
    for doc in docs:
        assert doc.workflow_status == WorkflowStatus.published
        assert doc.source_review_status == KnowledgeSourceReviewStatus.approved
        assert doc.source_type == KnowledgeSourceType.internal
        assert doc.trust_level == KnowledgeTrustLevel.verified
        assert doc.source_name == SYSTEM_DEFAULT_SOURCE_NAME
        assert doc.reviewed_at is not None

    bundle, evidence_ids = get_knowledge_bundle_with_doc_ids(db_session)
    assert DEFAULT_BRAND_VOICE in bundle["brand_voice"]
    assert DEFAULT_POLICY in bundle["policy"]
    assert set(evidence_ids) == {doc.id for doc in docs}

    original_ids = {doc.id for doc in docs}
    ensure_default_knowledge_docs(db_session)
    db_session.commit()
    assert {doc.id for doc in db_session.query(KnowledgeDoc).all()} == original_ids


def test_untouched_legacy_system_default_is_safely_promoted(db_session: Session) -> None:
    legacy = KnowledgeDoc(
        type=KnowledgeDocType.brand_voice,
        title="Default Brand Voice",
        content=DEFAULT_BRAND_VOICE,
    )
    db_session.add(legacy)
    db_session.commit()

    assert legacy.workflow_status == WorkflowStatus.draft
    assert legacy.source_review_status == KnowledgeSourceReviewStatus.pending

    ensure_default_knowledge_docs(db_session)
    db_session.commit()
    db_session.refresh(legacy)

    assert legacy.workflow_status == WorkflowStatus.published
    assert legacy.source_review_status == KnowledgeSourceReviewStatus.approved
    assert legacy.trust_level == KnowledgeTrustLevel.verified
    assert legacy.source_name == SYSTEM_DEFAULT_SOURCE_NAME


def test_customized_or_reviewed_legacy_docs_are_not_promoted(db_session: Session) -> None:
    deliberately_rejected = KnowledgeDoc(
        type=KnowledgeDocType.brand_voice,
        title="Default Brand Voice",
        content=DEFAULT_BRAND_VOICE,
        source_review_status=KnowledgeSourceReviewStatus.rejected,
    )
    customized = KnowledgeDoc(
        type=KnowledgeDocType.policy,
        title="Default Policy",
        content=f"{DEFAULT_POLICY}\n- Team-specific addition",
    )
    db_session.add_all([deliberately_rejected, customized])
    db_session.commit()

    ensure_default_knowledge_docs(db_session)
    db_session.commit()
    db_session.refresh(deliberately_rejected)
    db_session.refresh(customized)

    assert deliberately_rejected.workflow_status == WorkflowStatus.draft
    assert deliberately_rejected.source_review_status == KnowledgeSourceReviewStatus.rejected
    assert deliberately_rejected.trust_level == KnowledgeTrustLevel.medium
    assert deliberately_rejected.source_name is None
    assert customized.workflow_status == WorkflowStatus.draft
    assert customized.source_review_status == KnowledgeSourceReviewStatus.pending
    assert customized.trust_level == KnowledgeTrustLevel.medium
    assert customized.source_name is None
    assert db_session.query(KnowledgeDoc).count() == 2
