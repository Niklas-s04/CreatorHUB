from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy import DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class RegistrationRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class RegistrationRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "registration_requests"

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    status: Mapped[RegistrationRequestStatus] = mapped_column(
        Enum(RegistrationRequestStatus), default=RegistrationRequestStatus.pending, index=True
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
