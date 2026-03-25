from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class GlobalSearchEntityType(str, Enum):
    product = "product"
    asset = "asset"
    content = "content"
    knowledge = "knowledge"
    user = "user"


class GlobalSearchHit(BaseModel):
    id: str
    type: GlobalSearchEntityType
    title: str
    subtitle: str | None = None
    detail_path: str
    score: float


class GlobalSearchGroup(BaseModel):
    type: GlobalSearchEntityType
    label: str
    count: int
    hits: list[GlobalSearchHit]


class GlobalSearchOut(BaseModel):
    query: str
    total: int
    groups: list[GlobalSearchGroup]
