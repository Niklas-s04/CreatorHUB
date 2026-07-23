from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.base import utcnow
from app.models.knowledge import (
    KnowledgeDoc,
    KnowledgeDocType,
    KnowledgeSourceReviewStatus,
    KnowledgeSourceType,
    KnowledgeTrustLevel,
)
from app.models.user import User, UserRole
from app.models.workflow import WorkflowStatus
from app.services.content_defaults import ensure_content_defaults

DEFAULT_BRAND_VOICE = """- Ton: freundlich, direkt, professionell, keine Übertreibungen
- Länge: 6–12 Sätze Standard
- Emojis: selten/nie
- Anrede: „Hi <Name>,“ oder „Hallo <Name>,“ je nach Kontext
- Closing: „Viele Grüße,“
- Do: klare Fragen, next steps, kurze Bulletpoints
- Don’t: Zusagen ohne Bestätigung, keine privaten Daten
""".strip()

DEFAULT_POLICY = """- Keine Bankdaten, Adresse, Telefonnummer ausgeben oder wiederholen.
- Keine rechtsverbindlichen Zusagen („verbindlich“, „garantiere“) ohne manuelle Freigabe.
- Bei unklaren Details: max. 3 konkrete Rückfragen.
- Bei dubiosen Mails: höfliche Ablehnung + keine Links klicken + um offizielle Kontaktwege bitten.
""".strip()

SYSTEM_DEFAULT_SOURCE_NAME = "CreatorHUB system default"
SYSTEM_DEFAULT_REVIEWER_NAME = "CreatorHUB bootstrap"
SYSTEM_DEFAULT_SOURCE_REVIEW_NOTE = "Bundled and reviewed by CreatorHUB."
SYSTEM_DEFAULT_ORIGIN_SUMMARY = "Built-in CreatorHUB bootstrap knowledge."

_DEFAULT_KNOWLEDGE_DOCS = (
    (KnowledgeDocType.brand_voice, "Default Brand Voice", DEFAULT_BRAND_VOICE),
    (KnowledgeDocType.policy, "Default Policy", DEFAULT_POLICY),
)


def _is_untouched_legacy_system_default(
    doc: KnowledgeDoc,
    *,
    doc_type: KnowledgeDocType,
    title: str,
    content: str,
) -> bool:
    return (
        doc.type == doc_type
        and doc.title == title
        and doc.content == content
        and doc.workflow_status == WorkflowStatus.draft
        and doc.review_reason is None
        and doc.reviewed_by_id is None
        and doc.reviewed_by_name is None
        and doc.reviewed_at is None
        and doc.source_name is None
        and doc.source_url is None
        and doc.source_type == KnowledgeSourceType.internal
        and doc.source_review_status == KnowledgeSourceReviewStatus.pending
        and doc.source_review_note is None
        and doc.origin_summary is None
        and doc.trust_level == KnowledgeTrustLevel.medium
        and doc.is_outdated is False
        and doc.outdated_reason is None
        and doc.outdated_at is None
        and doc.current_version == 1
        and not doc.versions
    )


def _mark_system_default_trusted(doc: KnowledgeDoc) -> None:
    doc.workflow_status = WorkflowStatus.published
    doc.review_reason = None
    doc.reviewed_by_id = None
    doc.reviewed_by_name = SYSTEM_DEFAULT_REVIEWER_NAME
    doc.reviewed_at = utcnow()
    doc.source_name = SYSTEM_DEFAULT_SOURCE_NAME
    doc.source_url = None
    doc.source_type = KnowledgeSourceType.internal
    doc.source_review_status = KnowledgeSourceReviewStatus.approved
    doc.source_review_note = SYSTEM_DEFAULT_SOURCE_REVIEW_NOTE
    doc.origin_summary = SYSTEM_DEFAULT_ORIGIN_SUMMARY
    doc.trust_level = KnowledgeTrustLevel.verified
    doc.is_outdated = False
    doc.outdated_reason = None
    doc.outdated_at = None
    doc.current_version = 1


def ensure_default_knowledge_docs(db: Session) -> None:
    for doc_type, title, content in _DEFAULT_KNOWLEDGE_DOCS:
        existing = db.query(KnowledgeDoc).filter(KnowledgeDoc.type == doc_type).all()
        if not existing:
            doc = KnowledgeDoc(type=doc_type, title=title, content=content)
            _mark_system_default_trusted(doc)
            db.add(doc)
            continue

        legacy_candidates = [
            doc
            for doc in existing
            if _is_untouched_legacy_system_default(
                doc,
                doc_type=doc_type,
                title=title,
                content=content,
            )
        ]
        if len(legacy_candidates) == 1:
            _mark_system_default_trusted(legacy_candidates[0])


def bootstrap_if_needed() -> None:
    import os
    import secrets

    if os.getenv("SKIP_BOOTSTRAP", "false").lower() in ("true", "1", "yes"):
        print("SKIP_BOOTSTRAP is set - skipping bootstrap")
        return

    db: Session = SessionLocal()
    try:
        # Create the default admin only once.
        admin = db.query(User).filter(User.username == settings.BOOTSTRAP_ADMIN_USERNAME).first()
        if not admin:
            db.add(
                User(
                    username=settings.BOOTSTRAP_ADMIN_USERNAME,
                    hashed_password=hash_password(secrets.token_urlsafe(48)),
                    role=UserRole.admin,
                    is_active=True,
                    needs_password_setup=True,
                )
            )
            db.commit()

        ensure_default_knowledge_docs(db)
        ensure_content_defaults(db)
        db.commit()
    finally:
        db.close()
