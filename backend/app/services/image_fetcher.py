from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urljoin

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.outbound_http import request_outbound

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"

# Schlankes HTML-Parsing per Regex, bewusst einfach gehalten.
_OG_IMAGE_RE = re.compile(
    r"<meta[^>]+property=['\"]og:image['\"][^>]+content=['\"]([^'\"]+)['\"][^>]*>",
    re.IGNORECASE,
)
_TW_IMAGE_RE = re.compile(
    r"<meta[^>]+name=['\"]twitter:image(?::src)?['\"][^>]+content=['\"]([^'\"]+)['\"][^>]*>",
    re.IGNORECASE,
)
_IMG_TAG_RE = re.compile(
    r"<img[^>]+src=['\"]([^'\"]+)['\"][^>]*>",
    re.IGNORECASE,
)

# Einfacher Filter für offensichtliche Icons/Sprites.
_BAD_IMG_HINTS = ("sprite", "icon", "logo", "favicon", "data:")


def wikimedia_search_images(
    query: str, limit: int = 12, db: Session | None = None
) -> list[dict[str, Any]]:
    """Search Wikimedia Commons for file pages and return image info candidates."""
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,  # Namespace für Dateien in Wikimedia.
        "gsrlimit": min(limit, 50),
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "iiurlwidth": 800,
        "format": "json",
        "origin": "*",
    }
    response = request_outbound(
        url=WIKIMEDIA_API,
        method="GET",
        params=params,
        headers={"User-Agent": "creatorhub/1.0"},
        db=db,
        require_https=True,
    )
    data = response.json()
    pages = (data.get("query") or {}).get("pages") or {}
    out: list[dict[str, Any]] = []
    for _, page in pages.items():
        title = page.get("title")  # Beispiel: File:Something.jpg
        imageinfo = page.get("imageinfo") or []
        if not imageinfo:
            continue
        ii = imageinfo[0]
        ext = ii.get("extmetadata") or {}
        license_short = (ext.get("LicenseShortName") or {}).get("value")
        usage_terms = (ext.get("UsageTerms") or {}).get("value")
        attribution = (ext.get("Artist") or {}).get("value") or (ext.get("Credit") or {}).get(
            "value"
        )
        license_url = (ext.get("LicenseUrl") or {}).get("value")

        out.append(
            {
                "source": "wikimedia",
                "title": title,
                "image_url": ii.get("url"),
                "thumb_url": ii.get("thumburl") or ii.get("url"),
                "width": ii.get("width"),
                "height": ii.get("height"),
                "size_bytes": ii.get("size"),
                "license_type": license_short or usage_terms,
                "license_url": license_url,
                "attribution": attribution,
                "source_url": f"https://commons.wikimedia.org/?curid={page.get('pageid')}"
                if page.get("pageid")
                else None,
            }
        )
    return out[:limit]


def openverse_search_images(
    query: str, limit: int = 12, db: Session | None = None
) -> list[dict[str, Any]]:
    """Search Openverse (no key) for openly licensed images."""
    base = settings.OPENVERSE_API_BASE.rstrip("/")
    url = f"{base}/images"
    params = {
        "q": query,
        "page_size": min(limit, 50),
        # Bevorzugt brauchbare Lizenzklassen; Nutzung trotzdem selbst prüfen.
        # Openverse liefert Lizenztyp und Lizenz-URL pro Treffer.
        "license_type": "commercial,modification",
    }
    response = request_outbound(
        url=url,
        method="GET",
        params=params,
        headers={"User-Agent": "creatorhub/1.0"},
        db=db,
        require_https=True,
    )
    data = response.json()
    results = data.get("results") or []
    out: list[dict[str, Any]] = []
    for it in results:
        out.append(
            {
                "source": "openverse",
                "title": it.get("title"),
                "image_url": it.get("url"),  # Direkte Dateiadresse.
                "thumb_url": it.get("thumbnail") or it.get("url"),
                "width": it.get("width"),
                "height": it.get("height"),
                "size_bytes": it.get("filesize"),
                "license_type": it.get("license"),
                "license_url": it.get("license_url"),
                "attribution": _openverse_attribution(it),
                "source_url": it.get("foreign_landing_url") or it.get("detail_url"),
            }
        )
    return out[:limit]


