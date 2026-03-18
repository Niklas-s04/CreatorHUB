from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.email import (
    EmailDraft,
    EmailIntent,
    EmailThread,
    EmailThreadMessage,
    EmailThreadMessageRole,
)
from app.models.user import User, UserRole
from app.schemas.email import (
    EmailDraftOut,
    EmailDraftRequest,
    EmailRefineRequest,
    EmailThreadDetailOut,
    EmailThreadOut,
)
from app.services.email_assistant import generate_email_draft, refine_email_draft

router = APIRouter()


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
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
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
    return draft


@router.post("/refine", response_model=EmailDraftOut)
def refine_draft(
    payload: EmailRefineRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
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
    return draft


@router.get("/threads", response_model=list[EmailThreadOut])
def list_threads(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
) -> list[EmailThreadOut]:
    return (
        db.query(EmailThread)
        .order_by(EmailThread.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
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


@router.get("/threads/{thread_id}/drafts", response_model=list[EmailDraftOut])
def list_drafts(
    thread_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[EmailDraftOut]:
    return (
        db.query(EmailDraft)
        .filter(EmailDraft.thread_id == thread_id)
        .order_by(EmailDraft.created_at.desc())
        .all()
    )
