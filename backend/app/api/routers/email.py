from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.api.querying import apply_sorting, pagination_params, to_page
from app.core.authorization import Permission
from app.models.ai_settings import CreatorAiProfile, CreatorAiTone
from app.models.base import utcnow
from app.models.email import (
    EmailApprovalStatus,
    EmailDraft,
    EmailDraftSource,
    EmailDraftSuggestion,
    EmailDraftSuggestionType,
    EmailDraftVersion,
    EmailHandoffStatus,
    EmailIntent,
    EmailRiskLevel,
    EmailTemplate,
    EmailThread,
    EmailThreadMessage,
    EmailThreadMessageRole,
)
from app.models.knowledge import KnowledgeDoc, KnowledgeDocDraftLink
from app.models.user import User, UserRole
from app.schemas.common import Page, SortOrder
from app.schemas.email import (
    CreatorAiProfileInput,
    CreatorAiProfileOut,
    CreatorAiSettingsPreviewOut,
    EmailDraftApprovalRequest,
    EmailDraftHandoffRequest,
    EmailDraftManualUpdateRequest,
    EmailDraftOut,
    EmailDraftRequest,
    EmailRefineRequest,
    EmailTemplateCreate,
    EmailTemplateOut,
    EmailTemplateUpdate,
    EmailThreadDetailOut,
    EmailThreadOut,
)
from app.services.audit import record_audit_log
from app.services.creator_ai_settings import resolve_effective_settings, validate_profile_data
from app.services.domain_events import emit_domain_event
from app.services.email_assistant import generate_email_draft, refine_email_draft
from app.services.knowledge_service import link_docs_to_draft

router = APIRouter()


CRITICAL_RISK_FLAGS = {
    "scam_suspected",
    "contains_credit_card",
    "contains_iban",
    "output_contains_personal_data",
}
HIGH_RISK_FLAGS = {
    "binding_promise",
    "contains_links",
    "contains_email_address",
    "contains_phone_number",
}


def _normalize_risk_flags(raw_flags: Any) -> list[str]:
    if isinstance(raw_flags, list):
        return sorted({str(flag).strip() for flag in raw_flags if str(flag).strip()})
    if not raw_flags:
        return []
    try:
        parsed = json.loads(raw_flags)
        if isinstance(parsed, list):
            return sorted({str(flag).strip() for flag in parsed if str(flag).strip()})
    except (ValueError, TypeError):
        return []
    return []


def _risk_profile(flags: list[str]) -> tuple[int, EmailRiskLevel, str, bool, EmailApprovalStatus, EmailHandoffStatus]:
    score = 0
    for flag in flags:
        if flag in CRITICAL_RISK_FLAGS:
            score += 3
        elif flag in HIGH_RISK_FLAGS:
            score += 2
        else:
            score += 1

    level = EmailRiskLevel.low
    if score >= 6:
        level = EmailRiskLevel.critical
    elif score >= 3:
        level = EmailRiskLevel.high
    elif score >= 1:
        level = EmailRiskLevel.medium

    # Hard human-in-the-loop rule: AI-generated drafts always require explicit human approval.
    approval_required = True
    approval_status = EmailApprovalStatus.pending
    handoff_status = EmailHandoffStatus.blocked

    summary = "No relevant risks detected"
    if flags:
        summary = ", ".join(flags[:4])
        if len(flags) > 4:
            summary = f"{summary}, +{len(flags) - 4} more"

    return score, level, summary, approval_required, approval_status, handoff_status


def _log_thread_message(
    db: Session,
    thread_id: uuid.UUID,
    role: EmailThreadMessageRole,
    content: str | None,
    payload: dict[str, Any],
) -> None:
    db.add(EmailThreadMessage(thread_id=thread_id, role=role, content=content, payload=payload))


def _append_draft_version(
    db: Session,
    draft: EmailDraft,
    actor: User | None,
    reason: str,
) -> None:
    current_max = (
        db.query(EmailDraftVersion.version_number)
        .filter(EmailDraftVersion.draft_id == draft.id)
        .order_by(EmailDraftVersion.version_number.desc())
        .first()
    )
    next_version = 1 if not current_max else int(current_max[0]) + 1
    db.add(
        EmailDraftVersion(
            draft_id=draft.id,
            version_number=next_version,
            draft_subject=draft.draft_subject,
            draft_body=draft.draft_body,
            tone=draft.tone,
            changed_by_id=actor.id if actor else None,
            changed_by_name=actor.username if actor else None,
            change_reason=reason,
        )
    )


