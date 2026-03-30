from __future__ import annotations

import re

MAX_LOG_EXCERPT = 500

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

PROMPT_INJECTION_PATTERNS = {
    "prompt_injection_override": re.compile(
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions|"
        r"disregard\s+(the\s+)?system\s+prompt|"
        r"you\s+are\s+now\s+(developer|system)",
        re.IGNORECASE,
    ),
    "prompt_injection_exfiltration": re.compile(
        r"reveal\s+(the\s+)?(system\s+prompt|hidden\s+instructions)|"
        r"print\s+(all\s+)?instructions|"
        r"show\s+internal\s+rules",
        re.IGNORECASE,
    ),
    "prompt_injection_tool_abuse": re.compile(
        r"call\s+(tool|function)|run\s+command|execute\s+shell|"
        r"open\s+url\s+and\s+submit",
        re.IGNORECASE,
    ),
}

FORBIDDEN_CONTENT_PATTERNS = {
    "forbidden_sensitive_payment": re.compile(
        r"send\s+(your\s+)?(iban|bank\s+details|card\s+number)|"
        r"prepay\s+via\s+(gift\s*card|crypto|bitcoin)",
        re.IGNORECASE,
    ),
    "forbidden_secret_request": re.compile(
        r"share\s+(your\s+)?password|send\s+(your\s+)?otp|mfa\s+code|\bpassword\b",
        re.IGNORECASE,
    ),
    "forbidden_legal_commitment": re.compile(
        r"legally\s+binding\s+guarantee|irrevocable\s+commitment",
        re.IGNORECASE,
    ),
}

RISKY_PHRASE_REWRITES = {
    re.compile(r"\bI\s+guarantee\b", re.IGNORECASE): "I can propose",
    re.compile(r"\blegally\s+binding\b", re.IGNORECASE): "subject to final agreement",
    re.compile(r"\bunconditional\s+acceptance\b", re.IGNORECASE): "preliminary alignment",
}


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


def detect_prompt_injection(text: str) -> list[str]:
    if not text:
        return []
    matches = []
    for name, pattern in PROMPT_INJECTION_PATTERNS.items():
        if pattern.search(text):
            matches.append(name)
    return sorted(set(matches))


def detect_forbidden_content(text: str) -> list[str]:
    if not text:
        return []
    matches = []
    for name, pattern in FORBIDDEN_CONTENT_PATTERNS.items():
        if pattern.search(text):
            matches.append(name)
    return sorted(set(matches))


def rewrite_risky_phrases(text: str) -> tuple[str, list[str]]:
    if not text:
        return text, []
    out = text
    rewrites: list[str] = []
    for pattern, replacement in RISKY_PHRASE_REWRITES.items():
        replaced = pattern.sub(replacement, out)
        if replaced != out:
            rewrites.append(pattern.pattern)
        out = replaced
    return out, rewrites


def redact_sensitive(text: str) -> str:
    out = text
    out = PII_PATTERNS["email_address"].sub("[EMAIL_REDACTED]", out)
    out = PII_PATTERNS["phone_number"].sub("[PHONE_REDACTED]", out)
    out = PII_PATTERNS["iban"].sub("[IBAN_REDACTED]", out)
    out = PII_PATTERNS["credit_card"].sub("[CARD_REDACTED]", out)
    out = URL_PATTERN.sub("[URL_REDACTED]", out)
    # Kurze normale Zahlen nicht übermäßig schwärzen.
    return out


def redact_for_logging(text: str, max_len: int = MAX_LOG_EXCERPT) -> str:
    redacted = redact_sensitive(text or "")
    compact = " ".join(redacted.split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3] + "..."
