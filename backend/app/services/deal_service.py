from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.deal import DealDraft, DealDraftStatus
from app.models.email import EmailThread
from app.models.user import User
from app.schemas.deal import DealDraftIntakeRequest, DealDraftUpdate
from app.services.audit import record_audit_log
from app.services.deal_intake import extract_deal_intake
from app.services.errors import NotFoundError
from app.services.transactions import transaction_boundary

DEAL_DRAFT_FIELD_KEYS = [
    "brand_name",
    "contact_name",
    "contact_email",
    "budget",
    "deliverables",
    "usage_rights",
    "deadlines",
    "notes",
]


def _snapshot_deal_draft(draft: DealDraft) -> dict[str, str | None]:
    return {
        "status": draft.status.value,
        **{key: getattr(draft, key) for key in DEAL_DRAFT_FIELD_KEYS},
    }


def _apply_fields(target: DealDraft, data: dict[str, str | None]) -> None:
    for field, value in data.items():
        setattr(target, field, value)


def _merge_intake_values(
    extracted: dict[str, str | None],
    overrides: dict[str, Any],
) -> dict[str, str | None]:
    body = {key: extracted.get(key) for key in DEAL_DRAFT_FIELD_KEYS}
    for key in DEAL_DRAFT_FIELD_KEYS:
        override_value = overrides.get(key)
        if override_value is not None:
            body[key] = str(override_value)
    return body


def list_deal_drafts(
    db: Session,
    *,
    status: DealDraftStatus | None,
    thread_id: uuid.UUID | None,
    limit: int,
) -> list[DealDraft]:
    q = db.query(DealDraft)
    if status:
        q = q.filter(DealDraft.status == status)
    if thread_id:
        q = q.filter(DealDraft.thread_id == thread_id)
    safe_limit = max(1, min(limit, 200))
    return q.order_by(DealDraft.created_at.desc()).limit(safe_limit).all()


def get_deal_by_thread(db: Session, *, thread_id: uuid.UUID) -> DealDraft:
    draft = db.query(DealDraft).filter(DealDraft.thread_id == thread_id).first()
    if not draft:
        raise NotFoundError("Deal draft not found for thread")
    return draft


def create_or_update_from_email(
    db: Session,
    *,
    payload: DealDraftIntakeRequest,
    actor: User | None,
) -> DealDraft:
    thread = db.query(EmailThread).filter(EmailThread.id == payload.thread_id).first()
    if not thread:
        raise NotFoundError("Email thread not found")

    draft = db.query(DealDraft).filter(DealDraft.thread_id == thread.id).first()

    extracted: dict[str, str | None] = {}
    target: DealDraft
    with transaction_boundary(db):
        if payload.auto_extract or not draft:
            extracted = extract_deal_intake(db, subject=thread.subject, raw_body=thread.raw_body)

        overrides = payload.model_dump(exclude={"thread_id", "auto_extract", "status"})
        body = _merge_intake_values(extracted, overrides)

        next_status = payload.status or (draft.status if draft else DealDraftStatus.intake)

        if draft:
            before = _snapshot_deal_draft(draft)
            _apply_fields(draft, body)
            draft.status = next_status
            after = _snapshot_deal_draft(draft)
            if before != after:
                record_audit_log(
                    db,
                    actor=actor,
                    action="deals.draft.update",
                    entity_type="deal_draft",
                    entity_id=str(draft.id),
                    description=f"Updated deal draft for thread '{thread.subject or thread.id}'",
                    before=before,
                    after=after,
                )
            target = draft
        else:
            new_draft = DealDraft(thread_id=thread.id, status=next_status)
            _apply_fields(new_draft, body)
            db.add(new_draft)
            db.flush()
            record_audit_log(
                db,
                actor=actor,
                action="deals.draft.create",
                entity_type="deal_draft",
                entity_id=str(new_draft.id),
                description=f"Created deal draft for thread '{thread.subject or thread.id}'",
                after=_snapshot_deal_draft(new_draft),
            )
            target = new_draft

    db.refresh(target)
    return target


def update_deal_draft(
    db: Session,
    *,
    deal_id: uuid.UUID,
    payload: DealDraftUpdate,
    actor: User | None,
) -> DealDraft:
    draft = db.query(DealDraft).filter(DealDraft.id == deal_id).first()
    if not draft:
        raise NotFoundError("Deal draft not found")

    data = payload.model_dump(exclude_unset=True)
    status = data.pop("status", None)

    before = _snapshot_deal_draft(draft)
    with transaction_boundary(db):
        for key in DEAL_DRAFT_FIELD_KEYS:
            if key in data:
                setattr(draft, key, data[key])
        if status:
            draft.status = status

        after = _snapshot_deal_draft(draft)
        if before != after:
            record_audit_log(
                db,
                actor=actor,
                action="deals.draft.update",
                entity_type="deal_draft",
                entity_id=str(draft.id),
                description=f"Updated deal draft '{draft.id}'",
                before=before,
                after=after,
            )

    db.refresh(draft)
    return draft
