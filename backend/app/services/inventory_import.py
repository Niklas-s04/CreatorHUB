from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.product import ProductCreate
from app.services.data_quality import (
    build_duplicate_key,
    find_existing_product_by_fields,
    infer_product_domain,
    normalize_product_payload,
    validate_domain_required_fields,
    validate_product_reference_data,
)

ALLOWED_FIELDS = set(ProductCreate.model_fields.keys())
REQUIRED_FIELDS = {
    name for name, field in ProductCreate.model_fields.items() if bool(field.is_required())
}
MAX_PREVIEW_ROWS = 10
DEFAULT_IDEMPOTENCY_FIELDS: tuple[str, ...] = ("title", "brand", "model", "serial_number")


@dataclass
class CsvImportConfig:
    csv_text: str
    delimiter: str = "auto"
    quotechar: str = '"'
    column_map: dict[str, str] | None = None
    defaults: dict[str, Any] | None = None
    dry_run: bool = True
    idempotency_mode: Literal["none", "skip_existing"] = "skip_existing"
    idempotency_fields: list[str] | None = None
    continue_on_error: bool = True


def _format_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x is not None)
        prefix = f"{loc}: " if loc else ""
        parts.append(f"{prefix}{err.get('msg', 'invalid value')}")
    return "; ".join(parts) if parts else str(exc)


def _normalize_csv_text(raw: str) -> str:
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.strip()


def _canonical(value: str) -> str:
    return (value or "").strip().lower()


