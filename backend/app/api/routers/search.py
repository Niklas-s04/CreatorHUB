from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.authorization import Permission, has_permission
from app.models.asset import Asset
from app.models.content import ContentItem
from app.models.knowledge import KnowledgeDoc
from app.models.product import Product
from app.models.user import User
from app.schemas.search import (
    GlobalSearchEntityType,
    GlobalSearchGroup,
    GlobalSearchHit,
    GlobalSearchOut,
)

router = APIRouter()

_TYPE_LABELS: dict[GlobalSearchEntityType, str] = {
    GlobalSearchEntityType.product: "Produkte",
    GlobalSearchEntityType.asset: "Assets",
    GlobalSearchEntityType.content: "Content",
    GlobalSearchEntityType.knowledge: "Knowledge",
    GlobalSearchEntityType.user: "Benutzer",
}


def _normalize(value: str) -> str:
    return value.strip().lower()


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _score_text(query: str, raw_text: str | None, weight: float) -> float:
    if not raw_text:
        return 0.0
    text = _normalize(raw_text)
    if not text:
        return 0.0
    if text == query:
        return weight * 8
    if text.startswith(query):
        return weight * 5
    if f" {query}" in text:
        return weight * 3
    if query in text:
        return weight * 2
    return 0.0


def _recency_bonus(updated_at: datetime | None) -> float:
    aware = _as_aware(updated_at)
    if aware is None:
        return 0.0
    age = datetime.now(timezone.utc) - aware
    if age <= timedelta(days=2):
        return 0.3
    if age <= timedelta(days=7):
        return 0.15
    if age <= timedelta(days=30):
        return 0.05
    return 0.0


def _product_hits(
    db: Session, query: str, pattern: str, candidate_limit: int
) -> list[GlobalSearchHit]:
    rows = (
        db.query(Product)
        .filter(
            or_(
                Product.title.ilike(pattern),
                Product.brand.ilike(pattern),
                Product.model.ilike(pattern),
                Product.category.ilike(pattern),
            )
        )
        .order_by(Product.updated_at.desc())
        .limit(candidate_limit)
        .all()
    )
    hits: list[GlobalSearchHit] = []
    for row in rows:
        score = (
            _score_text(query, row.title, 4.0)
            + _score_text(query, row.brand, 2.2)
            + _score_text(query, row.model, 1.8)
            + _score_text(query, row.category, 1.3)
            + _recency_bonus(row.updated_at)
        )
        if score <= 0:
            continue
        subtitle_parts = [part for part in [row.brand, row.model, row.status.value] if part]
        hits.append(
            GlobalSearchHit(
                id=str(row.id),
                type=GlobalSearchEntityType.product,
                title=row.title,
                subtitle=" · ".join(subtitle_parts) if subtitle_parts else None,
                detail_path=f"/products/{row.id}",
                score=round(score, 3),
            )
        )
    return hits


def _asset_hits(
    db: Session, query: str, pattern: str, candidate_limit: int
) -> list[GlobalSearchHit]:
    rows = (
        db.query(Asset)
        .filter(
            or_(
                Asset.title.ilike(pattern),
                Asset.source_name.ilike(pattern),
                Asset.source_url.ilike(pattern),
                Asset.url.ilike(pattern),
            )
        )
        .order_by(Asset.updated_at.desc())
        .limit(candidate_limit)
        .all()
    )
    hits: list[GlobalSearchHit] = []
    for row in rows:
        score = (
            _score_text(query, row.title, 3.2)
            + _score_text(query, row.source_name, 1.9)
            + _score_text(query, row.source_url, 1.5)
            + _score_text(query, row.url, 1.2)
            + _recency_bonus(row.updated_at)
        )
        if score <= 0:
            continue
        subtitle = f"{row.kind.value} · {row.owner_type.value} · {row.review_state.value}"
        hits.append(
            GlobalSearchHit(
                id=str(row.id),
                type=GlobalSearchEntityType.asset,
                title=row.title or "Asset ohne Titel",
                subtitle=subtitle,
                detail_path=f"/assets#asset-{row.id}",
                score=round(score, 3),
            )
        )
    return hits


def _content_hits(
    db: Session, query: str, pattern: str, candidate_limit: int
) -> list[GlobalSearchHit]:
    rows = (
        db.query(ContentItem)
        .filter(
            or_(
                ContentItem.title.ilike(pattern),
                ContentItem.hook.ilike(pattern),
                ContentItem.tags_csv.ilike(pattern),
            )
        )
        .order_by(ContentItem.updated_at.desc())
        .limit(candidate_limit)
        .all()
    )
    hits: list[GlobalSearchHit] = []
    for row in rows:
        score = (
            _score_text(query, row.title, 3.8)
            + _score_text(query, row.hook, 1.7)
            + _score_text(query, row.tags_csv, 1.2)
            + _recency_bonus(row.updated_at)
        )
        if score <= 0:
            continue
        subtitle = f"{row.platform.value} · {row.type.value} · {row.status.value}"
        hits.append(
            GlobalSearchHit(
                id=str(row.id),
                type=GlobalSearchEntityType.content,
                title=row.title or "Content ohne Titel",
                subtitle=subtitle,
                detail_path=f"/content#content-{row.id}",
                score=round(score, 3),
            )
        )
    return hits


