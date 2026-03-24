from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class DashboardListItem(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    updated_at: datetime | date | None = None


class DashboardMetric(BaseModel):
    key: Literal[
        "open_deals",
        "unreviewed_assets",
        "overdue_tasks",
        "risky_email_drafts",
        "pending_registration_requests",
        "audit_incidents",
    ]
    label: str
    description: str
    count: int
    route: str
    tone: Literal["info", "warn", "danger"]
    items: list[DashboardListItem]


class DashboardSummaryOut(BaseModel):
    generated_at: datetime
    role: str
    metrics: list[DashboardMetric]
