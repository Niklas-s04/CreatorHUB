from __future__ import annotations

from typing import TypeVar

from fastapi import Query
from sqlalchemy.orm import Query as SAQuery

from app.schemas.common import Page, PageMeta, SortOrder

ModelT = TypeVar("ModelT")


def pagination_params(
    limit: int = Query(default=50, ge=1, le=500, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    sort_by: str = Query(default="created_at", description="Sort field"),
    sort_order: SortOrder = Query(default=SortOrder.desc, description="Sort direction"),
) -> tuple[int, int, str, SortOrder]:
    return limit, offset, sort_by, sort_order


def apply_sorting(
    query: SAQuery,
    *,
    model,
    sort_by: str,
    sort_order: SortOrder,
    allowed_fields: set[str],
    fallback: str,
) -> tuple[SAQuery, str, SortOrder]:
    selected_sort = sort_by if sort_by in allowed_fields else fallback
    column = getattr(model, selected_sort)
    ordered = query.order_by(column.asc() if sort_order == SortOrder.asc else column.desc())
    return ordered, selected_sort, sort_order


def to_page(
    *,
    items: list[ModelT],
    total: int,
    limit: int,
    offset: int,
    sort_by: str,
    sort_order: SortOrder,
) -> Page[ModelT]:
    return Page[ModelT](
        meta=PageMeta(
            limit=limit,
            offset=offset,
            total=total,
            sort_by=sort_by,
            sort_order=sort_order,
        ),
        items=items,
    )