def _knowledge_hits(
    db: Session, query: str, pattern: str, candidate_limit: int
) -> list[GlobalSearchHit]:
    rows = (
        db.query(KnowledgeDoc)
        .filter(or_(KnowledgeDoc.title.ilike(pattern), KnowledgeDoc.content.ilike(pattern)))
        .order_by(KnowledgeDoc.updated_at.desc())
        .limit(candidate_limit)
        .all()
    )
    hits: list[GlobalSearchHit] = []
    for row in rows:
        score = (
            _score_text(query, row.title, 3.0)
            + _score_text(query, row.content, 0.9)
            + _recency_bonus(row.updated_at)
        )
        if score <= 0:
            continue
        subtitle = f"{row.type.value} · {row.workflow_status.value}"
        hits.append(
            GlobalSearchHit(
                id=str(row.id),
                type=GlobalSearchEntityType.knowledge,
                title=row.title,
                subtitle=subtitle,
                detail_path=f"/settings#knowledge-{row.id}",
                score=round(score, 3),
            )
        )
    return hits


def _user_hits(
    db: Session, query: str, pattern: str, candidate_limit: int
) -> list[GlobalSearchHit]:
    rows = (
        db.query(User)
        .filter(User.username.ilike(pattern))
        .order_by(User.created_at.desc())
        .limit(candidate_limit)
        .all()
    )
    hits: list[GlobalSearchHit] = []
    for row in rows:
        score = _score_text(query, row.username, 4.0) + _recency_bonus(row.updated_at)
        if score <= 0:
            continue
        subtitle = f"{row.role.value} · {'active' if row.is_active else 'inactive'}"
        hits.append(
            GlobalSearchHit(
                id=str(row.id),
                type=GlobalSearchEntityType.user,
                title=row.username,
                subtitle=subtitle,
                detail_path=f"/admin#user-{row.id}",
                score=round(score, 3),
            )
        )
    return hits


@router.get("/", response_model=GlobalSearchOut)
def global_search(
    q: str = Query(..., min_length=2, max_length=80),
    per_type: int = Query(5, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GlobalSearchOut:
    query = _normalize(q)
    pattern = f"%{query}%"
    candidate_limit = max(per_type * 8, 24)

    grouped_hits: dict[GlobalSearchEntityType, list[GlobalSearchHit]] = {
        GlobalSearchEntityType.product: [],
        GlobalSearchEntityType.asset: [],
        GlobalSearchEntityType.content: [],
        GlobalSearchEntityType.knowledge: [],
        GlobalSearchEntityType.user: [],
    }

    if has_permission(current_user, Permission.product_read):
        grouped_hits[GlobalSearchEntityType.product] = _product_hits(
            db, query, pattern, candidate_limit
        )
    if has_permission(current_user, Permission.asset_read):
        grouped_hits[GlobalSearchEntityType.asset] = _asset_hits(
            db, query, pattern, candidate_limit
        )
    if has_permission(current_user, Permission.content_read):
        grouped_hits[GlobalSearchEntityType.content] = _content_hits(
            db, query, pattern, candidate_limit
        )
    if has_permission(current_user, Permission.knowledge_read):
        grouped_hits[GlobalSearchEntityType.knowledge] = _knowledge_hits(
            db, query, pattern, candidate_limit
        )
    if has_permission(current_user, Permission.user_read):
        grouped_hits[GlobalSearchEntityType.user] = _user_hits(db, query, pattern, candidate_limit)

    groups: list[GlobalSearchGroup] = []
    total = 0
    for entity_type in [
        GlobalSearchEntityType.product,
        GlobalSearchEntityType.asset,
        GlobalSearchEntityType.content,
        GlobalSearchEntityType.knowledge,
        GlobalSearchEntityType.user,
    ]:
        hits = grouped_hits[entity_type]
        if not hits:
            continue
        hits.sort(key=lambda item: item.score, reverse=True)
        limited_hits = hits[:per_type]
        groups.append(
            GlobalSearchGroup(
                type=entity_type,
                label=_TYPE_LABELS[entity_type],
                count=len(limited_hits),
                hits=limited_hits,
            )
        )
        total += len(limited_hits)

    return GlobalSearchOut(query=q.strip(), total=total, groups=groups)
