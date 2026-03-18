from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class AssetOwnerType(str, enum.Enum):
    product = "product"
    content = "content"
    email = "email"
    deal = "deal"


class AssetKind(str, enum.Enum):
    image = "image"
    pdf = "pdf"
    link = "link"
    video = "video"


class AssetSource(str, enum.Enum):
    upload = "upload"
    web = "web"


class AssetReviewState(str, enum.Enum):
    quarantine = "quarantine"
    pending_review = "pending_review"
    needs_review = "needs_review"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Asset(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "assets"

    owner_type: Mapped[AssetOwnerType] = mapped_column(
        Enum(AssetOwnerType), default=AssetOwnerType.product
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True))
    kind: Mapped[AssetKind] = mapped_column(Enum(AssetKind), default=AssetKind.image)
    source: Mapped[AssetSource] = mapped_column(Enum(AssetSource), default=AssetSource.upload)

    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    local_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    license_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    attribution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    license_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    perceptual_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    review_state: Mapped[AssetReviewState] = mapped_column(
        Enum(AssetReviewState), default=AssetReviewState.pending_review
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
