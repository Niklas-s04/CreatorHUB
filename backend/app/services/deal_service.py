from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.deal import DealDraft, DealDraftStatus
from app.models.email import EmailThread
from app.models.user import User
from app.models.workflow import WorkflowStatus
from app.schemas.deal import DealDraftIntakeRequest, DealDraftUpdate
from app.services.audit import record_audit_log
from app.services.deal_checklists import merge_checklist, missing_required_items
from app.services.deal_intake import extract_deal_intake
from app.services.errors import BusinessRuleViolation, NotFoundError
from app.services.transactions import transaction_boundary
from app.services.workflow import (
    apply_workflow_change,
    auto_re_review_reason,
    requires_re_review,
    validate_workflow_status_change,
)

DEAL_DRAFT_FIELD_KEYS = [
    "product_id",
    "brand_name",
    "contact_name",
    "contact_email",
    "budget",
    "deliverables",
    "usage_rights",
    "deadlines",
    "notes",
    "checklist",
]

DEAL_RE_REVIEW_FIELDS: set[str] = set(DEAL_DRAFT_FIELD_KEYS)


def _snapshot_deal_draft(draft: DealDraft) -> dict[str, str | None]:
    return {
        "status": draft.status.value,
        "workflow_status": draft.workflow_status.value,
        "review_reason": draft.review_reason,
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
        if payload.product_id is not None:
            body["product_id"] = payload.product_id
        body["checklist"] = payload.checklist

        next_status = payload.status or (draft.status if draft else DealDraftStatus.intake)
        requested_workflow_status = payload.workflow_status
        review_reason = payload.review_reason

        if draft:
            changed_fields = {
                key
                for key in DEAL_DRAFT_FIELD_KEYS
                if key in body and getattr(draft, key) != body[key]
            }
            target_workflow_status = requested_workflow_status or draft.workflow_status
            if requested_workflow_status is None and requires_re_review(
                current_status=draft.workflow_status,
                changed_fields=changed_fields,
                relevant_fields=DEAL_RE_REVIEW_FIELDS,
            ):
                target_workflow_status = WorkflowStatus.in_review
                review_reason = review_reason or auto_re_review_reason(changed_fields)

            validate_workflow_status_change(
                current_status=draft.workflow_status,
                target_status=target_workflow_status,
                review_reason=review_reason,
            )

            before = _snapshot_deal_draft(draft)
            _apply_fields(draft, body)
            draft.status = next_status
            draft.checklist = merge_checklist(
                current=draft.checklist,
                status=draft.status,
                override=payload.checklist,
            )
            if draft.status in {DealDraftStatus.negotiating, DealDraftStatus.won}:
                missing_items = missing_required_items(draft.checklist)
                if missing_items:
                    raise BusinessRuleViolation(
                        "Deal cannot move forward, required checklist items missing: "
                        + ", ".join(missing_items)
                    )
            if target_workflow_status != draft.workflow_status:
                apply_workflow_change(
                    entity=draft,
                    target_status=target_workflow_status,
                    review_reason=review_reason,
                    actor=actor,
                )
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
            target_workflow_status = requested_workflow_status or WorkflowStatus.draft
            validate_workflow_status_change(
                current_status=target_workflow_status,
                target_status=target_workflow_status,
                review_reason=review_reason,
            )
            new_draft.workflow_status = target_workflow_status
            new_draft.review_reason = (review_reason or "").strip() or None
            _apply_fields(new_draft, body)
            new_draft.checklist = merge_checklist(
                current=None,
                status=new_draft.status,
                override=payload.checklist,
            )
            db.add(new_draft)
            db.flush()
            if target_workflow_status != WorkflowStatus.draft or new_draft.review_reason:
                apply_workflow_change(
                    entity=new_draft,
                    target_status=target_workflow_status,
                    review_reason=review_reason,
                    actor=actor,
                )
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
    requested_workflow_status = data.pop("workflow_status", None)
    explicit_review_reason = data.pop("review_reason", None)

    changed_fields = {key for key in DEAL_DRAFT_FIELD_KEYS if key in data and getattr(draft, key) != data[key]}

    target_workflow_status = requested_workflow_status or draft.workflow_status
    review_reason = explicit_review_reason
    if requested_workflow_status is None and requires_re_review(
        current_status=draft.workflow_status,
        changed_fields=changed_fields,
        relevant_fields=DEAL_RE_REVIEW_FIELDS,
    ):
        target_workflow_status = WorkflowStatus.in_review
        review_reason = review_reason or auto_re_review_reason(changed_fields)

    validate_workflow_status_change(
        current_status=draft.workflow_status,
        target_status=target_workflow_status,
        review_reason=review_reason,
    )

    before = _snapshot_deal_draft(draft)
    with transaction_boundary(db):
        for key in DEAL_DRAFT_FIELD_KEYS:
            if key in data:
                setattr(draft, key, data[key])
        if status:
            draft.status = status
        draft.checklist = merge_checklist(
            current=draft.checklist,
            status=draft.status,
            override=payload.checklist,
        )
        if draft.status in {DealDraftStatus.negotiating, DealDraftStatus.won}:
            missing_items = missing_required_items(draft.checklist)
            if missing_items:
                raise BusinessRuleViolation(
                    "Deal cannot move forward, required checklist items missing: "
                    + ", ".join(missing_items)
                )
        if target_workflow_status != draft.workflow_status:
            apply_workflow_change(
                entity=draft,
                target_status=target_workflow_status,
                review_reason=review_reason,
                actor=actor,
            )
        elif explicit_review_reason is not None and explicit_review_reason != draft.review_reason:
            draft.review_reason = explicit_review_reason.strip() or None

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