def _openverse_attribution(it: dict[str, Any]) -> str | None:
    creator = it.get("creator")
    creator_url = it.get("creator_url")
    src = it.get("foreign_landing_url") or it.get("detail_url")
    if creator and creator_url:
        return f"{creator} ({creator_url})"
    if creator:
        return str(creator)
    if src:
        return str(src)
    return None


def opengraph_images_from_page(
    url: str, timeout: int = 20, db: Session | None = None
) -> list[dict[str, Any]]:
    """Extract likely hero images from a given page (OG/Twitter + a few <img> fallbacks).
    This does not imply license.
    """
    try:
        response = request_outbound(
            url=url,
            method="GET",
            headers={"User-Agent": "creatorhub/1.0"},
            db=db,
            require_https=True,
            timeout_read=timeout,
            max_bytes=min(settings.OUTBOUND_MAX_RESPONSE_BYTES, 2 * 1024 * 1024),
            max_redirects=1,
        )
        html = response.text or ""
    except Exception:
        return []

    base = url
    candidates: list[str] = []

    for regex in (_OG_IMAGE_RE, _TW_IMAGE_RE):
        m = regex.search(html)
        if m:
            candidates.append(m.group(1).strip())

    # Fallback: einige <img>-Quellen von der Seite sammeln.
    if len(candidates) < 3:
        for m in _IMG_TAG_RE.finditer(html):
            src = (m.group(1) or "").strip()
            if not src:
                continue
            if any(h in src.lower() for h in _BAD_IMG_HINTS):
                continue
            candidates.append(src)
            if len(candidates) >= 8:
                break

    # URLs normalisieren (relativ -> absolut).
    normalized: list[str] = []
    for c in candidates:
        normalized.append(_normalize_url(c, base=base))

    # Doppelte URLs entfernen.
    seen: set[str] = set()
    uniq = []
    for u in normalized:
        if not u:
            continue
        if u in seen:
            continue
        seen.add(u)
        uniq.append(u)

    out: list[dict[str, Any]] = []
    for img in uniq[:8]:
        out.append(
            {
                "source": "opengraph",
                "title": None,
                "image_url": img,
                "thumb_url": img,
                "width": None,
                "height": None,
                "size_bytes": None,
                "license_type": "unknown (verify)",
                "license_url": None,
                "attribution": url,
                "source_url": url,
            }
        )
    return out


def manufacturer_url_candidates(
    urls: Iterable[str], per_url_limit: int = 6, db: Session | None = None
) -> list[dict[str, Any]]:
    """User-provided manufacturer/product page URLs → extract likely images from each page.
    No keys, no search engine.
    """
    out: list[dict[str, Any]] = []
    for raw in urls:
        u = (raw or "").strip()
        if not u:
            continue
        if not (u.startswith("http://") or u.startswith("https://")):
            u = "https://" + u
        if u.startswith("http://"):
            u = "https://" + u[len("http://") :]
        items = opengraph_images_from_page(u, db=db)
        for it in items[:per_url_limit]:
            it["source"] = "manufacturer"
        out.extend(items[:per_url_limit])
    return out


def _normalize_url(u: str, base: str) -> str | None:
    u = (u or "").strip()
    if not u:
        return None
    # Protokollrelative URLs wie //cdn... behandeln.
    if u.startswith("//"):
        return "https:" + u
    # Absolute URL unverändert übernehmen.
    if u.startswith("http://") or u.startswith("https://"):
        return u
    # Relative URL gegen Basis auflösen.
    try:
        return urljoin(base, u)
    except Exception:
        return None
