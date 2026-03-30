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
    assert result["errors"][0]["code"] == "validation_error"
    assert result["summary"]["status"] == "partial_success"
    assert isinstance(result["quality_issues"], list)


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
    assert result["summary"]["status"] == "success"

    count = db_session.query(Product).count()
    assert count == 1


def test_csv_import_handles_utf8_bom_header(db_session: Session) -> None:
    result = import_products_from_csv(
        db_session,
        config=CsvImportConfig(
            csv_text="\ufefftitle;currency\nPhone;EUR\n",
            column_map={"title": "title", "currency": "currency"},
            dry_run=True,
        ),
    )

    assert result["rows_total"] == 1
    assert result["ready"] == 1
    assert result["errors"] == []


def test_csv_import_normalizes_manufacturer_and_category(db_session: Session) -> None:
    result = import_products_from_csv(
        db_session,
        config=CsvImportConfig(
            csv_text="title;brand;model;category;currency\ncanon r6 body;hewlett packard;R6;Kamera;EUR\n",
            column_map={
                "title": "title",
                "brand": "brand",
                "model": "model",
                "category": "category",
                "currency": "currency",
            },
            dry_run=True,
        ),
    )

    assert result["ready"] == 1
    assert result["preview"][0]["brand"] == "HP"
    assert result["preview"][0]["category"] == "camera"
    codes = {issue.get("code") for issue in result["quality_issues"]}
    assert "manufacturer_normalized" in codes
    assert "category_normalized" in codes


def test_csv_import_domain_required_fields_for_camera(db_session: Session) -> None:
    result = import_products_from_csv(
        db_session,
        config=CsvImportConfig(
            csv_text="title;brand;category;currency\nCamera Body;Sony;camera;EUR\n",
            column_map={
                "title": "title",
                "brand": "brand",
                "category": "category",
                "currency": "currency",
            },
            dry_run=True,
        ),
    )

    assert result["ready"] == 0
    assert result["summary"]["status"] == "failed"
    assert any(error.get("code") == "missing_domain_required_fields" for error in result["errors"])


def test_csv_import_reference_data_validation_marks_invalid_currency(db_session: Session) -> None:
    result = import_products_from_csv(
        db_session,
        config=CsvImportConfig(
            csv_text="title;brand;model;category;currency\nPhone X;Apple;X;phone;ABC\n",
            column_map={
                "title": "title",
                "brand": "brand",
                "model": "model",
                "category": "category",
                "currency": "currency",
            },
            dry_run=True,
        ),
    )

    assert result["ready"] == 0
    assert any(error.get("code") == "invalid_currency_reference" for error in result["errors"])
    assert result["summary"]["data_quality_errors"] >= 1


def test_csv_import_reference_data_unknown_category_is_visible_warning(db_session: Session) -> None:
    result = import_products_from_csv(
        db_session,
        config=CsvImportConfig(
            csv_text="title;brand;model;category;currency\nCustom Device;BrandY;M1;special_rig;EUR\n",
            column_map={
                "title": "title",
                "brand": "brand",
                "model": "model",
                "category": "category",
                "currency": "currency",
            },
            dry_run=True,
        ),
    )

    assert result["ready"] == 1
    assert any(issue.get("code") == "unknown_category_reference" for issue in result["quality_issues"])
    assert result["summary"]["data_quality_warnings"] >= 1


def test_csv_import_requires_mapping_for_required_fields(db_session: Session) -> None:
    with pytest.raises(ValueError, match="missing_required_field_mappings"):
        import_products_from_csv(
            db_session,
            config=CsvImportConfig(
                csv_text="brand\nSony\n",
                column_map={"brand": "brand"},
                dry_run=True,
            ),
        )


def test_csv_import_skips_duplicates_with_idempotency(db_session: Session) -> None:
    db_session.add(Product(title="Canon R6", brand="Canon", model="R6", currency="EUR"))
    db_session.commit()

    result = import_products_from_csv(
        db_session,
        config=CsvImportConfig(
            csv_text="title;brand;model;currency\nCanon R6;Canon;R6;EUR\nCanon R6;Canon;R6;EUR\n",
            column_map={
                "title": "title",
                "brand": "brand",
                "model": "model",
                "currency": "currency",
            },
            dry_run=False,
            idempotency_mode="skip_existing",
        ),
    )

    assert result["rows_total"] == 2
    assert result["inserted"] == 0
    assert result["skipped"] == 2
    assert len(result["row_warnings"]) >= 2
    assert any(w.get("code") == "already_exists" for w in result["row_warnings"])
    assert result["summary"]["status"] == "partial_success"


def test_csv_import_non_atomic_partial_success(db_session: Session) -> None:
    result = import_products_from_csv(
        db_session,
        config=CsvImportConfig(
            csv_text="title;currency\nValid Item;EUR\n;EUR\n",
            column_map={"title": "title", "currency": "currency"},
            dry_run=False,
            continue_on_error=True,
        ),
    )

    assert result["rows_total"] == 2
    assert result["inserted"] == 1
    assert len(result["errors"]) == 1
    assert result["summary"]["status"] == "partial_success"
    assert db_session.query(Product).count() == 1