def _add_draft_suggestion(
    db: Session,
    draft: EmailDraft,
    suggestion_type: EmailDraftSuggestionType,
    source: str,
    summary: str,
    payload: dict[str, Any] | None,
    decided: bool = False,
    actor: User | None = None,
) -> None:
    db.add(
        EmailDraftSuggestion(
            draft_id=draft.id,
            suggestion_type=suggestion_type,
            source=source,
            summary=summary,
            payload=payload,
            decided=decided,
            decided_at=utcnow() if decided else None,
            decided_by_id=actor.id if decided and actor else None,
            decided_by_name=actor.username if decided and actor else None,
        )
    )


def _resolve_template(
    db: Session,
    template_id: uuid.UUID | None,
    thread_id: uuid.UUID,
) -> EmailTemplate | None:
    if not template_id:
        return None
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if not template.active:
        raise HTTPException(status_code=400, detail="Template is not active")
    if template.thread_id and template.thread_id != thread_id:
        raise HTTPException(status_code=400, detail="Template does not belong to this thread")
    return template


def _next_thread_version_number(db: Session, thread_id: uuid.UUID) -> int:
    max_version = (
        db.query(EmailDraft.version_number)
        .filter(EmailDraft.thread_id == thread_id)
        .order_by(EmailDraft.version_number.desc())
        .first()
    )
    return 1 if not max_version else int(max_version[0]) + 1


def _validate_handoff_transition(
    draft: EmailDraft,
    status: EmailHandoffStatus,
    note: str | None,
) -> None:
    if status == EmailHandoffStatus.ready_for_send:
        if not (draft.draft_subject or "").strip() or not (draft.draft_body or "").strip():
            raise HTTPException(status_code=400, detail="Draft subject and body are required for handoff")
        if draft.approval_required and draft.approval_status != EmailApprovalStatus.approved:
            raise HTTPException(status_code=400, detail="Draft must be approved before handoff")
    if status == EmailHandoffStatus.handed_off:
        if draft.handoff_status != EmailHandoffStatus.ready_for_send:
            raise HTTPException(status_code=400, detail="Draft must be ready_for_send before handoff")
        if draft.approval_required and draft.approval_status != EmailApprovalStatus.approved:
            raise HTTPException(status_code=400, detail="Draft must be approved before handoff")
        if not note:
            raise HTTPException(status_code=400, detail="Handoff note is required when marking handed_off")
    if status == EmailHandoffStatus.blocked and not note:
        raise HTTPException(status_code=400, detail="Blocking handoff requires a reason")


def _get_creator_profile_for_user(
    db: Session,
    *,
    profile_id: uuid.UUID,
    current_user: User,
) -> CreatorAiProfile:
    profile = db.query(CreatorAiProfile).filter(CreatorAiProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Creator profile not found")
    if not profile.is_global_default and profile.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No access to this creator profile")
    return profile


@router.get("/ai-settings/profiles", response_model=list[CreatorAiProfileOut])
def list_creator_profiles(
    include_global_default: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.email_generate)),
) -> list[CreatorAiProfileOut]:
    qry = db.query(CreatorAiProfile).filter(CreatorAiProfile.owner_user_id == current_user.id)
    profiles = qry.order_by(CreatorAiProfile.updated_at.desc()).all()
    if include_global_default:
        global_defaults = (
            db.query(CreatorAiProfile)
            .filter(
                CreatorAiProfile.is_global_default.is_(True),
                CreatorAiProfile.is_active.is_(True),
            )
            .order_by(CreatorAiProfile.updated_at.desc())
            .all()
        )
        profiles = profiles + [p for p in global_defaults if p.id not in {item.id for item in profiles}]
    return profiles


