from __future__ import annotations

import re

PII_PATTERNS = {
    "phone_number": re.compile(
        r"\b(\+?\d{1,3}[\s-]?)?(\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}\b"
    ),
    "email_address": re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
}

RISK_KEYWORDS = {
    "binding_promise": ["verbindlich", "garantiere", "rechtsverbindlich", "unwiderruflich"],
    "scam_suspected": [
        "bitcoin",
        "gift card",
        "steam gift",
        "dringend",
        "sofort",
        "konto gesperrt",
        "password",
    ],
}

URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


def detect_pii(text: str) -> list[str]:
    flags = []
    for name, pat in PII_PATTERNS.items():
        if pat.search(text):
            flags.append(f"contains_{name}")
    return flags


def detect_risk_keywords(text: str) -> list[str]:
    t = text.lower()
    flags = []
    for name, kws in RISK_KEYWORDS.items():
        if any(kw in t for kw in kws):
            flags.append(name)
    if URL_PATTERN.search(text):
        flags.append("contains_links")
    return sorted(set(flags))


def redact_sensitive(text: str) -> str:
    out = text
    out = PII_PATTERNS["iban"].sub("[IBAN_REDACTED]", out)
    out = PII_PATTERNS["credit_card"].sub("[CARD_REDACTED]", out)
    # Kurze normale Zahlen nicht übermäßig schwärzen.
    return out
