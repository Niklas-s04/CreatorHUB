from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.api.querying import apply_sorting, pagination_params, to_page
from app.core.authorization import Permission
from app.models.base import utcnow
from app.models.email import (
    EmailDraft,
    EmailIntent,
    EmailThread,
    EmailThreadMessage,
    EmailThreadMessageRole,
)
from app.models.user import User
from app.schemas.common import Page, SortOrder
from app.schemas.email import (
    EmailDraftApprovalRequest,
    EmailDraftOut,
    EmailDraftRequest,
    EmailRefineRequest,
    EmailThreadDetailOut,
    EmailThreadOut,
)
from app.services.audit import record_audit_log
from app.services.domain_events import emit_domain_event
from app.services.email_assistant import generate_email_draft, refine_email_draft

router = APIRouter()


def _risk_score(raw_flags: str | None) -> int:
    if not raw_flags:
        return 0
    try:
        parsed = json.loads(raw_flags)
        if isinstance(parsed, list):
            return len(parsed)
    except (ValueError, TypeError):
        return 0
    return 0


def _log_thread_message(
    db: Session,
    thread_id: uuid.UUID,
    role: EmailThreadMessageRole,
    content: str | None,
    payload: dict[str, Any],
) -> None:
    db.add(EmailThreadMessage(thread_id=thread_id, role=role, content=content, payload=payload))


@router.post("/draft", response_model=EmailDraftOut)
def create_draft(
    payload: EmailDraftRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.email_generate)),
) -> EmailDraftOut:
    thread = None
    if payload.thread_id:
        thread = db.query(EmailThread).filter(EmailThread.id == payload.thread_id).first()
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
    else:
        thread = EmailThread(subject=payload.subject, raw_body=payload.raw_body)
        db.add(thread)
        db.commit()
        db.refresh(thread)

    result = generate_email_draft(
        db, subject=payload.subject or thread.subject, raw_body=payload.raw_body, tone=payload.tone
    )

    thread.detected_intent = EmailIntent(result["intent"])

    draft = EmailDraft(
        thread_id=thread.id,
        tone=payload.tone,
        draft_subject=result.get("draft_subject"),
        draft_body=result.get("draft_body") or "",
        questions_to_ask=json.dumps(result.get("questions_to_ask") or [], ensure_ascii=False),
        risk_flags=json.dumps(result.get("risk_flags") or [], ensure_ascii=False),
        risk_score=len(result.get("risk_flags") or []),
        risk_checked_at=utcnow(),
        approved=False,
    )
    _log_thread_message(
        db,
        thread.id,
        EmailThreadMessageRole.user,
        content=payload.raw_body,
        payload={
            "action": "draft_request",
            "subject": payload.subject or thread.subject,
            "tone": payload.tone.value,
            "raw_body": payload.raw_body,
        },
    )

    db.add(draft)

    _log_thread_message(
        db,
        thread.id,
        EmailThreadMessageRole.assistant,
        content=result.get("draft_body") or "",
        payload={
            "action": "draft_response",
            **result,
        },
    )

    db.commit()
    db.refresh(draft)
    record_audit_log(
        db,
        actor=None,
        action="email.draft.create",
        entity_type="email_draft",
        entity_id=str(draft.id),
        description="Generated email draft with risk analysis",
        after={
            "risk_score": draft.risk_score,
            "approved": draft.approved,
            "thread_id": str(draft.thread_id),
        },
    )
    emit_domain_event(
        db,
        actor=None,
        event_name="email.risk.checked",
        entity_type="email_draft",
        entity_id=str(draft.id),
        payload={
            "risk_score": draft.risk_score,
            "risk_flags": result.get("risk_flags") or [],
        },
        description="Email draft risk check completed",
    )
    db.commit()
    return draft