@router.post("/ai-settings/profiles", response_model=CreatorAiProfileOut)
def create_creator_profile(
    payload: CreatorAiProfileInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.email_generate)),
) -> CreatorAiProfileOut:
    try:
        validated = validate_profile_data(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    profile = CreatorAiProfile(
        owner_user_id=current_user.id,
        profile_name=payload.profile_name.strip() or "Mein Profil",
        is_global_default=False,
        is_active=payload.is_active,
        clear_name=str(validated["clear_name"]),
        artist_name=str(validated["artist_name"]),
        channel_link=str(validated["channel_link"]),
        themes=list(validated["themes"]),
        platforms=list(validated["platforms"]),
        short_description=validated["short_description"],
        tone=CreatorAiTone(str(validated["tone"])),
        target_audience=validated["target_audience"],
        language_code=str(validated["language_code"]),
        content_focus=list(validated["content_focus"]),
        created_by_id=current_user.id,
        created_by_name=current_user.username,
        updated_by_id=current_user.id,
        updated_by_name=current_user.username,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    record_audit_log(
        db,
        actor=current_user,
        action="email.ai_settings.profile.create",
        entity_type="creator_ai_profile",
        entity_id=str(profile.id),
        description="Created creator AI settings profile",
        after={
            "profile_name": profile.profile_name,
            "owner_user_id": str(profile.owner_user_id),
            "is_active": profile.is_active,
        },
    )
    db.commit()
    return profile


@router.patch("/ai-settings/profiles/{profile_id}", response_model=CreatorAiProfileOut)
def update_creator_profile(
    profile_id: uuid.UUID,
    payload: CreatorAiProfileInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.email_generate)),
) -> CreatorAiProfileOut:
    profile = _get_creator_profile_for_user(
        db,
        profile_id=profile_id,
        current_user=current_user,
    )
    if profile.is_global_default and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can modify global defaults")

    try:
        validated = validate_profile_data(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    before = {
        "profile_name": profile.profile_name,
        "is_active": profile.is_active,
        "channel_link": profile.channel_link,
        "language_code": profile.language_code,
    }

    profile.profile_name = payload.profile_name.strip() or profile.profile_name
    profile.is_active = payload.is_active
    profile.clear_name = str(validated["clear_name"])
    profile.artist_name = str(validated["artist_name"])
    profile.channel_link = str(validated["channel_link"])
    profile.themes = list(validated["themes"])
    profile.platforms = list(validated["platforms"])
    profile.short_description = validated["short_description"]
    profile.tone = CreatorAiTone(str(validated["tone"]))
    profile.target_audience = validated["target_audience"]
    profile.language_code = str(validated["language_code"])
    profile.content_focus = list(validated["content_focus"])
    profile.updated_by_id = current_user.id
    profile.updated_by_name = current_user.username

    record_audit_log(
        db,
        actor=current_user,
        action="email.ai_settings.profile.update",
        entity_type="creator_ai_profile",
        entity_id=str(profile.id),
        description="Updated creator AI settings profile",
        before=before,
        after={
            "profile_name": profile.profile_name,
            "is_active": profile.is_active,
            "channel_link": profile.channel_link,
            "language_code": profile.language_code,
        },
    )
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/ai-settings/default", response_model=CreatorAiProfileOut)
def upsert_global_default_profile(
    payload: CreatorAiProfileInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.email_generate)),
) -> CreatorAiProfileOut:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can update global defaults")

    try:
        validated = validate_profile_data(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    profile = (
        db.query(CreatorAiProfile)
        .filter(CreatorAiProfile.is_global_default.is_(True))
        .order_by(CreatorAiProfile.updated_at.desc())
        .first()
    )
    if profile is None:
        profile = CreatorAiProfile(
            owner_user_id=None,
            profile_name=payload.profile_name.strip() or "Global Default",
            is_global_default=True,
            is_active=True,
            clear_name=str(validated["clear_name"]),
            artist_name=str(validated["artist_name"]),
            channel_link=str(validated["channel_link"]),
            themes=list(validated["themes"]),
            platforms=list(validated["platforms"]),
            short_description=validated["short_description"],
            tone=CreatorAiTone(str(validated["tone"])),
            target_audience=validated["target_audience"],
            language_code=str(validated["language_code"]),
            content_focus=list(validated["content_focus"]),
            created_by_id=current_user.id,
            created_by_name=current_user.username,
            updated_by_id=current_user.id,
            updated_by_name=current_user.username,
        )
        db.add(profile)
    else:
        profile.profile_name = payload.profile_name.strip() or profile.profile_name
        profile.is_active = True
        profile.clear_name = str(validated["clear_name"])
        profile.artist_name = str(validated["artist_name"])
        profile.channel_link = str(validated["channel_link"])
        profile.themes = list(validated["themes"])
        profile.platforms = list(validated["platforms"])
        profile.short_description = validated["short_description"]
        profile.tone = CreatorAiTone(str(validated["tone"]))
        profile.target_audience = validated["target_audience"]
        profile.language_code = str(validated["language_code"])
        profile.content_focus = list(validated["content_focus"])
        profile.updated_by_id = current_user.id
        profile.updated_by_name = current_user.username

    db.commit()
    db.refresh(profile)

    record_audit_log(
        db,
        actor=current_user,
        action="email.ai_settings.default.upsert",
        entity_type="creator_ai_profile",
        entity_id=str(profile.id),
        description="Upserted global creator AI defaults",
        after={"profile_name": profile.profile_name, "is_global_default": profile.is_global_default},
    )
    db.commit()
    return profile


@router.get("/ai-settings/preview", response_model=CreatorAiSettingsPreviewOut)
def preview_creator_ai_settings(
    profile_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.email_generate)),
) -> CreatorAiSettingsPreviewOut:
    effective, source, profile = resolve_effective_settings(
        db,
        user=current_user,
        profile_id=profile_id,
    )
    db.commit()
    return {
        "source": source,
        "profile_id": profile.id if profile else None,
        "profile_name": profile.profile_name if profile else None,
        "missing_required": list(effective.get("missing_required") or []),
        "applied_settings": {
            "clear_name": effective.get("clear_name"),
            "artist_name": effective.get("artist_name"),
            "channel_link": effective.get("channel_link"),
            "themes": list(effective.get("themes") or []),
            "platforms": list(effective.get("platforms") or []),
            "short_description": effective.get("short_description") or "",
            "tone": effective.get("tone"),
            "target_audience": effective.get("target_audience") or "",
            "language_code": effective.get("language_code"),
            "content_focus": list(effective.get("content_focus") or []),
        },
    }


