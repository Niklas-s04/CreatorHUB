from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

OperationKind = Literal[
    "asset_review",
    "registration_approval",
    "email_risk",
    "content_overdue",
]

OperationPriority = Literal["low", "medium", "high", "critical"]
OperationDueFilter = Literal["all", "overdue", "today", "next7", "none"]


class OperationInboxItem(BaseModel):
    id: str
    kind: OperationKind
    title: str
    description: str
    source_route: str
    source_id: str
    priority: OperationPriority
    escalation: bool
    due_at: datetime | date | None = None
    created_at: datetime | date | None = None
    updated_at: datetime | date | None = None
    assignee_username: str | None = None
    responsible_role: Literal["admin", "editor", "viewer"]


class OperationInboxOut(BaseModel):
    generated_at: datetime
    total_open: int
    items: list[OperationInboxItem]
