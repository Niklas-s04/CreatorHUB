from __future__ import annotations

import warnings
from io import BytesIO

import pytest
from PIL import Image

from app.core.config import settings
from app.services.storage import validate_upload_file


def _png_bytes(width: int = 2, height: int = 2) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(12, 34, 56)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_magic_byte_validation() -> None:
    with pytest.raises(ValueError, match="Only safe image formats"):
        validate_upload_file("image.png", b"%PDF-1.7\n%%EOF", "image")


def test_image_dimension_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "UPLOAD_MAX_IMAGE_WIDTH", 1)

    with pytest.raises(ValueError, match="dimensions exceed limit"):
        validate_upload_file("image.png", _png_bytes(width=2, height=1), "image")


def test_image_bomb_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "UPLOAD_MAX_IMAGE_PIXELS", 1)

    with pytest.raises(ValueError, match="pixel count|validation failed"):
        validate_upload_file("image.png", _png_bytes(width=2, height=2), "image")


def test_image_validation_does_not_use_deprecated_pillow_pixel_api() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        result = validate_upload_file("image.png", _png_bytes(), "image")

    assert result.perceptual_hash is not None
