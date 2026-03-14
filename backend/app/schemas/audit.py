from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: str | None
    description: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    meta: dict[str, Any] | None
    created_at: datetime

    class Config:
        from_attributes = True
