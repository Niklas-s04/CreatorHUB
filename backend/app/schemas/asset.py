from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.asset import AssetOwnerType, AssetKind, AssetSource, AssetReviewState


class AssetBase(BaseModel):
    owner_type: AssetOwnerType
    owner_id: uuid.UUID
    kind: AssetKind = AssetKind.image
    source: AssetSource = AssetSource.upload

    url: Optional[str] = None
    local_path: Optional[str] = None
    title: Optional[str] = None

    license_type: Optional[str] = None
    attribution: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    license_url: Optional[str] = None
    fetched_at: Optional[datetime] = None

    width: Optional[int] = None
    height: Optional[int] = None
    size_bytes: Optional[int] = None
    hash: Optional[str] = None
    perceptual_hash: Optional[str] = None

    review_state: AssetReviewState = AssetReviewState.approved
    is_primary: bool = False


class AssetCreateWeb(AssetBase):
    pass


class AssetUpdate(BaseModel):
    title: Optional[str] = None
    license_type: Optional[str] = None
    attribution: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    license_url: Optional[str] = None
    fetched_at: Optional[datetime] = None
    review_state: Optional[AssetReviewState] = None
    is_primary: Optional[bool] = None


class AssetOut(AssetBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True