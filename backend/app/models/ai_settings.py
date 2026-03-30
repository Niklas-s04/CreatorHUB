from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class CreatorAiTone(str, enum.Enum):
    neutral = "neutral"
    friendly = "friendly"
    professional = "professional"
    energetic = "energetic"
    direct = "direct"


class CreatorAiProfile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "creator_ai_profiles"

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    profile_name: Mapped[str] = mapped_column(String(128))
    is_global_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    clear_name: Mapped[str] = mapped_column(String(128))
    artist_name: Mapped[str] = mapped_column(String(128))
    channel_link: Mapped[str] = mapped_column(Text)
    themes: Mapped[list[str]] = mapped_column(JSON, default=list)
    platforms: Mapped[list[str]] = mapped_column(JSON, default=list)

    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone: Mapped[CreatorAiTone] = mapped_column(Enum(CreatorAiTone), default=CreatorAiTone.neutral)
    target_audience: Mapped[str | None] = mapped_column(String(256), nullable=True)
    language_code: Mapped[str] = mapped_column(String(16), default="de")
    content_focus: Mapped[list[str]] = mapped_column(JSON, default=list)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    created_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    updated_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
