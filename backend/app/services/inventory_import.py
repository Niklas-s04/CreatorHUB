from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.product import ProductCreate

ALLOWED_FIELDS = set(ProductCreate.model_fields.keys())
MAX_PREVIEW_ROWS = 10


@dataclass
class CsvImportConfig:
    csv_text: str
    delimiter: str = ";"
    quotechar: str = '"'
    column_map: dict[str, str] | None = None
    defaults: dict[str, Any] | None = None
    dry_run: bool = True


def _format_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x is not None)
        prefix = f"{loc}: " if loc else ""
        parts.append(f"{prefix}{err.get('msg', 'invalid value')}")
    return "; ".join(parts) if parts else str(exc)


def import_products_from_csv(db: Session, *, config: CsvImportConfig) -> dict[str, Any]:
    if not config.column_map:
        raise ValueError("column_map_required")

    invalid_targets = [field for field in config.column_map.keys() if field not in ALLOWED_FIELDS]
    if invalid_targets:
        raise ValueError(f"unknown_target_fields: {', '.join(invalid_targets)}")

    delimiter = (config.delimiter or ";").strip() or ";"
    quotechar = (config.quotechar or '\"')[:1]

    text = (config.csv_text or "").strip()
    if not text:
        return {
            "dry_run": config.dry_run,
            "rows_total": 0,
            "ready": 0,
            "inserted": 0,
            "errors": [],
            "preview": [],
            "warnings": ["CSV data is empty"],
        }

    reader = csv.DictReader(StringIO(text), delimiter=delimiter, quotechar=quotechar)
    if not reader.fieldnames:
        raise ValueError("missing_header_row")

    warnings: list[str] = []
    missing_columns = [col for col in config.column_map.values() if col not in reader.fieldnames]
    if missing_columns:
        warnings.append(f"Missing columns in CSV: {', '.join(missing_columns)}")

    defaults = {k: v for k, v in (config.defaults or {}).items() if k in ALLOWED_FIELDS}
    dropped_defaults = set((config.defaults or {}).keys()) - ALLOWED_FIELDS
    if dropped_defaults:
        warnings.append(f"Ignored defaults for unknown fields: {', '.join(sorted(dropped_defaults))}")

    rows_total = 0
    success_rows = 0
    preview: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for row_index, row in enumerate(reader, start=2):
        rows_total += 1

        merged: dict[str, Any] = defaults.copy()
        for field, column in config.column_map.items():
            raw_value = row.get(column)
            if raw_value is None:
                continue
            value = raw_value.strip()
            if value == "":
                continue
            merged[field] = value

        try:
            product_payload = ProductCreate(**merged).model_dump()
        except ValidationError as exc:
            errors.append({"row": row_index, "error": _format_validation_error(exc)})
            continue

        success_rows += 1
        if config.dry_run and len(preview) < MAX_PREVIEW_ROWS:
            preview.append(product_payload)

        if not config.dry_run:
            product = Product(**product_payload)
            product.status_changed_at = now
            db.add(product)

    if not config.dry_run:
        if success_rows:
            db.commit()
        else:
            db.rollback()

    return {
        "dry_run": config.dry_run,
        "rows_total": rows_total,
        "ready": success_rows,
        "inserted": success_rows if not config.dry_run else 0,
        "errors": errors,
        "preview": preview,
        "warnings": warnings,
    }
