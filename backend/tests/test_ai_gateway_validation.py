from __future__ import annotations

import pytest

from app.services import ai_gateway
from app.services.ai_gateway import AiOutputTechnicalError


def test_safe_ollama_json_uses_fallback_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_ollama_chat(*_args, **_kwargs):
        return "not-json", {"provider": "test"}

    monkeypatch.setattr(ai_gateway, "ollama_chat", _fake_ollama_chat)

    payload, meta = ai_gateway.safe_ollama_json(
        model="dummy",
        system="sys",
        user="user",
        expected_schema={"name": "str"},
        fallback_payload={"name": "fallback"},
        max_fix_attempts=0,
    )

    assert payload == {"name": "fallback"}
    assert meta.get("fallback_used") is True
    assert "json_parse_failed" in " ".join(meta.get("technical_errors") or [])


def test_safe_ollama_json_uses_fallback_on_schema_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_ollama_chat(*_args, **_kwargs):
        return '{"name": 123}', {"provider": "test"}

    monkeypatch.setattr(ai_gateway, "ollama_chat", _fake_ollama_chat)

    payload, meta = ai_gateway.safe_ollama_json(
        model="dummy",
        system="sys",
        user="user",
        expected_schema={"name": "str"},
        fallback_payload={"name": "fallback"},
    )

    assert payload == {"name": "fallback"}
    assert meta.get("fallback_used") is True
    assert "invalid_type:name:str" in (meta.get("technical_errors") or [])


def test_safe_ollama_json_raises_without_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_ollama_chat(*_args, **_kwargs):
        return '{"name": 123}', {"provider": "test"}

    monkeypatch.setattr(ai_gateway, "ollama_chat", _fake_ollama_chat)

    with pytest.raises(AiOutputTechnicalError):
        ai_gateway.safe_ollama_json(
            model="dummy",
            system="sys",
            user="user",
            expected_schema={"name": "str"},
            fallback_payload=None,
        )
