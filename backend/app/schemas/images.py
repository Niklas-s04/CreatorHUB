from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


class ImageSearchRequest(BaseModel):
    product_id: uuid.UUID
    query: str | None = None
    max_results: int = Field(default=12, ge=1, le=50)

    # Quelle kann sein:
    #  - "auto" (nutzt IMAGE_HUNT_DEFAULT_SOURCES)
    #  - einzeln: "wikimedia" | "openverse" | "manufacturer" | "opengraph"
    #  - kommagetrennt: "wikimedia,openverse"
    source: str = "auto"

    # Für source="manufacturer": vom Nutzer angegebene URLs.
    manufacturer_urls: list[str] | None = None


class JobStatusOut(BaseModel):
    job_id: str
    status: str  # Mögliche Werte: queued|started|finished|failed
    result: dict | None = None
    error: str | None = None