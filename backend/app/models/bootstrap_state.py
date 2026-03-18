from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class BootstrapState(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "bootstrap_state"

    setup_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    setup_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    setup_completed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    install_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    install_token_consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
