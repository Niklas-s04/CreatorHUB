from __future__ import annotations

import hashlib
import os
import secrets
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.outbound_http import request_outbound


@dataclass
class StoredFile:
    local_path: str
    size_bytes: int
    sha256: str
    safe_filename: str
    extension: str
    width: int | None = None
    height: int | None = None
    mime_type: str | None = None
    perceptual_hash: str | None = None


def _ensure_dirs() -> None:
    Path(settings.UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.CACHE_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.EXPORTS_DIR).mkdir(parents=True, exist_ok=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


ARCHIVE_SIGNATURES: tuple[bytes, ...] = (
    b"PK\x03\x04",  # zip
    b"Rar!\x1a\x07",  # rar
    b"\x1f\x8b\x08",  # gzip
    b"7z\xbc\xaf\x27\x1c",  # 7z
)

MAGIC_MIME_MAP: list[tuple[bytes, str, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"GIF87a", "image/gif", ".gif"),
    (b"GIF89a", "image/gif", ".gif"),
    (b"RIFF", "image/webp", ".webp"),
    (b"%PDF-", "application/pdf", ".pdf"),
]

SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _parse_extensions(raw: str) -> set[str]:
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def _sanitize_filename(name: str) -> str:
    base = os.path.basename((name or "file").strip())
    safe = SAFE_FILENAME_RE.sub("_", base).strip("._")
    return safe or "file"


def _detect_mime_and_ext(data: bytes) -> tuple[str | None, str | None]:
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    for signature, mime, ext in MAGIC_MIME_MAP:
        if data.startswith(signature):
            return mime, ext
    return None, None


def _is_archive_or_compressed(data: bytes) -> bool:
    for sig in ARCHIVE_SIGNATURES:
        if data.startswith(sig):
            return True
    return False


def _validate_pdf_content(data: bytes) -> None:
    if not data.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF signature")
    tail = data[-2048:] if len(data) > 2048 else data
    if b"%%EOF" not in tail:
        raise ValueError("Invalid PDF EOF marker")


def _validate_image_content(data: bytes) -> tuple[int, int, str]:
    Image.MAX_IMAGE_PIXELS = settings.UPLOAD_MAX_IMAGE_PIXELS
    try:
        with Image.open(BytesIO(data)) as img_verify:
            img_verify.verify()
    except Exception as exc:
        raise ValueError("Image signature validation failed") from exc

    try:
        with Image.open(BytesIO(data)) as img:
            img.load()
            width, height = img.size
            if width <= 0 or height <= 0:
                raise ValueError("Invalid image dimensions")
            if width > settings.UPLOAD_MAX_IMAGE_WIDTH or height > settings.UPLOAD_MAX_IMAGE_HEIGHT:
                raise ValueError("Image dimensions exceed limit")
            if width * height > settings.UPLOAD_MAX_IMAGE_PIXELS:
                raise ValueError("Image pixel count exceeds limit")
            phash = _average_hash(img.convert("RGB"))
            return width, height, phash
    except (Image.DecompressionBombError, UnidentifiedImageError) as exc:
        raise ValueError("Image validation failed") from exc


def _optional_malware_scan(data: bytes) -> None:
    if not settings.ENABLE_OPTIONAL_MALWARE_SCAN:
        return
    if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in data:
        raise ValueError("Malware scan failed")


def _image_metadata(path: Path) -> Tuple[int | None, int | None, str | None]:
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            width, height = img.size
            phash = _average_hash(img)
            return width, height, phash
    except Exception:
        return None, None, None


def _average_hash(img: Image.Image, hash_size: int = 8) -> str:
    gray = img.convert("L").resize((hash_size, hash_size), Image.LANCZOS)
    pixels = list(gray.getdata())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for idx, pixel in enumerate(pixels):
        if pixel >= avg:
            bits |= 1 << (len(pixels) - 1 - idx)
    width = hash_size * hash_size // 4
    return f"{bits:0{width}x}"


def save_upload(owner_folder: str, filename: str, data: bytes) -> StoredFile:
    return save_upload_validated(owner_folder=owner_folder, filename=filename, data=data, expected_kind="image")


def save_upload_validated(
    owner_folder: str,
    filename: str,
    data: bytes,
    expected_kind: str,
    base_dir: str | None = None,
) -> StoredFile:
    _ensure_dirs()
    safe_name = _sanitize_filename(filename)
    sha = sha256_bytes(data)

    if _is_archive_or_compressed(data):
        raise ValueError("Archive and compressed uploads are not allowed")

    if expected_kind not in {"image", "pdf"}:
        raise ValueError("Unsupported upload kind")

    original_ext = os.path.splitext(safe_name)[1].lower()
    detected_mime, detected_ext = _detect_mime_and_ext(data)
    if not detected_mime or not detected_ext:
        raise ValueError("Unsupported or unknown file signature")

    image_exts = _parse_extensions(settings.UPLOAD_ALLOWED_IMAGE_EXTENSIONS)
    pdf_exts = _parse_extensions(settings.UPLOAD_ALLOWED_PDF_EXTENSIONS)

    width: int | None = None
    height: int | None = None
    perceptual_hash: str | None = None

    if expected_kind == "image":
        if detected_mime not in {"image/png", "image/jpeg", "image/gif", "image/webp"}:
            raise ValueError("Only safe image formats are allowed")
        if detected_ext not in image_exts or (original_ext and original_ext not in image_exts):
            raise ValueError("File extension not allowed for image upload")
        if len(data) > settings.UPLOAD_MAX_IMAGE_BYTES:
            raise ValueError("Image exceeds max size")
        width, height, perceptual_hash = _validate_image_content(data)
    elif expected_kind == "pdf":
        if detected_mime != "application/pdf":
            raise ValueError("Only PDF allowed for pdf upload")
        if detected_ext not in pdf_exts or (original_ext and original_ext not in pdf_exts):
            raise ValueError("File extension not allowed for pdf upload")
        if len(data) > settings.UPLOAD_MAX_PDF_BYTES:
            raise ValueError("PDF exceeds max size")
        _validate_pdf_content(data)

    _optional_malware_scan(data)

    root = Path(base_dir or settings.UPLOADS_DIR)
    folder = root / owner_folder
    folder.mkdir(parents=True, exist_ok=True)
    storage_key = f"{sha[:20]}_{secrets.token_hex(8)}{detected_ext}"
    path = folder / storage_key
    path.write_bytes(data)

    mime = detected_mime

    return StoredFile(
        local_path=str(path),
        size_bytes=len(data),
        sha256=sha,
        safe_filename=safe_name,
        extension=detected_ext,
        width=width,
        height=height,
        mime_type=mime,
        perceptual_hash=perceptual_hash,
    )


def cache_download(url: str, subdir: str = "web", db: Session | None = None, expected_kind: str = "image") -> StoredFile:
    _ensure_dirs()
    response = request_outbound(
        url=url,
        method="GET",
        headers={"User-Agent": "creator-suite/1.0"},
        db=db,
        require_https=True,
        max_bytes=settings.OUTBOUND_MAX_RESPONSE_BYTES,
        max_redirects=1,
    )
    data = response.content
    parsed = urlparse(response.url)
    source_name = os.path.basename(parsed.path) or "download.bin"
    return save_upload_validated(
        owner_folder=subdir,
        filename=source_name,
        data=data,
        expected_kind=expected_kind,
        base_dir=settings.CACHE_DIR,
    )


def ensure_thumbnail(image_path: str, max_size: int = 512) -> str:
    _ensure_dirs()
    src = Path(image_path)
    thumb_dir = Path(settings.CACHE_DIR) / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / f"{src.stem}_thumb{src.suffix}"
    if thumb_path.exists():
        return str(thumb_path)

    try:
        with Image.open(src) as img:
            if img.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                raise ValueError("Unsupported thumbnail source format")
            img.thumbnail((max_size, max_size))
            img.save(thumb_path)
    except Exception as exc:
        raise ValueError("Thumbnail creation failed") from exc

    return str(thumb_path)
