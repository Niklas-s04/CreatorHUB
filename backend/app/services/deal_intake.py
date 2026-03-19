from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_runs import AiRun
from app.services.ai_gateway import safe_ollama_json

DEAL_FIELDS = [
    "brand_name",
    "contact_name",
    "contact_email",
    "budget",
    "deliverables",
    "usage_rights",
    "deadlines",
    "notes",
]

DEAL_INTAKE_SCHEMA = {
    "brand_name": "",
    "contact_name": "",
    "contact_email": "",
    "budget": "",
    "deliverables": "",
    "usage_rights": "",
    "deadlines": "",
    "notes": "",
}

SYSTEM_PROMPT = """You are a deal intake analyst for a creator business. Extract structured information from sponsoring inquiries.
- Return short strings.
- If a field is unknown, use an empty string.
- Budget should include currency if present (e.g. "2500 EUR").
- Deliverables, usage_rights, deadlines can be concise bullet-style text separated by semicolons.
""".strip()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract_deal_intake(db: Session, subject: str | None, raw_body: str) -> dict[str, str | None]:
    user_prompt = f"""Analyse the following email and extract sponsorship deal details.
Return JSON with keys exactly: {", ".join(DEAL_FIELDS)}.

Email Subject: {subject or ""}
Email Body:
{raw_body}
""".strip()

    out, meta = safe_ollama_json(
        model=settings.OLLAMA_TEXT_MODEL,
        system=SYSTEM_PROMPT,
        user=user_prompt,
        images_b64=None,
        max_fix_attempts=1,
    )

    cleaned = {field: _clean(out.get(field)) for field in DEAL_FIELDS}

    db.add(
        AiRun(
            job_type="deal_intake",
            model=settings.OLLAMA_TEXT_MODEL,
            input_summary=(subject or "")[:120] + " | " + raw_body[:400],
            output_summary=" | ".join(
                filter(
                    None,
                    [
                        cleaned.get("brand_name"),
                        cleaned.get("budget") or "",
                        cleaned.get("deadlines") or "",
                    ],
                )
            )[:500],
            meta_json=meta,
        )
    )
    db.flush()

    return cleaned