@router.post("/draft", response_model=EmailDraftOut)
def create_draft(
    payload: EmailDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.email_generate)),
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

    template = _resolve_template(db, payload.template_id, thread.id)

    effective_settings, settings_source, profile = resolve_effective_settings(
        db,
        user=current_user,
        profile_id=payload.creator_profile_id,
    )

    result = generate_email_draft(
        db,
        subject=payload.subject or thread.subject,
        raw_body=payload.raw_body,
        tone=payload.tone,
        template_subject=template.subject_template if template else None,
        template_body=template.body_template if template else None,
        creator_settings=effective_settings,
    )

    thread.detected_intent = EmailIntent(result["intent"])
    flags = _normalize_risk_flags(result.get("risk_flags"))
    risk_score, risk_level, risk_summary, approval_required, approval_status, handoff_status = (
        _risk_profile(flags)
    )

    draft = EmailDraft(
        thread_id=thread.id,
        template_id=template.id if template else None,
        source=EmailDraftSource.ai_generate,
        version_number=_next_thread_version_number(db, thread.id),
        tone=payload.tone,
        draft_subject=result.get("draft_subject"),
        draft_body=result.get("draft_body") or "",
        questions_to_ask=json.dumps(result.get("questions_to_ask") or [], ensure_ascii=False),
        risk_flags=json.dumps(flags, ensure_ascii=False),
        risk_score=risk_score,
        risk_level=risk_level,
        risk_summary=risk_summary,
        approval_required=approval_required,
        approval_status=approval_status,
        risk_checked_at=utcnow(),
        approved=False,
        handoff_status=handoff_status,
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
            "creator_profile_id": str(payload.creator_profile_id) if payload.creator_profile_id else None,
            "ai_settings_source": settings_source,
            "ai_settings_profile_name": profile.profile_name if profile else None,
        },
    )

    db.add(draft)
    db.flush()
    _append_draft_version(db, draft=draft, actor=current_user, reason="Initial draft generated")
    _add_draft_suggestion(
        db,
        draft=draft,
        suggestion_type=EmailDraftSuggestionType.ai_draft,
        source="assistant",
        summary="AI generated initial draft",
        payload={"tone": payload.tone.value, "template_id": str(template.id) if template else None},
    )
    _add_draft_suggestion(
        db,
        draft=draft,
        suggestion_type=EmailDraftSuggestionType.risk_assessment,
        source="system",
        summary=f"Risk profile: {risk_level.value}",
        payload={"risk_flags": flags, "risk_score": risk_score, "risk_level": risk_level.value},
    )
    _add_draft_suggestion(
        db,
        draft=draft,
        suggestion_type=EmailDraftSuggestionType.system_note,
        source="settings",
        summary="AI settings applied",
        payload={
            "source": settings_source,
            "profile_id": str(profile.id) if profile else None,
            "profile_name": profile.profile_name if profile else None,
        },
    )
    if template:
        _add_draft_suggestion(
            db,
            draft=draft,
            suggestion_type=EmailDraftSuggestionType.template_applied,
            source="template",
            summary=f"Template applied: {template.name}",
            payload={"template_id": str(template.id), "template_name": template.name},
            decided=True,
            actor=current_user,
        )

    raw_doc_ids = result.get("knowledge_doc_ids") or []
    doc_ids: list[uuid.UUID] = []
    for raw in raw_doc_ids:
        try:
            doc_ids.append(uuid.UUID(str(raw)))
        except (TypeError, ValueError):
            continue
    link_docs_to_draft(
        db,
        doc_ids=doc_ids,
        email_draft_id=draft.id,
        actor=current_user,
    )

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
            "risk_level": draft.risk_level.value,
            "approved": draft.approved,
            "approval_required": draft.approval_required,
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
            "risk_flags": flags,
            "risk_level": draft.risk_level.value,
        },
        description="Email draft risk check completed",
    )
    db.commit()
    return draft


