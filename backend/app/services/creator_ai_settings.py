from __future__ import annotations

import re
import uuid
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.ai_settings import CreatorAiProfile
from app.models.base import utcnow
from app.models.user import User

ALLOWED_PLATFORMS = {
    "youtube",
    "instagram",
    "tiktok",
    "twitch",
    "linkedin",
    "x",
    "facebook",
    "podcast",
    "newsletter",
    "blog",
}

ALLOWED_CONTENT_FOCUS = {
    "sponsoring",
    "community",
    "education",
    "storytelling",
    "brand_growth",
    "product_promotion",
    "behind_the_scenes",
}

LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")

STATIC_AI_DEFAULTS: dict[str, Any] = {
    "clear_name": "Creator",
    "artist_name": "Creator",
    "channel_link": "https://example.com/channel",
    "themes": ["content creation"],
    "platforms": ["youtube"],
    "short_description": "",
    "tone": "neutral",
    "target_audience": "",
    "language_code": "de",
    "content_focus": ["community"],
}


def _clean_text(value: str | None, *, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if max_len is not None:
        return cleaned[:max_len]
    return cleaned


def _normalize_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _validate_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_profile_data(payload: dict[str, Any]) -> dict[str, Any]:
    clear_name = _clean_text(str(payload.get("clear_name") or ""), max_len=128)
    artist_name = _clean_text(str(payload.get("artist_name") or ""), max_len=128)
    channel_link = _clean_text(str(payload.get("channel_link") or ""), max_len=1024)
    themes = _normalize_list(
        payload.get("themes") if isinstance(payload.get("themes"), list) else []
    )
    platforms = _normalize_list(
        payload.get("platforms") if isinstance(payload.get("platforms"), list) else []
    )
    short_description = _clean_text(
        payload.get("short_description")
        if isinstance(payload.get("short_description"), str)
        else None,
        max_len=2000,
    )
    raw_tone = payload.get("tone")
    tone_value = getattr(raw_tone, "value", raw_tone)
    tone = _clean_text(str(tone_value or "neutral"), max_len=32) or "neutral"
    target_audience = _clean_text(
        payload.get("target_audience") if isinstance(payload.get("target_audience"), str) else None,
        max_len=256,
    )
    language_code = _clean_text(str(payload.get("language_code") or "de"), max_len=16) or "de"
    content_focus = _normalize_list(
        payload.get("content_focus") if isinstance(payload.get("content_focus"), list) else []
    )

    if not clear_name:
        raise ValueError("clear_name is required")
    if not artist_name:
        raise ValueError("artist_name is required")
    if not channel_link:
        raise ValueError("channel_link is required")
    if not _validate_url(channel_link):
        raise ValueError("channel_link must be a valid http(s) URL")
    if not themes:
        raise ValueError("themes must contain at least one entry")
    if not platforms:
        raise ValueError("platforms must contain at least one entry")
    invalid_platforms = sorted({item for item in platforms if item not in ALLOWED_PLATFORMS})
    if invalid_platforms:
        raise ValueError("unsupported platform(s): " + ", ".join(invalid_platforms))
    if not LANGUAGE_PATTERN.match(language_code):
        raise ValueError("language_code must match pattern 'll' or 'll-CC'")
    invalid_focus = sorted({item for item in content_focus if item not in ALLOWED_CONTENT_FOCUS})
    if invalid_focus:
        raise ValueError("unsupported content_focus value(s): " + ", ".join(invalid_focus))
    if tone not in {"neutral", "friendly", "professional", "energetic", "direct"}:
        raise ValueError("unsupported tone value")

    return {
        "clear_name": clear_name,
        "artist_name": artist_name,
        "channel_link": channel_link,
        "themes": themes,
        "platforms": platforms,
        "short_description": short_description,
        "tone": tone,
        "target_audience": target_audience,
        "language_code": language_code,
        "content_focus": content_focus,
    }


def resolve_effective_settings(
    db: Session,
    *,
    user: User,
    profile_id: uuid.UUID | None = None,
) -> tuple[dict[str, Any], str, CreatorAiProfile | None]:
    profile: CreatorAiProfile | None = None
    source = "static_default"

    if profile_id:
        profile = (
            db.query(CreatorAiProfile)
            .filter(
                CreatorAiProfile.id == profile_id,
                CreatorAiProfile.is_active.is_(True),
            )
            .first()
        )
        if profile and not profile.is_global_default and profile.owner_user_id != user.id:
            profile = None
        if profile:
            source = "selected_profile"

    if not profile:
        profile = (
            db.query(CreatorAiProfile)
            .filter(
                CreatorAiProfile.owner_user_id == user.id,
                CreatorAiProfile.is_active.is_(True),
                CreatorAiProfile.is_global_default.is_(False),
            )
            .order_by(CreatorAiProfile.updated_at.desc())
            .first()
        )
        if profile:
            source = "user_profile"

    global_defaults = (
        db.query(CreatorAiProfile)
        .filter(
            CreatorAiProfile.is_global_default.is_(True),
            CreatorAiProfile.is_active.is_(True),
        )
        .order_by(CreatorAiProfile.updated_at.desc())
        .first()
    )

    effective: dict[str, Any] = dict(STATIC_AI_DEFAULTS)
    if global_defaults:
        effective.update(
            {
                "clear_name": global_defaults.clear_name,
                "artist_name": global_defaults.artist_name,
                "channel_link": global_defaults.channel_link,
                "themes": list(global_defaults.themes or []),
                "platforms": list(global_defaults.platforms or []),
                "short_description": global_defaults.short_description or "",
                "tone": global_defaults.tone.value,
                "target_audience": global_defaults.target_audience or "",
                "language_code": global_defaults.language_code,
                "content_focus": list(global_defaults.content_focus or []),
            }
        )
        if source == "static_default":
            source = "global_default"

    if profile:
        effective.update(
            {
                "clear_name": profile.clear_name,
                "artist_name": profile.artist_name,
                "channel_link": profile.channel_link,
                "themes": list(profile.themes or []),
                "platforms": list(profile.platforms or []),
                "short_description": profile.short_description or "",
                "tone": profile.tone.value,
                "target_audience": profile.target_audience or "",
                "language_code": profile.language_code,
                "content_focus": list(profile.content_focus or []),
            }
        )
        profile.last_used_at = utcnow()

    missing_required: list[str] = []
    if not str(effective.get("clear_name") or "").strip():
        missing_required.append("clear_name")
    if not str(effective.get("artist_name") or "").strip():
        missing_required.append("artist_name")
    if not str(effective.get("channel_link") or "").strip():
        missing_required.append("channel_link")
    themes = effective.get("themes")
    if not isinstance(themes, list) or not themes:
        missing_required.append("themes")
    platforms = effective.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        missing_required.append("platforms")
    if missing_required:
        fallback = dict(STATIC_AI_DEFAULTS)
        fallback.update(effective)
        effective = fallback

    effective["source"] = source
    effective["missing_required"] = missing_required
    return effective, source, profile


def settings_to_prompt_context(settings: dict[str, Any]) -> str:
    themes = ", ".join(settings.get("themes") or [])
    platforms = ", ".join(settings.get("platforms") or [])
    content_focus = ", ".join(settings.get("content_focus") or [])
    return (
        "CREATOR_PROFILE_CONTEXT:\n"
        f"- clear_name: {settings.get('clear_name') or ''}\n"
        f"- artist_name: {settings.get('artist_name') or ''}\n"
        f"- channel_link: {settings.get('channel_link') or ''}\n"
        f"- themes: {themes}\n"
        f"- platforms: {platforms}\n"
        f"- short_description: {settings.get('short_description') or ''}\n"
        f"- preferred_tone: {settings.get('tone') or ''}\n"
        f"- target_audience: {settings.get('target_audience') or ''}\n"
        f"- language_code: {settings.get('language_code') or ''}\n"
        f"- content_focus: {content_focus}"
    )
