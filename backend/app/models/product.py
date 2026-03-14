from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import String, Text, Enum, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, utcnow


class ProductCondition(str, enum.Enum):
    new = "new"
    very_good = "very_good"
    good = "good"
    ok = "ok"
    broken = "broken"


class ProductStatus(str, enum.Enum):
    active = "active"
    sold = "sold"
    gifted = "gifted"
    returned = "returned"
    broken = "broken"
    archived = "archived"


class TransactionType(str, enum.Enum):
    purchase = "purchase"
    sale = "sale"
    gift = "gift"
    return_ = "return"
    repair = "repair"


class Product(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "products"

    title: Mapped[str] = mapped_column(String(256), index=True)
    brand: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)

    condition: Mapped[ProductCondition] = mapped_column(Enum(ProductCondition), default=ProductCondition.good)

    purchase_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    current_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="EUR")

    storage_location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)

    notes_md: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[ProductStatus] = mapped_column(Enum(ProductStatus), default=ProductStatus.active)
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    transactions: Mapped[list["ProductTransaction"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    value_history: Mapped[list["ProductValueHistory"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class ProductTransaction(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "product_transactions"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    date: Mapped[date] = mapped_column(Date)
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    counterparty: Mapped[str | None] = mapped_column(String(256), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship(back_populates="transactions")


class ValueSource(str, enum.Enum):
    manual = "manual"
    estimate = "estimate"
    import_ = "import"


class ProductValueHistory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "product_value_history"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    source: Mapped[ValueSource] = mapped_column(Enum(ValueSource), default=ValueSource.manual)

    product: Mapped["Product"] = relationship(back_populates="value_history")
