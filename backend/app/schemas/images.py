from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ImageSearchRequest(BaseModel):
    product_id: uuid.UUID
    query: str | None = None
    max_results: int = Field(default=12, ge=1, le=50)

    # Source values can be:
    # - "auto" (uses IMAGE_HUNT_DEFAULT_SOURCES)
    # - a single source such as "wikimedia", "openverse", "manufacturer", or "opengraph"
    # - a comma-separated list such as "wikimedia,openverse"
    source: str = "auto"

    # For source="manufacturer": URLs provided by the user.
    manufacturer_urls: list[str] | None = None


class JobStatusOut(BaseModel):
    job_id: str
    status: str  # Allowed values: queued, started, finished, failed
    result: dict | None = None
    error: str | None = None
