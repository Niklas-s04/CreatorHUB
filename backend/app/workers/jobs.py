from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.product import Product
from app.models.asset import Asset, AssetOwnerType, AssetKind, AssetSource, AssetReviewState
from app.models.ai_runs import AiRun
from app.services.image_fetcher import (
    wikimedia_search_images,
    openverse_search_images,
    manufacturer_url_candidates,
    opengraph_images_from_page,
)
from app.services.storage import cache_download
from app.services.image_scoring import score_image
from app.core.config import settings


def _build_query(p: Product) -> str:
    parts = [p.brand, p.model, p.title]
    parts = [x.strip() for x in parts if x and x.strip()]
    q = " ".join(parts)
    # Suchbegriff um einen Bildhinweis ergänzen.
    return f"{q} product photo" if q else "product photo"


def _parse_sources(source: str) -> list[str]:
    s = (source or "").strip().lower()
    if not s or s == "auto":
        s = settings.IMAGE_HUNT_DEFAULT_SOURCES
    parts = [p.strip() for p in s.split(",") if p.strip()]
    # Quellen normalisieren und auf bekannte Werte begrenzen.
    known = {"wikimedia", "openverse", "manufacturer", "opengraph"}
    out = [p for p in parts if p in known]
    return out or ["wikimedia"]


def _hex_hamming_distance(a: str, b: str) -> int:
    if not a or not b:
        return 64
    try:
        return (int(a, 16) ^ int(b, 16)).bit_count()
    except Exception:
        return 64


def _find_perceptual_duplicate(existing: list[Asset], candidate_hash: str, threshold: int = 6) -> tuple[Asset, int] | None:
    if not candidate_hash:
        return None
    best: tuple[Asset, int] | None = None
    for item in existing:
        if not item.perceptual_hash:
            continue
        dist = _hex_hamming_distance(candidate_hash, item.perceptual_hash)
        if dist <= threshold:
            if best is None or dist < best[1]:
                best = (item, dist)
                if dist == 0:
                    break
    return best


MIN_IMAGE_WIDTH = 900
MIN_IMAGE_HEIGHT = 700
MIN_ASPECT_RATIO = 0.6
MAX_ASPECT_RATIO = 1.85
MIN_BACKGROUND_SCORE = 0.3
MIN_OVERALL_SCORE = 0.4


