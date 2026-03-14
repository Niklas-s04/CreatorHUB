from __future__ import annotations

import csv
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable, Optional

from app.core.config import settings
from app.models.product import Product, ProductTransaction, ProductValueHistory


def _fmt_date(d: Optional[date]) -> str:
    if not d:
        return ""
    return d.strftime("%Y-%m-%d")


def _fmt_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M")


def _fmt_money(x: Optional[Decimal | float | int]) -> str:
    if x is None:
        return ""
    try:
        v = Decimal(str(x))
    except Exception:
        return str(x)
    return format(v.normalize(), "f")


def _build_path(prefix: str) -> str:
    os.makedirs(settings.EXPORTS_DIR, exist_ok=True)
    filename = f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return os.path.join(settings.EXPORTS_DIR, filename)


def _write_csv(prefix: str, headers: list[str], rows: Iterable[list[str]]) -> str:
    path = _build_path(prefix)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(
            f,
            delimiter=";",
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
    return path


def export_products_csv(products: Iterable[Product]) -> str:
    """Export a tidy, readable, Excel-friendly CSV."""

    headers = [
        "Titel",
        "Marke",
        "Modell",
        "Kategorie",
        "Zustand",
        "Status",
        "Aktueller Wert",
        "Währung",
        "Kaufpreis",
        "Kaufdatum",
        "Lagerort",
        "Seriennummer",
        "Produkt-ID",
        "Erstellt (UTC)",
        "Aktualisiert (UTC)",
    ]

    def _rows() -> Iterable[list[str]]:
        for p in products:
            yield [
                p.title or "",
                p.brand or "",
                p.model or "",
                p.category or "",
                getattr(p.condition, "value", str(p.condition)),
                getattr(p.status, "value", str(p.status)),
                _fmt_money(getattr(p, "current_value", None)),
                getattr(p, "currency", "") or "",
                _fmt_money(getattr(p, "purchase_price", None)),
                _fmt_date(getattr(p, "purchase_date", None)),
                getattr(p, "storage_location", "") or "",
                getattr(p, "serial_number", "") or "",
                str(getattr(p, "id", "")),
                _fmt_dt(getattr(p, "created_at", None)),
                _fmt_dt(getattr(p, "updated_at", None)),
            ]

    return _write_csv("products", headers, _rows())


def export_transactions_csv(transactions: Iterable[ProductTransaction]) -> str:
    headers = [
        "Produkt-ID",
        "Produkt Titel",
        "Transaktionstyp",
        "Datum",
        "Betrag",
        "Währung",
        "Gegenpartei",
        "Notiz",
        "Angelegt (UTC)",
        "Aktualisiert (UTC)",
    ]

    def _rows() -> Iterable[list[str]]:
        for tx in transactions:
            product = getattr(tx, "product", None)
            yield [
                str(getattr(tx, "product_id", "")),
                getattr(product, "title", "") or "",
                getattr(tx.type, "value", str(tx.type)),
                _fmt_date(getattr(tx, "date", None)),
                _fmt_money(getattr(tx, "amount", None)),
                getattr(tx, "currency", "") or "",
                getattr(tx, "counterparty", "") or "",
                getattr(tx, "notes", "") or "",
                _fmt_dt(getattr(tx, "created_at", None)),
                _fmt_dt(getattr(tx, "updated_at", None)),
            ]

    return _write_csv("transactions", headers, _rows())


def export_value_history_csv(entries: Iterable[ProductValueHistory]) -> str:
    headers = [
        "Produkt-ID",
        "Produkt Titel",
        "Datum",
        "Wert",
        "Währung",
        "Quelle",
        "Angelegt (UTC)",
        "Aktualisiert (UTC)",
    ]

    def _rows() -> Iterable[list[str]]:
        for entry in entries:
            product = getattr(entry, "product", None)
            yield [
                str(getattr(entry, "product_id", "")),
                getattr(product, "title", "") or "",
                _fmt_date(getattr(entry, "date", None)),
                _fmt_money(getattr(entry, "value", None)),
                getattr(entry, "currency", "") or "",
                getattr(entry.source, "value", str(entry.source)),
                _fmt_dt(getattr(entry, "created_at", None)),
                _fmt_dt(getattr(entry, "updated_at", None)),
            ]

    return _write_csv("value_history", headers, _rows())
