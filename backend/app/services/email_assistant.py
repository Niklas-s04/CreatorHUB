from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_runs import AiRun
from app.models.email import EmailIntent, EmailTone
from app.services.ai_gateway import safe_ollama_json
from app.services.knowledge_service import get_knowledge_bundle
from app.services.policy_checks import detect_pii, detect_risk_keywords, redact_sensitive


EMAIL_SCHEMA_HINT = {
  "intent": "sponsoring|support|collab|shipping|refund|unknown",
  "summary": "Kurzfassung der Anfrage",
  "risk_flags": ["contains_personal_data", "unclear_terms", "scam_suspected"],
  "questions_to_ask": ["..."],
  "draft_subject": "...",
  "draft_body": "..."
}


def _build_system_prompt(db: Session) -> str:
    kb = get_knowledge_bundle(db)
    brand = kb.get("brand_voice") or "Ton: freundlich, direkt, professionell. Keine Übertreibungen."
    policy = kb.get("policy") or "Keine sensiblen Daten. Keine rechtsverbindlichen Zusagen ohne Freigabe. Max 3 Rückfragen."
    templates = kb.get("templates") or ""

    return f"""You are a local email assistant for a creator business. Follow BRAND VOICE and POLICY.

BRAND VOICE:
{brand}

POLICY / GUARDRAILS:
{policy}

TEMPLATES (optional snippets):
{templates}

Rules:
- Output ONLY valid JSON.
- Never invent facts or commitments.
- If terms are unclear, ask up to 3 concrete questions.
- If scam is suspected: politely decline and advise not clicking links.
- Do not include personal data (addresses, bank, phone). If user email contains it, do not repeat it.
""".strip()


def generate_email_draft(db: Session, subject: str | None, raw_body: str, tone: EmailTone) -> dict[str, Any]:
    system = _build_system_prompt(db)

    user = f"""Create an email reply draft.

Input Email Subject: {subject or ''}
Input Email Body:
{raw_body}

Desired tone: {tone.value}

Return JSON with keys exactly: intent, summary, risk_flags, questions_to_ask, draft_subject, draft_body.
Schema example:
{json.dumps(EMAIL_SCHEMA_HINT, ensure_ascii=False)}
""".strip()

    out, meta = safe_ollama_json(
        model=settings.OLLAMA_TEXT_MODEL,
        system=system,
        user=user,
        images_b64=None,
        max_fix_attempts=1,
    )

    # Risk-Flags mit deterministischen Checks prüfen und ergänzen.
    risk_flags = set(out.get("risk_flags") or [])
    # Risiken aus dem Eingabetext übernehmen.
    inp_pii = detect_pii(raw_body)
    inp_kw = detect_risk_keywords(raw_body)
    if inp_pii:
        risk_flags.add("contains_personal_data")
        risk_flags.update(inp_pii)
    risk_flags.update(inp_kw)

    # Ausgabe auf sensible Daten prüfen.
    draft_body = str(out.get("draft_body") or "")
    out_pii = detect_pii(draft_body)
    if out_pii:
        risk_flags.add("output_contains_personal_data")
        draft_body = redact_sensitive(draft_body)

    # Intent auf gültige Enum-Werte normieren.
    intent_raw = str(out.get("intent") or "unknown").lower()
    if intent_raw not in {e.value for e in EmailIntent}:
        intent_raw = "unknown"

    result = {
        "intent": intent_raw,
        "summary": (out.get("summary") or "")[:5000],
        "risk_flags": sorted(risk_flags),
        "questions_to_ask": out.get("questions_to_ask") or [],
        "draft_subject": out.get("draft_subject") or subject or "",
        "draft_body": draft_body,
    }

    db.add(AiRun(
        job_type="email_reply",
        model=settings.OLLAMA_TEXT_MODEL,
        input_summary=(subject or "")[:200] + " | " + raw_body[:500],
        output_summary=(result["draft_subject"] or "")[:200] + " | " + result["draft_body"][:500],
        meta_json=meta,
    ))
    db.commit()

    return result


def refine_email_draft(
    db: Session,
    subject: str | None,
    raw_body: str,
    tone: EmailTone,
    previous_draft_subject: str | None,
    previous_draft_body: str,
    qa: list[dict[str, str]],
    note: str | None = None,
) -> dict[str, Any]:
    """Create a refined draft based on a previous draft plus user answers.

    This enables a 2-step flow in the UI:
      1) AI drafts + asks questions
      2) User answers → AI refines
    """

    system = _build_system_prompt(db)

    # Prompt bewusst einfach und deterministisch halten.
    qa_lines: list[str] = []
    for item in qa or []:
        q = (item.get("question") or "").strip()
        a = (item.get("answer") or "").strip()
        if not q and not a:
            continue
        qa_lines.append(f"Q: {q}\nA: {a}")

    qa_block = "\n\n".join(qa_lines) if qa_lines else "(no answers provided)"
    note_block = (note or "").strip()

    user = f"""Refine an email reply draft.

Original Email Subject: {subject or ''}
Original Email Body:
{raw_body}

Previous Draft Subject: {previous_draft_subject or ''}
Previous Draft Body:
{previous_draft_body}

User answers / clarifications:
{qa_block}

Additional note (optional):
{note_block}

Desired tone: {tone.value}

Return JSON with keys exactly: intent, summary, risk_flags, questions_to_ask, draft_subject, draft_body.
Schema example:
{json.dumps(EMAIL_SCHEMA_HINT, ensure_ascii=False)}

Rules:
- Incorporate the user's answers.
- If anything is still unclear, ask at most 2 follow-up questions.
- Keep the reply short and actionable.
""".strip()

    out, meta = safe_ollama_json(
        model=settings.OLLAMA_TEXT_MODEL,
        system=system,
        user=user,
        images_b64=None,
        max_fix_attempts=1,
    )

    # Risk-Flags mit deterministischen Checks prüfen und ergänzen.
    risk_flags = set(out.get("risk_flags") or [])
    inp_pii = detect_pii(raw_body)
    inp_kw = detect_risk_keywords(raw_body)
    if inp_pii:
        risk_flags.add("contains_personal_data")
        risk_flags.update(inp_pii)
    risk_flags.update(inp_kw)

    draft_body = str(out.get("draft_body") or "")
    out_pii = detect_pii(draft_body)
    if out_pii:
        risk_flags.add("output_contains_personal_data")
        draft_body = redact_sensitive(draft_body)

    intent_raw = str(out.get("intent") or "unknown").lower()
    if intent_raw not in {e.value for e in EmailIntent}:
        intent_raw = "unknown"

    # Nachfragen im Refine-Schritt stärker begrenzen.
    questions = out.get("questions_to_ask") or []
    if isinstance(questions, list) and len(questions) > 2:
        questions = questions[:2]

    result = {
        "intent": intent_raw,
        "summary": (out.get("summary") or "")[:5000],
        "risk_flags": sorted(risk_flags),
        "questions_to_ask": questions,
        "draft_subject": out.get("draft_subject") or subject or "",
        "draft_body": draft_body,
    }

    db.add(
        AiRun(
            job_type="email_refine",
            model=settings.OLLAMA_TEXT_MODEL,
            input_summary=(subject or "")[:200] + " | " + raw_body[:500],
            output_summary=(result["draft_subject"] or "")[:200] + " | " + result["draft_body"][:500],
            meta_json={
                **(meta or {}),
                "qa_count": len(qa_lines),
            },
        )
    )
    db.commit()

    return result