def image_hunt_job(product_id: str, query: str | None = None, max_results: int = 12, source: str = "auto") -> dict[str, Any]:
    db: Session = SessionLocal()
    try:
        p = db.query(Product).filter(Product.id == product_id).first()
        if not p:
            return {"error": "product_not_found"}

        q = (query or "").strip() or _build_query(p)

        sources = _parse_sources(source)
        per = max(1, max_results // max(1, len(sources)))
        # Restkontingent der ersten Quelle zuweisen.
        remainder = max_results - (per * len(sources))

        candidates: list[dict[str, Any]] = []
        for i, src in enumerate(sources):
            lim = per + (remainder if i == 0 else 0)
            if src == "wikimedia":
                candidates.extend(wikimedia_search_images(q, limit=lim, db=db))
            elif src == "openverse":
                candidates.extend(openverse_search_images(q, limit=lim, db=db))
            elif src == "manufacturer":
                if q.startswith("http://") or q.startswith("https://"):
                    candidates.extend(manufacturer_url_candidates([q], per_url_limit=lim, db=db))
            elif src == "opengraph":
                # OpenGraph braucht URLs; bei URL-ähnlicher Query als Fallback verwenden.
                if q.startswith("http://") or q.startswith("https://"):
                    candidates.extend(opengraph_images_from_page(q, db=db))
            else:
                continue

        if not candidates:
            return {"query": q, "candidates": [], "best": [], "warning": "no_candidates (check sources/config)"}

        results: list[dict[str, Any]] = []
        quality_rejections = {
            "missing_dimensions": 0,
            "low_resolution": 0,
            "bad_aspect_ratio": 0,
            "spec_sheet": 0,
            "low_background": 0,
            "low_score": 0,
        }
        skipped_duplicates = 0
        existing_assets = db.query(Asset).filter(
            Asset.owner_type == AssetOwnerType.product,
            Asset.owner_id == p.id,
            Asset.kind == AssetKind.image,
        ).all()
        existing_by_hash = {a.hash: a for a in existing_assets if a.hash}

        seen_url: set[str] = set()
        for c in candidates:
            url = c.get("thumb_url") or c.get("image_url")
            if not url:
                continue
            # Mehrfachdownloads bei identischen URLs vermeiden.
            if url in seen_url:
                continue
            seen_url.add(url)

            stored = cache_download(url, subdir="web", db=db)

            duplicate_asset = existing_by_hash.get(stored.sha256)
            if not duplicate_asset:
                similar = _find_perceptual_duplicate(existing_assets, stored.perceptual_hash or "")
                if similar:
                    duplicate_asset, _ = similar

            if duplicate_asset:
                skipped_duplicates += 1
                continue

            width = stored.width or c.get("width")
            height = stored.height or c.get("height")
            if not width or not height:
                quality_rejections["missing_dimensions"] += 1
                continue

            width = int(width)
            height = int(height)
            if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                quality_rejections["low_resolution"] += 1
                continue

            aspect_ratio = width / height if height else 0
            if aspect_ratio < MIN_ASPECT_RATIO or aspect_ratio > MAX_ASPECT_RATIO:
                quality_rejections["bad_aspect_ratio"] += 1
                continue

            if not stored.local_path:
                quality_rejections["missing_dimensions"] += 1
                continue

            score = score_image(Path(stored.local_path))
            if score.spec_sheet:
                quality_rejections["spec_sheet"] += 1
                continue
            if score.background_score < MIN_BACKGROUND_SCORE:
                quality_rejections["low_background"] += 1
                continue
            if score.score < MIN_OVERALL_SCORE:
                quality_rejections["low_score"] += 1
                continue

            asset = Asset(
                owner_type=AssetOwnerType.product,
                owner_id=p.id,
                kind=AssetKind.image,
                source=AssetSource.web,
                url=c.get("image_url"),
                local_path=stored.local_path,
                title=c.get("title"),
                license_type=c.get("license_type"),
                attribution=c.get("attribution"),
                source_name=c.get("source"),
                source_url=c.get("source_url"),
                license_url=c.get("license_url"),
                fetched_at=datetime.now(timezone.utc),
                width=width,
                height=height,
                size_bytes=stored.size_bytes or c.get("size_bytes"),
                hash=stored.sha256,
                perceptual_hash=stored.perceptual_hash,
                review_state=AssetReviewState.pending,
                is_primary=False,
            )
            db.add(asset)
            db.commit()
            db.refresh(asset)

            existing_assets.append(asset)
            if asset.hash:
                existing_by_hash[asset.hash] = asset

            score_dict = score.to_dict()
            results.append({
                "asset_id": str(asset.id),
                "score": score_dict["score"],
                "reason": score_dict["reason"],
                "spec_sheet": score_dict["spec_sheet"],
                "background_score": score_dict["background_score"],
                "white_ratio": score_dict["white_ratio"],
                "edge_density": score_dict["edge_density"],
                "aspect_ratio": score_dict["aspect_ratio"],
                "license_type": asset.license_type,
                "attribution": asset.attribution,
                "source_url": c.get("source_url"),
                "image_url": c.get("image_url"),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        best = results[:3]

        db.add(AiRun(
            job_type="image_select",
            model=settings.OLLAMA_VISION_MODEL or "heuristic",
            input_summary=f"product_id={product_id} query={q} sources={','.join(sources)}",
            output_summary=json.dumps(best, ensure_ascii=False)[:2000],
            meta_json={"count": len(results), "quality_rejections": quality_rejections},
        ))
        db.commit()

        return {
            "query": q,
            "sources": sources,
            "candidates": results,
            "best": best,
            "count": len(results),
            "skipped_duplicates": skipped_duplicates,
            "quality_rejections": quality_rejections,
        }
    finally:
        db.close()