def _resolve_dialect(text: str, delimiter: str, quotechar: str) -> tuple[str, str]:
    selected_delimiter = (delimiter or "").strip()
    if selected_delimiter.lower() == "auto":
        selected_delimiter = ""
    selected_quotechar = (quotechar or '"')[:1] or '"'

    if selected_delimiter:
        return selected_delimiter, selected_quotechar

    sample = "\n".join(text.splitlines()[:10])[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t,|")
        guessed_delimiter = getattr(dialect, "delimiter", ";") or ";"
    except csv.Error:
        guessed_delimiter = ";"
    return guessed_delimiter, selected_quotechar


def import_products_from_csv(db: Session, *, config: CsvImportConfig) -> dict[str, Any]:
    if not config.column_map:
        raise ValueError("column_map_required")

    invalid_targets = [field for field in config.column_map.keys() if field not in ALLOWED_FIELDS]
    if invalid_targets:
        raise ValueError(f"unknown_target_fields: {', '.join(invalid_targets)}")

    idempotency_mode = (config.idempotency_mode or "none").strip().lower()
    if idempotency_mode not in {"none", "skip_existing"}:
        raise ValueError("invalid_idempotency_mode")

    raw_idempotency_fields = config.idempotency_fields or list(DEFAULT_IDEMPOTENCY_FIELDS)
    idempotency_fields = [field for field in raw_idempotency_fields if field in ALLOWED_FIELDS]
    if raw_idempotency_fields and not idempotency_fields:
        raise ValueError("idempotency_fields_invalid")

    defaults = {k: v for k, v in (config.defaults or {}).items() if k in ALLOWED_FIELDS}
    dropped_defaults = set((config.defaults or {}).keys()) - ALLOWED_FIELDS

    missing_required_mappings = [
        field
        for field in REQUIRED_FIELDS
        if field not in defaults and field not in set(config.column_map.keys())
    ]
    if missing_required_mappings:
        raise ValueError(
            f"missing_required_field_mappings: {', '.join(sorted(missing_required_mappings))}"
        )

    text = _normalize_csv_text(config.csv_text)
    if not text:
        return {
            "dry_run": config.dry_run,
            "rows_total": 0,
            "ready": 0,
            "inserted": 0,
            "skipped": 0,
            "errors": [],
            "row_warnings": [],
            "preview": [],
            "warnings": ["CSV data is empty"],
            "summary": {
                "status": "failed",
                "successes": 0,
                "warnings": 1,
                "errors": 0,
            },
            "idempotency": {
                "mode": idempotency_mode,
                "key_fields": idempotency_fields,
                "strategy": "skip_existing_records" if idempotency_mode == "skip_existing" else "none",
            },
        }

    delimiter, quotechar = _resolve_dialect(text, config.delimiter, config.quotechar)

    try:
        reader = csv.DictReader(StringIO(text), delimiter=delimiter, quotechar=quotechar)
    except csv.Error as exc:
        raise ValueError(f"invalid_csv_format: {exc}") from exc

    if not reader.fieldnames:
        raise ValueError("missing_header_row")

    warnings: list[str] = []
    row_warnings: list[dict[str, Any]] = []

    raw_headers = [str(header or "") for header in reader.fieldnames]
    normalized_headers = [_canonical(header) for header in raw_headers]
    if any(not header for header in normalized_headers):
        raise ValueError("invalid_header_row: contains empty header")

    duplicates = sorted(
        {
            header
            for header in normalized_headers
            if normalized_headers.count(header) > 1
        }
    )
    if duplicates:
        raise ValueError(f"duplicate_header_columns: {', '.join(duplicates)}")

    header_lookup = {_canonical(header): header for header in raw_headers}
    mapped_columns = {_canonical(column): column for column in config.column_map.values()}
    missing_columns = [
        column
        for canonical, column in mapped_columns.items()
        if canonical not in header_lookup
    ]
    if missing_columns:
        raise ValueError(f"missing_csv_columns: {', '.join(sorted(missing_columns))}")

    if dropped_defaults:
        warnings.append(
            f"Ignored defaults for unknown fields: {', '.join(sorted(dropped_defaults))}"
        )

    unknown_csv_columns = sorted(
        [header for header in raw_headers if _canonical(header) not in mapped_columns]
    )
    if unknown_csv_columns:
        warnings.append(f"Unused CSV columns: {', '.join(unknown_csv_columns)}")

    rows_total = 0
    ready_rows = 0
    inserted_rows = 0
    skipped_rows = 0
    preview: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    quality_issues: list[dict[str, Any]] = []
    seen_idempotency_keys: set[str] = set()
    seen_duplicate_keys: set[str] = set()
    now = datetime.now(timezone.utc)

    for row_index, row in enumerate(reader, start=2):
        rows_total += 1

        if None in row:
            errors.append(
                {
                    "row": row_index,
                    "code": "invalid_column_count",
                    "error": "Row has more columns than header",
                    "values": {"extra": row.get(None)},
                }
            )
            if not config.continue_on_error:
                break
            continue

        merged: dict[str, Any] = defaults.copy()
        for field, column in config.column_map.items():
            raw_header = header_lookup.get(_canonical(column), column)
            raw_value = row.get(raw_header)
            if raw_value is None:
                continue
            value = raw_value.strip()
            if value == "":
                continue
            merged[field] = value

        merged, normalization_issues = normalize_product_payload(merged)
        for issue in normalization_issues:
            payload = {"row": row_index, **issue}
            quality_issues.append(payload)
            row_warnings.append(payload)

        try:
            product_payload = ProductCreate(**merged).model_dump()
        except ValidationError as exc:
            errors.append(
                {
                    "row": row_index,
                    "code": "validation_error",
                    "error": _format_validation_error(exc),
                    "values": {k: row.get(k) for k in row.keys() if isinstance(k, str)},
                }
            )
            if not config.continue_on_error:
                break
            continue

        domain = infer_product_domain(product_payload)
        domain_issues = validate_domain_required_fields(product_payload, domain=domain)
        reference_issues = validate_product_reference_data(product_payload)

        for issue in [*domain_issues, *reference_issues]:
            issue_payload = {"row": row_index, "domain": domain, **issue}
            quality_issues.append(issue_payload)
            if issue.get("severity") == "error":
                errors.append(
                    {
                        "row": row_index,
                        "code": str(issue.get("code") or "data_quality_error"),
                        "error": str(issue.get("message") or "data quality error"),
                        "field": issue.get("field"),
                    }
                )
            else:
                row_warnings.append(
                    {
                        "row": row_index,
                        "code": str(issue.get("code") or "data_quality_warning"),
                        "warning": str(issue.get("message") or "data quality warning"),
                        "field": issue.get("field"),
                    }
                )

        if any(issue.get("severity") == "error" for issue in domain_issues + reference_issues):
            if not config.continue_on_error:
                break
            continue

        duplicate_key = build_duplicate_key(product_payload, key_fields=idempotency_fields)
        if duplicate_key and duplicate_key in seen_duplicate_keys:
            row_warnings.append(
                {
                    "row": row_index,
                    "code": "duplicate_in_file",
                    "warning": "Potential duplicate row detected in current import",
                    "duplicate_key": duplicate_key,
                }
            )
            quality_issues.append(
                {
                    "row": row_index,
                    "severity": "warning",
                    "code": "duplicate_in_file",
                    "message": "Potential duplicate row detected in current import",
                    "domain": domain,
                }
            )
        if duplicate_key:
            seen_duplicate_keys.add(duplicate_key)

        if idempotency_mode == "skip_existing" and idempotency_fields:
            row_key = build_duplicate_key(product_payload, key_fields=idempotency_fields)
            if row_key and row_key in seen_idempotency_keys:
                skipped_rows += 1
                row_warnings.append(
                    {
                        "row": row_index,
                        "code": "duplicate_in_file",
                        "warning": "Duplicate row in same import batch skipped",
                        "idempotency_key": row_key,
                    }
                )
                continue
            existing = find_existing_product_by_fields(
                db,
                key_fields=idempotency_fields,
                payload=product_payload,
            )
            if existing is not None:
                skipped_rows += 1
                row_warnings.append(
                    {
                        "row": row_index,
                        "code": "already_exists",
                        "warning": "Existing product matched idempotency key; row skipped",
                        "entity_id": str(existing.id),
                    }
                )
                if row_key:
                    seen_idempotency_keys.add(row_key)
                continue
            if row_key:
                seen_idempotency_keys.add(row_key)

        ready_rows += 1
        if config.dry_run and len(preview) < MAX_PREVIEW_ROWS:
            preview.append(product_payload)

        if not config.dry_run:
            try:
                with db.begin_nested():
                    product = Product(**product_payload)
                    product.status_changed_at = now
                    db.add(product)
                    db.flush()
                inserted_rows += 1
            except Exception as exc:
                errors.append(
                    {
                        "row": row_index,
                        "code": "db_insert_error",
                        "error": exc.__class__.__name__,
                    }
                )
                if not config.continue_on_error:
                    break

    if not config.dry_run:
        if inserted_rows > 0:
            db.commit()
        else:
            db.rollback()

    error_count = len(errors)
    warning_count = len(warnings) + len(row_warnings)
    quality_warning_count = len([item for item in quality_issues if item.get("severity") == "warning"])
    quality_error_count = len([item for item in quality_issues if item.get("severity") == "error"])
    status = "success"
    if error_count > 0 and (ready_rows > 0 or inserted_rows > 0):
        status = "partial_success"
    elif error_count > 0 and inserted_rows == 0 and ready_rows == 0:
        status = "failed"
    elif rows_total > 0 and ready_rows == 0 and skipped_rows > 0:
        status = "partial_success"

    return {
        "dry_run": config.dry_run,
        "rows_total": rows_total,
        "ready": ready_rows,
        "inserted": inserted_rows if not config.dry_run else 0,
        "skipped": skipped_rows,
        "errors": errors,
        "row_warnings": row_warnings,
        "quality_issues": quality_issues,
        "preview": preview,
        "warnings": warnings,
        "summary": {
            "status": status,
            "successes": ready_rows,
            "warnings": warning_count,
            "errors": error_count,
            "data_quality_warnings": quality_warning_count,
            "data_quality_errors": quality_error_count,
        },
        "idempotency": {
            "mode": idempotency_mode,
            "key_fields": idempotency_fields,
            "strategy": "skip_existing_records" if idempotency_mode == "skip_existing" else "none",
        },
    }