@router.post("/refine", response_model=EmailDraftOut)
def refine_draft(
    payload: EmailRefineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.email_generate)),
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

    template = _resolve_template(db, payload.template_id, thread.id)

    # Ursprünglichen E-Mail-Text aus dem Thread als Referenz nutzen.
    raw_body = thread.raw_body
    subject = thread.subject

    effective_settings, settings_source, profile = resolve_effective_settings(
        db,
        user=current_user,
        profile_id=payload.creator_profile_id,
    )

    result = refine_email_draft(
        db,
        subject=subject,
        raw_body=raw_body,
        tone=payload.tone,
        previous_draft_subject=prev.draft_subject,
        previous_draft_body=prev.draft_body,
        qa=payload.qa or [],
        note=payload.note,
        template_subject=template.subject_template if template else None,
        template_body=template.body_template if template else None,
        creator_settings=effective_settings,
    )

    thread.detected_intent = EmailIntent(result["intent"])
    flags = _normalize_risk_flags(result.get("risk_flags"))
    risk_score, risk_level, risk_summary, approval_required, approval_status, handoff_status = (
        _risk_profile(flags)
    )

    draft = EmailDraft(
        thread_id=thread.id,
        parent_draft_id=prev.id,
        template_id=template.id if template else prev.template_id,
        source=EmailDraftSource.ai_refine,
        version_number=_next_thread_version_number(db, thread.id),
        tone=payload.tone,
        draft_subject=result.get("draft_subject"),
        draft_body=result.get("draft_body") or "",
        questions_to_ask=json.dumps(result.get("questions_to_ask") or [], ensure_ascii=False),
        risk_flags=json.dumps(flags, ensure_ascii=False),
        risk_score=risk_score,
        risk_level=risk_level,
        risk_summary=risk_summary,
        approval_required=approval_required,
        approval_status=approval_status,
        risk_checked_at=utcnow(),
        approved=False,
        handoff_status=handoff_status,
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
            "creator_profile_id": str(payload.creator_profile_id) if payload.creator_profile_id else None,
            "ai_settings_source": settings_source,
            "ai_settings_profile_name": profile.profile_name if profile else None,
        },
    )

    db.add(draft)
    db.flush()
    _append_draft_version(db, draft=draft, actor=current_user, reason="Draft refined")
    _add_draft_suggestion(
        db,
        draft=draft,
        suggestion_type=EmailDraftSuggestionType.ai_refine,
        source="assistant",
        summary="AI refined previous draft",
        payload={
            "parent_draft_id": str(prev.id),
            "qa_count": len(payload.qa or []),
            "template_id": str(template.id) if template else None,
        },
    )
    _add_draft_suggestion(
        db,
        draft=draft,
        suggestion_type=EmailDraftSuggestionType.risk_assessment,
        source="system",
        summary=f"Risk profile: {risk_level.value}",
        payload={"risk_flags": flags, "risk_score": risk_score, "risk_level": risk_level.value},
    )
    _add_draft_suggestion(
        db,
        draft=draft,
        suggestion_type=EmailDraftSuggestionType.system_note,
        source="settings",
        summary="AI settings applied",
        payload={
            "source": settings_source,
            "profile_id": str(profile.id) if profile else None,
            "profile_name": profile.profile_name if profile else None,
        },
    )
    if template:
        _add_draft_suggestion(
            db,
            draft=draft,
            suggestion_type=EmailDraftSuggestionType.template_applied,
            source="template",
            summary=f"Template applied: {template.name}",
            payload={"template_id": str(template.id), "template_name": template.name},
            decided=True,
            actor=current_user,
        )

    raw_doc_ids = result.get("knowledge_doc_ids") or []
    doc_ids: list[uuid.UUID] = []
    for raw in raw_doc_ids:
        try:
            doc_ids.append(uuid.UUID(str(raw)))
        except (TypeError, ValueError):
            continue
    link_docs_to_draft(
        db,
        doc_ids=doc_ids,
        email_draft_id=draft.id,
        actor=current_user,
    )

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
            "risk_level": draft.risk_level.value,
            "approved": draft.approved,
            "approval_required": draft.approval_required,
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
            "risk_flags": flags,
            "risk_level": draft.risk_level.value,
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
    if draft.approval_required and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can approve high-risk drafts")
    if draft.risk_level in {EmailRiskLevel.high, EmailRiskLevel.critical} and payload.approved and not reason:
        raise HTTPException(
            status_code=400,
            detail="Approval reason required for high-risk drafts",
        )
    if not payload.approved and not reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")

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
    if draft.approval_required:
        draft.approval_status = (
            EmailApprovalStatus.approved if payload.approved else EmailApprovalStatus.rejected
        )
    else:
        draft.approval_status = EmailApprovalStatus.not_required

    if not payload.approved:
        draft.handoff_status = EmailHandoffStatus.blocked

    _add_draft_suggestion(
        db,
        draft=draft,
        suggestion_type=EmailDraftSuggestionType.approval_decision,
        source="workflow",
        summary=("Approved" if payload.approved else "Rejected") + " draft",
        payload={"approved": payload.approved, "reason": reason, "risk_level": draft.risk_level.value},
        decided=True,
        actor=current_user,
    )
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
            "approval_status": draft.approval_status.value,
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
            "risk_level": draft.risk_level.value,
            "approval_status": draft.approval_status.value,
            "approval_reason": draft.approval_reason,
        },
        description="Email draft approval updated",
    )

    db.commit()
    db.refresh(draft)
    return draft


