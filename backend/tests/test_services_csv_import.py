from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.product import Product
from app.services.inventory_import import CsvImportConfig, import_products_from_csv

CSV_TEXT = "title;brand;currency\nLaptop;Lenovo;EUR\n;MissingTitle;EUR\n"


def test_csv_import_requires_column_map(db_session: Session) -> None:
    with pytest.raises(ValueError, match="column_map_required"):
        import_products_from_csv(
            db_session, config=CsvImportConfig(csv_text="title\nA", column_map=None)
        )


def test_csv_import_unknown_target_field(db_session: Session) -> None:
    with pytest.raises(ValueError, match="unknown_target_fields"):
        import_products_from_csv(
            db_session,
            config=CsvImportConfig(
                csv_text="x\nvalue",
                column_map={"not_a_real_field": "x"},
            ),
        )


def test_csv_import_empty_input_returns_warning(db_session: Session) -> None:
    result = import_products_from_csv(
        db_session,
        config=CsvImportConfig(csv_text="   ", column_map={"title": "title"}, dry_run=True),
    )

    assert result["rows_total"] == 0
    assert result["ready"] == 0
    assert result["inserted"] == 0
    assert "empty" in result["warnings"][0].lower()


def test_csv_import_dry_run_collects_preview_and_errors(db_session: Session) -> None:
    result = import_products_from_csv(
        db_session,
        config=CsvImportConfig(
            csv_text=CSV_TEXT,
            delimiter=";",
            column_map={"title": "title", "brand": "brand", "currency": "currency"},
            dry_run=True,
        ),
    )

    assert result["rows_total"] == 2
    assert result["ready"] == 1
    assert result["inserted"] == 0
    assert len(result["preview"]) == 1
    assert len(result["errors"]) == 1


def test_csv_import_persists_rows_when_not_dry_run(db_session: Session) -> None:
    result = import_products_from_csv(
        db_session,
        config=CsvImportConfig(
            csv_text="title;brand;currency\nCamera;Sony;EUR\n",
            delimiter=";",
            column_map={"title": "title", "brand": "brand", "currency": "currency"},
            dry_run=False,
        ),
    )

    assert result["rows_total"] == 1
    assert result["ready"] == 1
    assert result["inserted"] == 1

    count = db_session.query(Product).count()
    assert count == 1
