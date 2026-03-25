from __future__ import annotations

import enum


class WorkflowStatus(str, enum.Enum):
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"
    published = "published"
    archived = "archived"