@router.patch("/drafts/{draft_id}", response_model=EmailDraftOut)
def update_draft_content(
    draft_id: uuid.UUID,
    payload: EmailDraftManualUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.email_generate)),
) -> EmailDraftOut:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    before = {
        "draft_subject": draft.draft_subject,
        "draft_body": draft.draft_body,
        "tone": draft.tone.value,
        "approval_status": draft.approval_status.value,
        "handoff_status": draft.handoff_status.value,
    }

    changed = False
    if payload.draft_subject is not None:
        draft.draft_subject = payload.draft_subject.strip() or None
        changed = True
    if payload.draft_body is not None:
        body = payload.draft_body.strip()
        if not body:
            raise HTTPException(status_code=400, detail="Draft body must not be empty")
        draft.draft_body = body
        changed = True
    if payload.tone is not None:
        draft.tone = payload.tone
        changed = True

    if not changed:
        raise HTTPException(status_code=400, detail="No draft changes provided")

    draft.source = EmailDraftSource.manual
    draft.approved = False
    draft.approved_at = None
    draft.approved_by_id = None
    draft.approved_by_name = None
    draft.approval_status = EmailApprovalStatus.pending
    draft.approval_required = True
    draft.handoff_status = EmailHandoffStatus.blocked
    draft.handoff_note = None

    reason = (payload.change_reason or "").strip() or "Manual editorial update"
    _append_draft_version(db, draft=draft, actor=current_user, reason=reason)
    _add_draft_suggestion(
        db,
        draft=draft,
        suggestion_type=EmailDraftSuggestionType.system_note,
        source="editor",
        summary="Manual draft revision saved",
        payload={"change_reason": reason},
        decided=True,
        actor=current_user,
    )

    record_audit_log(
        db,
        actor=current_user,
        action="email.draft.update",
        entity_type="email_draft",
        entity_id=str(draft.id),
        description="Updated draft content and reset approval state",
        before=before,
        after={
            "draft_subject": draft.draft_subject,
            "draft_body": draft.draft_body,
            "tone": draft.tone.value,
            "approval_status": draft.approval_status.value,
            "handoff_status": draft.handoff_status.value,
        },
    )

    emit_domain_event(
        db,
        actor=current_user,
        event_name="email.draft.edited",
        entity_type="email_draft",
        entity_id=str(draft.id),
        payload={"change_reason": reason},
        description="Draft was manually edited",
    )

    db.commit()
    db.refresh(draft)
    return draft


