from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class PageMeta(BaseModel):
    limit: int
    offset: int
    total: int
    sort_by: str
    sort_order: SortOrder


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    meta: PageMeta
    items: list[T]


class ErrorResponse(BaseModel):
    code: str
    message: str
    status: int
    details: dict | list | str | None = None