@router.post("/refine", response_model=EmailDraftOut)
def refine_draft(
    payload: EmailRefineRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.email_generate)),
) -> EmailDraftOut:
    thread = db.query(EmailThread).filter(EmailThread.id == payload.thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    prev = (
        db.query(EmailDraft)
        .filter(EmailDraft.id == payload.draft_id, EmailDraft.thread_id == thread.id)
        .first()
    )
    if not prev:
        raise HTTPException(status_code=404, detail="Draft not found")

    # Ursprünglichen E-Mail-Text aus dem Thread als Referenz nutzen.
    raw_body = thread.raw_body
    subject = thread.subject

    result = refine_email_draft(
        db,
        subject=subject,
        raw_body=raw_body,
        tone=payload.tone,
        previous_draft_subject=prev.draft_subject,
        previous_draft_body=prev.draft_body,
        qa=payload.qa or [],
        note=payload.note,
    )

    thread.detected_intent = EmailIntent(result["intent"])

    draft = EmailDraft(
        thread_id=thread.id,
        tone=payload.tone,
        draft_subject=result.get("draft_subject"),
        draft_body=result.get("draft_body") or "",
        questions_to_ask=json.dumps(result.get("questions_to_ask") or [], ensure_ascii=False),
        risk_flags=json.dumps(result.get("risk_flags") or [], ensure_ascii=False),
        risk_score=len(result.get("risk_flags") or []),
        risk_checked_at=utcnow(),
        approved=False,
    )
    qa_lines = []
    for item in payload.qa:
        question = (item.get("question") or "").strip()
        answer = (item.get("answer") or "").strip()
        if not answer:
            continue
        qa_lines.append(f"Q: {question}\nA: {answer}".strip())

    user_content_parts: list[str] = []
    if qa_lines:
        user_content_parts.append("\n\n".join(qa_lines))
    if payload.note:
        user_content_parts.append(f"Note: {payload.note.strip()}")

    user_content = "\n\n".join(user_content_parts) if user_content_parts else "Refinement input"

    _log_thread_message(
        db,
        thread.id,
        EmailThreadMessageRole.user,
        content=user_content,
        payload={
            "action": "draft_refine_request",
            "tone": payload.tone.value,
            "draft_id": str(payload.draft_id),
            "qa": payload.qa,
            "note": payload.note,
        },
    )

    db.add(draft)

    _log_thread_message(
        db,
        thread.id,
        EmailThreadMessageRole.assistant,
        content=result.get("draft_body") or "",
        payload={
            "action": "draft_refine_response",
            **result,
        },
    )

    db.commit()
    db.refresh(draft)
    record_audit_log(
        db,
        actor=None,
        action="email.draft.refine",
        entity_type="email_draft",
        entity_id=str(draft.id),
        description="Refined email draft with risk analysis",
        after={
            "risk_score": draft.risk_score,
            "approved": draft.approved,
            "thread_id": str(draft.thread_id),
        },
    )
    emit_domain_event(
        db,
        actor=None,
        event_name="email.risk.checked",
        entity_type="email_draft",
        entity_id=str(draft.id),
        payload={
            "risk_score": draft.risk_score,
            "risk_flags": result.get("risk_flags") or [],
        },
        description="Email draft risk check completed",
    )
    db.commit()
    return draft


@router.patch("/drafts/{draft_id}/approval", response_model=EmailDraftOut)
def set_draft_approval(
    draft_id: uuid.UUID,
    payload: EmailDraftApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.email_generate)),
) -> EmailDraftOut:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    reason = (payload.reason or "").strip() or None
    if draft.risk_score >= 3 and payload.approved and not reason:
        raise HTTPException(
            status_code=400,
            detail="Approval reason required for high-risk drafts",
        )

    before = {
        "approved": draft.approved,
        "approval_reason": draft.approval_reason,
        "risk_score": draft.risk_score,
    }

    draft.approved = payload.approved
    draft.approval_reason = reason
    draft.approved_at = utcnow()
    draft.approved_by_id = current_user.id
    draft.approved_by_name = current_user.username

    record_audit_log(
        db,
        actor=current_user,
        action="email.draft.approval",
        entity_type="email_draft",
        entity_id=str(draft.id),
        description=("Approved" if draft.approved else "Rejected") + " email draft",
        before=before,
        after={
            "approved": draft.approved,
            "approval_reason": draft.approval_reason,
            "approved_at": draft.approved_at.isoformat() if draft.approved_at else None,
            "approved_by_id": str(draft.approved_by_id) if draft.approved_by_id else None,
            "approved_by_name": draft.approved_by_name,
        },
    )
    emit_domain_event(
        db,
        actor=current_user,
        event_name="email.draft.approval.changed",
        entity_type="email_draft",
        entity_id=str(draft.id),
        payload={
            "approved": draft.approved,
            "risk_score": draft.risk_score,
            "approval_reason": draft.approval_reason,
        },
        description="Email draft approval updated",
    )

    db.commit()
    db.refresh(draft)
    return draft


@router.get("/threads", response_model=Page[EmailThreadOut])
def list_threads(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    paging: tuple[int, int, str, SortOrder] = Depends(pagination_params),
) -> Page[EmailThreadOut]:
    limit, offset, sort_by, sort_order = paging
    qry = db.query(EmailThread)
    total = qry.order_by(None).count()
    qry, selected_sort, selected_order = apply_sorting(
        qry,
        model=EmailThread,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields={"created_at", "updated_at", "subject", "detected_intent"},
        fallback="updated_at",
    )
    items = qry.offset(offset).limit(limit).all()
    return to_page(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=selected_sort,
        sort_order=selected_order,
    )


@router.get("/threads/{thread_id}", response_model=EmailThreadDetailOut)
def get_thread(
    thread_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> EmailThreadDetailOut:
    t = db.query(EmailThread).filter(EmailThread.id == thread_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    drafts = (
        db.query(EmailDraft)
        .filter(EmailDraft.thread_id == thread_id)
        .order_by(EmailDraft.created_at.desc())
        .all()
    )
    messages = (
        db.query(EmailThreadMessage)
        .filter(EmailThreadMessage.thread_id == thread_id)
        .order_by(EmailThreadMessage.created_at.asc())
        .all()
    )
    return {
        "id": t.id,
        "subject": t.subject,
        "raw_body": t.raw_body,
        "detected_intent": t.detected_intent,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "drafts": drafts,
        "messages": messages,
        "deal_draft": t.deal_draft,
    }


@router.get("/threads/{thread_id}/drafts", response_model=Page[EmailDraftOut])
def list_drafts(
    thread_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    paging: tuple[int, int, str, SortOrder] = Depends(pagination_params),
) -> Page[EmailDraftOut]:
    limit, offset, sort_by, sort_order = paging
    qry = db.query(EmailDraft).filter(EmailDraft.thread_id == thread_id)
    total = qry.order_by(None).count()
    qry, selected_sort, selected_order = apply_sorting(
        qry,
        model=EmailDraft,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields={"created_at", "updated_at", "tone", "approved"},
        fallback="created_at",
    )
    items = qry.offset(offset).limit(limit).all()
    return to_page(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=selected_sort,
        sort_order=selected_order,
    )
