from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.product import ProductCondition, ProductStatus, TransactionType, ValueSource
from app.models.workflow import WorkflowStatus


class ProductBase(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    brand: str | None = None
    model: str | None = None
    category: str | None = None
    condition: ProductCondition = ProductCondition.good
    purchase_price: float | None = None
    purchase_date: date | None = None
    current_value: float | None = None
    currency: str = "EUR"
    storage_location: str | None = None
    serial_number: str | None = None
    notes_md: str | None = None
    status: ProductStatus = ProductStatus.active
    workflow_status: WorkflowStatus = WorkflowStatus.draft
    review_reason: str | None = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    title: str | None = None
    brand: str | None = None
    model: str | None = None
    category: str | None = None
    condition: ProductCondition | None = None
    purchase_price: float | None = None
    purchase_date: date | None = None
    current_value: float | None = None
    currency: str | None = None
    storage_location: str | None = None
    serial_number: str | None = None
    notes_md: str | None = None
    status: ProductStatus | None = None
    workflow_status: WorkflowStatus | None = None
    review_reason: str | None = None


class ProductOut(ProductBase):
    id: uuid.UUID
    status_changed_at: datetime
    reviewed_by_id: uuid.UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductTransactionCreate(BaseModel):
    type: TransactionType
    date: date
    amount: float | None = None
    currency: str = "EUR"
    counterparty: str | None = None
    notes: str | None = None


class ProductTransactionOut(ProductTransactionCreate):
    id: uuid.UUID
    product_id: uuid.UUID

    class Config:
        from_attributes = True


class ProductValueHistoryCreate(BaseModel):
    date: date
    value: float
    currency: str = "EUR"
    source: ValueSource = ValueSource.manual


class ProductValueHistoryOut(ProductValueHistoryCreate):
    id: uuid.UUID
    product_id: uuid.UUID

    class Config:
        from_attributes = True


class ProductStatusChange(BaseModel):
    status: ProductStatus
    date: date
    amount: float | None = None
    currency: str = "EUR"
    notes: str | None = None
    counterparty: str | None = None


class InventoryCsvImportRequest(BaseModel):
    csv_text: str = Field(min_length=1, description="Raw CSV (including header row)")
    delimiter: str = Field(default=";", min_length=1, max_length=1)
    quotechar: str = Field(default='"', min_length=1, max_length=1)
    column_map: dict[str, str] = Field(description="Mapping of product field -> CSV column header")
    defaults: dict[str, Any] | None = Field(
        default=None, description="Fallback values for missing columns"
    )
    dry_run: bool = Field(default=True, description="If true, validates without inserting records")


class InventoryCsvImportResult(BaseModel):
    dry_run: bool
    rows_total: int
    ready: int
    inserted: int
    errors: list[dict[str, Any]]
    preview: list[dict[str, Any]]
    warnings: list[str] | None = None
