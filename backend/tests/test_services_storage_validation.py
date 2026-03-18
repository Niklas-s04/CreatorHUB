from __future__ import annotations

import base64

import pytest

from app.core.config import settings
from app.services.storage import save_upload_validated

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9ylnRxkAAAAASUVORK5CYII="
)
VALID_PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


def test_rejects_archive_signatures(tmp_path) -> None:
    with pytest.raises(ValueError, match="Archive"):
        save_upload_validated(
            owner_folder="x",
            filename="archive.zip",
            data=b"PK\x03\x04abc",
            expected_kind="image",
            base_dir=str(tmp_path),
        )


def test_rejects_pdf_without_eof(tmp_path) -> None:
    with pytest.raises(ValueError, match="EOF"):
        save_upload_validated(
            owner_folder="x",
            filename="doc.pdf",
            data=b"%PDF-1.7\nmissing-eof",
            expected_kind="pdf",
            base_dir=str(tmp_path),
        )


def test_rejects_extension_mismatch_for_image(tmp_path) -> None:
    with pytest.raises(ValueError, match="extension"):
        save_upload_validated(
            owner_folder="x",
            filename="image.pdf",
            data=TINY_PNG,
            expected_kind="image",
            base_dir=str(tmp_path),
        )


def test_optional_malware_scan_blocks_eicar(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENABLE_OPTIONAL_MALWARE_SCAN", True)
    with pytest.raises(ValueError, match="Malware"):
        save_upload_validated(
            owner_folder="x",
            filename="evil.pdf",
            data=VALID_PDF + b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE",
            expected_kind="pdf",
            base_dir=str(tmp_path),
        )