@router.patch("/drafts/{draft_id}/handoff", response_model=EmailDraftOut)
def set_draft_handoff(
    draft_id: uuid.UUID,
    payload: EmailDraftHandoffRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.email_generate)),
) -> EmailDraftOut:
    draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    note = (payload.note or "").strip() or None
    _validate_handoff_transition(draft, payload.status, note)

    before = {
        "handoff_status": draft.handoff_status.value,
        "handoff_note": draft.handoff_note,
    }

    draft.handoff_status = payload.status
    draft.handoff_note = note
    if payload.status == EmailHandoffStatus.handed_off:
        draft.handed_off_at = utcnow()
        draft.handed_off_by_id = current_user.id
        draft.handed_off_by_name = current_user.username

    _add_draft_suggestion(
        db,
        draft=draft,
        suggestion_type=EmailDraftSuggestionType.handoff_decision,
        source="workflow",
        summary=f"Handoff set to {payload.status.value}",
        payload={"status": payload.status.value, "note": note},
        decided=True,
        actor=current_user,
    )

    record_audit_log(
        db,
        actor=current_user,
        action="email.draft.handoff",
        entity_type="email_draft",
        entity_id=str(draft.id),
        description="Updated draft handoff status",
        before=before,
        after={
            "handoff_status": draft.handoff_status.value,
            "handoff_note": draft.handoff_note,
            "handed_off_at": draft.handed_off_at.isoformat() if draft.handed_off_at else None,
            "handed_off_by_id": str(draft.handed_off_by_id) if draft.handed_off_by_id else None,
            "handed_off_by_name": draft.handed_off_by_name,
        },
    )
    emit_domain_event(
        db,
        actor=current_user,
        event_name="email.draft.handoff.changed",
        entity_type="email_draft",
        entity_id=str(draft.id),
        payload={"status": draft.handoff_status.value, "note": draft.handoff_note},
        description="Email draft handoff updated",
    )

    db.commit()
    db.refresh(draft)
    return draft


