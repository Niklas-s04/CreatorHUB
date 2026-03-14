from __future__ import annotations

import hashlib
import os
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests
from PIL import Image

from app.core.config import settings


@dataclass
class StoredFile:
    local_path: str
    size_bytes: int
    sha256: str
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
    _ensure_dirs()
    safe_name = "".join([c for c in filename if c.isalnum() or c in "._- "]).strip().replace(" ", "_")
    sha = sha256_bytes(data)

    folder = Path(settings.UPLOADS_DIR) / owner_folder
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sha}_{safe_name}"
    path.write_bytes(data)

    mime, _ = mimetypes.guess_type(str(path))
    width, height, perceptual_hash = _image_metadata(path)

    return StoredFile(
        local_path=str(path),
        size_bytes=len(data),
        sha256=sha,
        width=width,
        height=height,
        mime_type=mime,
        perceptual_hash=perceptual_hash,
    )


def cache_download(url: str, subdir: str = "web") -> StoredFile:
    _ensure_dirs()
    r = requests.get(url, timeout=30, headers={"User-Agent": "creator-suite/1.0"})
    r.raise_for_status()
    data = r.content
    sha = sha256_bytes(data)

    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1]
    if not ext:
        ext = ".bin"

    folder = Path(settings.CACHE_DIR) / subdir
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sha}{ext}"
    if not path.exists():
        path.write_bytes(data)

    mime, _ = mimetypes.guess_type(str(path))
    width, height, perceptual_hash = _image_metadata(path)

    return StoredFile(
        local_path=str(path),
        size_bytes=len(data),
        sha256=sha,
        width=width,
        height=height,
        mime_type=mime,
        perceptual_hash=perceptual_hash,
    )


def ensure_thumbnail(image_path: str, max_size: int = 512) -> str:
    _ensure_dirs()
    src = Path(image_path)
    thumb_dir = Path(settings.CACHE_DIR) / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / f"{src.stem}_thumb{src.suffix}"
    if thumb_path.exists():
        return str(thumb_path)

    with Image.open(src) as img:
        img.thumbnail((max_size, max_size))
        img.save(thumb_path)

    return str(thumb_path)
