from __future__ import annotations

from app.services.email_rules import MACHINE_READABLE_COMMUNICATION_RULES


def test_machine_readable_rules_define_trust_boundary() -> None:
    boundary = MACHINE_READABLE_COMMUNICATION_RULES.get("trust_boundary") or {}
    assert "trusted_inputs" in boundary
    assert "untrusted_inputs" in boundary
    assert "user_email_body" in (boundary.get("untrusted_inputs") or [])


def test_machine_readable_rules_define_forbidden_flags() -> None:
    flags = MACHINE_READABLE_COMMUNICATION_RULES.get("forbidden_content_flags") or []
    assert "forbidden_sensitive_payment" in flags
    assert "forbidden_secret_request" in flags
