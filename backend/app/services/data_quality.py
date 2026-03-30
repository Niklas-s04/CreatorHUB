from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.product import Product

VALID_CURRENCIES = {"EUR", "USD", "GBP", "CHF"}
REFERENCE_CATEGORIES = {
    "camera",
    "console",
    "phone",
    "tablet",
    "laptop",
    "audio",
    "accessory",
    "gaming",
    "other",
}
CATEGORY_ALIASES = {
    "cameras": "camera",
    "kamera": "camera",
    "kameras": "camera",
    "smartphone": "phone",
    "smartphones": "phone",
    "handy": "phone",
    "notebook": "laptop",
    "headphones": "audio",
    "kopfh\u00f6rer": "audio",
    "zubeh\u00f6r": "accessory",
    "zubehoer": "accessory",
    "spielekonsole": "console",
}
BRAND_ALIASES = {
    "hp": "HP",
    "hewlett packard": "HP",
    "hewlett-packard": "HP",
    "hewlett packard enterprise": "HPE",
    "h p": "HP",
    "apple inc": "Apple",
    "samsung electronics": "Samsung",
    "sony corporation": "Sony",
    "nintendo co ltd": "Nintendo",
}
DOMAIN_REQUIRED_FIELDS: dict[str, set[str]] = {
    "default": {"title", "currency"},
    "camera": {"title", "brand", "model", "currency"},
    "console": {"title", "brand", "model", "currency"},
    "phone": {"title", "brand", "model", "currency"},
    "tablet": {"title", "brand", "model", "currency"},
    "laptop": {"title", "brand", "model", "currency"},
}


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = _collapse_spaces(str(value))
    return text or None


def _slug(value: str) -> str:
    text = value.lower().strip()
    text = re.sub(r"\s+", "_", text)
    return re.sub(r"[^a-z0-9_\-]", "", text)


def normalize_product_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized = dict(payload)
    issues: list[dict[str, Any]] = []

    title = _clean_text(normalized.get("title"))
    if title is not None:
        normalized["title"] = title

    brand = _clean_text(normalized.get("brand"))
    if brand is not None:
        alias_key = _slug(brand).replace("_", " ")
        normalized_brand = BRAND_ALIASES.get(alias_key)
        if normalized_brand is None:
            normalized_brand = brand
        elif normalized_brand != brand:
            issues.append(
                {
                    "severity": "warning",
                    "code": "manufacturer_normalized",
                    "message": f"Brand normalized from '{brand}' to '{normalized_brand}'",
                    "field": "brand",
                }
            )
        normalized["brand"] = normalized_brand

    model = _clean_text(normalized.get("model"))
    if model is not None:
        normalized["model"] = model

    category = _clean_text(normalized.get("category"))
    if category is not None:
        category_slug = _slug(category)
        canonical = CATEGORY_ALIASES.get(category_slug, category_slug)
        if canonical != category_slug:
            issues.append(
                {
                    "severity": "warning",
                    "code": "category_normalized",
                    "message": f"Category normalized from '{category}' to '{canonical}'",
                    "field": "category",
                }
            )
        normalized["category"] = canonical

    currency = _clean_text(normalized.get("currency"))
    if currency is not None:
        normalized["currency"] = currency.upper()

    serial_number = _clean_text(normalized.get("serial_number"))
    if serial_number is not None:
        normalized["serial_number"] = serial_number.upper()

    return normalized, issues


def infer_product_domain(payload: dict[str, Any]) -> str:
    category = str(payload.get("category") or "").strip().lower()
    if category in DOMAIN_REQUIRED_FIELDS:
        return category
    if category in REFERENCE_CATEGORIES:
        return category
    return "default"


def build_duplicate_key(payload: dict[str, Any], *, key_fields: list[str]) -> str | None:
    parts: list[str] = []
    for field in key_fields:
        value = payload.get(field)
        if value is None:
            parts.append("")
            continue
        text = _clean_text(value)
        parts.append((text or "").lower())
    if not any(parts):
        return None
    return "|".join(parts)


def find_existing_product_by_fields(
    db: Session,
    *,
    payload: dict[str, Any],
    key_fields: list[str],
) -> Product | None:
    conditions = []
    for field in key_fields:
        value = payload.get(field)
        if value is None or value == "":
            continue
        conditions.append(getattr(Product, field) == value)

    if not conditions:
        return None

    qry = db.query(Product)
    for condition in conditions:
        qry = qry.filter(condition)
    return qry.first()


def validate_product_reference_data(payload: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    currency = str(payload.get("currency") or "").strip().upper()
    if currency and currency not in VALID_CURRENCIES:
        issues.append(
            {
                "severity": "error",
                "code": "invalid_currency_reference",
                "message": f"Unsupported currency '{currency}'",
                "field": "currency",
            }
        )

    category = str(payload.get("category") or "").strip().lower()
    if category and category not in REFERENCE_CATEGORIES:
        issues.append(
            {
                "severity": "warning",
                "code": "unknown_category_reference",
                "message": f"Category '{category}' is not in reference data",
                "field": "category",
            }
        )

    return issues


def validate_domain_required_fields(payload: dict[str, Any], *, domain: str) -> list[dict[str, Any]]:
    required = DOMAIN_REQUIRED_FIELDS.get(domain, DOMAIN_REQUIRED_FIELDS["default"])
    missing = sorted(
        [
            field
            for field in required
            if payload.get(field) is None or str(payload.get(field)).strip() == ""
        ]
    )
    if not missing:
        return []

    return [
        {
            "severity": "error",
            "code": "missing_domain_required_fields",
            "message": f"Missing required fields for domain '{domain}': {', '.join(missing)}",
            "field": ",".join(missing),
        }
    ]