@router.get("/templates", response_model=list[EmailTemplateOut])
def list_templates(
    thread_id: uuid.UUID | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[EmailTemplateOut]:
    qry = db.query(EmailTemplate)
    if thread_id:
        qry = qry.filter(or_(EmailTemplate.thread_id.is_(None), EmailTemplate.thread_id == thread_id))
    if active_only:
        qry = qry.filter(EmailTemplate.active.is_(True))
    return qry.order_by(EmailTemplate.updated_at.desc()).all()


@router.post("/templates", response_model=EmailTemplateOut)
def create_template(
    payload: EmailTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.email_generate)),
) -> EmailTemplateOut:
    name = payload.name.strip()
    body = payload.body_template.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Template name is required")
    if not body:
        raise HTTPException(status_code=400, detail="Template body is required")

    template = EmailTemplate(
        thread_id=payload.thread_id,
        name=name,
        intent=payload.intent,
        subject_template=(payload.subject_template or "").strip() or None,
        body_template=body,
        active=payload.active,
        created_by_id=current_user.id,
        created_by_name=current_user.username,
    )
    db.add(template)
    db.flush()

    record_audit_log(
        db,
        actor=current_user,
        action="email.template.create",
        entity_type="email_template",
        entity_id=str(template.id),
        description="Created email template",
        after={"name": template.name, "intent": template.intent.value, "active": template.active},
    )

    db.commit()
    db.refresh(template)
    return template


@router.patch("/templates/{template_id}", response_model=EmailTemplateOut)
def update_template(
    template_id: uuid.UUID,
    payload: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.email_generate)),
) -> EmailTemplateOut:
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    before = {
        "name": template.name,
        "intent": template.intent.value,
        "subject_template": template.subject_template,
        "body_template": template.body_template,
        "active": template.active,
    }

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Template name is required")
        template.name = name
    if payload.intent is not None:
        template.intent = payload.intent
    if payload.subject_template is not None:
        template.subject_template = payload.subject_template.strip() or None
    if payload.body_template is not None:
        body = payload.body_template.strip()
        if not body:
            raise HTTPException(status_code=400, detail="Template body is required")
        template.body_template = body
    if payload.active is not None:
        template.active = payload.active

    record_audit_log(
        db,
        actor=current_user,
        action="email.template.update",
        entity_type="email_template",
        entity_id=str(template.id),
        description="Updated email template",
        before=before,
        after={
            "name": template.name,
            "intent": template.intent.value,
            "subject_template": template.subject_template,
            "body_template": template.body_template,
            "active": template.active,
        },
    )

    db.commit()
    db.refresh(template)
    return template


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
    templates = (
        db.query(EmailTemplate)
        .filter(or_(EmailTemplate.thread_id.is_(None), EmailTemplate.thread_id == thread_id))
        .order_by(EmailTemplate.updated_at.desc())
        .all()
    )
    draft_ids = [d.id for d in drafts]
    versions = []
    suggestions = []
    if draft_ids:
        versions = (
            db.query(EmailDraftVersion)
            .filter(EmailDraftVersion.draft_id.in_(draft_ids))
            .order_by(EmailDraftVersion.created_at.desc())
            .all()
        )
        suggestions = (
            db.query(EmailDraftSuggestion)
            .filter(EmailDraftSuggestion.draft_id.in_(draft_ids))
            .order_by(EmailDraftSuggestion.created_at.desc())
            .all()
        )
    knowledge_evidence: list[dict[str, Any]] = []
    if draft_ids:
        evidence_rows = (
            db.query(KnowledgeDocDraftLink, KnowledgeDoc)
            .join(KnowledgeDoc, KnowledgeDoc.id == KnowledgeDocDraftLink.knowledge_doc_id)
            .filter(KnowledgeDocDraftLink.email_draft_id.in_(draft_ids))
            .order_by(KnowledgeDocDraftLink.linked_at.desc())
            .all()
        )
        knowledge_evidence = [
            {
                "draft_id": link.email_draft_id,
                "knowledge_doc_id": link.knowledge_doc_id,
                "knowledge_doc_title": doc.title,
                "knowledge_doc_type": doc.type.value,
                "linked_at": link.linked_at,
                "linked_by_name": link.linked_by_name,
            }
            for link, doc in evidence_rows
        ]
    return {
        "id": t.id,
        "subject": t.subject,
        "raw_body": t.raw_body,
        "detected_intent": t.detected_intent,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "drafts": drafts,
        "messages": messages,
        "templates": templates,
        "draft_versions": versions,
        "draft_suggestions": suggestions,
        "knowledge_evidence": knowledge_evidence,
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
