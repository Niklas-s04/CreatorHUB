from __future__ import annotations

import json
import time
from typing import Any, Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.services.outbound_http import request_outbound


class OllamaError(RuntimeError):
    pass


class AiOutputTechnicalError(RuntimeError):
    pass


def ollama_chat(
    model: str,
    system: str,
    user: str,
    images_b64: Optional[list[str]] = None,
    force_json: bool = True,
) -> tuple[str, dict]:
    """Call Ollama chat API and return (content, meta)."""
    url = f"{settings.OLLAMA_URL.rstrip('/')}/api/chat"
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    user_msg: dict[str, Any] = {"role": "user", "content": user}
    if images_b64:
        user_msg["images"] = images_b64
    messages.append(user_msg)

    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
    if force_json:
        payload["format"] = "json"

    host = (urlparse(url).hostname or "").lower()
    allow_hosts = {host} if host else None

    t0 = time.time()
    response = request_outbound(
        url=url,
        method="POST",
        json_body=payload,
        timeout_read=180,
        require_https=False,
        allow_private_ips=True,
        allowed_hosts=allow_hosts,
    )
    dt = time.time() - t0

    if response.status_code != 200:
        raise OllamaError(f"Ollama error {response.status_code}: {response.text[:500]}")
    data = response.json()
    content = (data.get("message") or {}).get("content") or ""
    meta = {k: v for k, v in data.items() if k != "message"}
    meta["duration_sec"] = round(dt, 3)
    return content, meta


def ensure_json(text: str) -> Any:
    """Parse JSON output; tolerates surrounding text."""
    text = text.strip()
    # Direkter JSON-Parse.
    try:
        return json.loads(text)
    except Exception:
        pass
    # Erstes JSON-Objekt oder -Array aus Freitext extrahieren.
    start = min([i for i in [text.find("{"), text.find("[")] if i != -1], default=-1)
    if start == -1:
        raise ValueError("No JSON start found")
    # Einfache Klammerlogik zum Finden des JSON-Endes.
    stack = []
    end = None
    for i in range(start, len(text)):
        ch = text[i]
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if not stack:
                continue
            stack.pop()
            if not stack:
                end = i + 1
                break
    if end is None:
        raise ValueError("No JSON end found")
    return json.loads(text[start:end])


def _matches_schema_type(value: Any, expected_type: str) -> bool:
    if expected_type == "str":
        return isinstance(value, str)
    if expected_type == "list":
        return isinstance(value, list)
    if expected_type == "dict":
        return isinstance(value, dict)
    if expected_type == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "bool":
        return isinstance(value, bool)
    if expected_type == "nullable_str":
        return value is None or isinstance(value, str)
    if expected_type == "nullable_list":
        return value is None or isinstance(value, list)
    if expected_type == "nullable_dict":
        return value is None or isinstance(value, dict)
    return False


def _validate_payload_schema(payload: dict[str, Any], expected_schema: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for field, expected_type in expected_schema.items():
        if field not in payload:
            errors.append(f"missing_field:{field}")
            continue
        if not _matches_schema_type(payload[field], expected_type):
            errors.append(f"invalid_type:{field}:{expected_type}")
    return errors


def safe_ollama_json(
    model: str,
    system: str,
    user: str,
    images_b64: Optional[list[str]] = None,
    max_fix_attempts: int = 1,
    expected_schema: dict[str, str] | None = None,
    fallback_payload: dict[str, Any] | None = None,
) -> tuple[dict, dict]:
    """Call Ollama, parse JSON, validate schema, and optionally apply a fallback payload.

    Technical model output faults are tracked in `technical_errors` metadata.
    Domain/business warnings should be handled by callers separately.
    """
    technical_errors: list[str] = []
    fallback_used = False
    content = ""
    meta: dict[str, Any] = {}

    try:
        content, meta = ollama_chat(
            model=model, system=system, user=user, images_b64=images_b64, force_json=True
        )
    except Exception as exc:  # noqa: BLE001
        technical_errors.append(f"ollama_call_failed:{exc.__class__.__name__}")
        if fallback_payload is not None:
            return (
                dict(fallback_payload),
                {
                    "technical_errors": technical_errors,
                    "fallback_used": True,
                    "fallback_reason": "ollama_call_failed",
                },
            )
        raise AiOutputTechnicalError("AI call failed and no fallback payload provided") from exc

    try:
        parsed = ensure_json(content)
    except Exception as exc:  # noqa: BLE001
        technical_errors.append(f"json_parse_failed:{exc.__class__.__name__}")
        if max_fix_attempts <= 0:
            if fallback_payload is not None:
                return (
                    dict(fallback_payload),
                    {
                        **meta,
                        "technical_errors": technical_errors,
                        "fallback_used": True,
                        "fallback_reason": "json_parse_failed",
                    },
                )
            raise AiOutputTechnicalError(
                "Invalid JSON output and no fallback payload provided"
            ) from exc
        fix_system = "You are a JSON repair utility. Output ONLY valid JSON."
        fix_user = f"Fix to valid JSON only. Original:\n{content}"
        try:
            fixed, meta2 = ollama_chat(
                model=model, system=fix_system, user=fix_user, images_b64=None, force_json=True
            )
            parsed = ensure_json(fixed)
            meta = {**meta, "repair": meta2}
        except Exception as repair_exc:  # noqa: BLE001
            technical_errors.append(f"json_repair_failed:{repair_exc.__class__.__name__}")
            if fallback_payload is not None:
                return (
                    dict(fallback_payload),
                    {
                        **meta,
                        "technical_errors": technical_errors,
                        "fallback_used": True,
                        "fallback_reason": "json_repair_failed",
                    },
                )
            raise AiOutputTechnicalError(
                "JSON repair failed and no fallback payload provided"
            ) from repair_exc

    if not isinstance(parsed, dict):
        technical_errors.append("json_root_not_object")
        if fallback_payload is not None:
            return (
                dict(fallback_payload),
                {
                    **meta,
                    "technical_errors": technical_errors,
                    "fallback_used": True,
                    "fallback_reason": "json_root_not_object",
                },
            )
        raise AiOutputTechnicalError("Model output JSON root must be an object")

    if expected_schema:
        schema_errors = _validate_payload_schema(parsed, expected_schema)
        if schema_errors:
            technical_errors.extend(schema_errors)
            if fallback_payload is not None:
                fallback_used = True
                parsed = dict(fallback_payload)
            else:
                raise AiOutputTechnicalError(
                    "Model JSON failed schema validation: " + ", ".join(schema_errors)
                )

    result_meta = {**meta, "technical_errors": technical_errors, "fallback_used": fallback_used}
    if fallback_used and "fallback_reason" not in result_meta:
        result_meta["fallback_reason"] = "schema_validation_failed"
    return parsed, result_meta
