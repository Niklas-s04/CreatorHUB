from __future__ import annotations

import enum

from sqlalchemy import String, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class KnowledgeDocType(str, enum.Enum):
    brand_voice = "brand_voice"
    policy = "policy"
    template = "template"
    rate_card = "rate_card"


class KnowledgeDoc(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_docs"

    type: Mapped[KnowledgeDocType] = mapped_column(Enum(KnowledgeDocType), index=True)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    # Embeddings (pgvector) sind im MVP bewusst nicht enthalten.
