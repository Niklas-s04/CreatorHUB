from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

    @field_validator("title")
    @classmethod
    def product_title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value


class ProductCreate(ProductBase):
    status: Literal[ProductStatus.active] = ProductStatus.active
    workflow_status: Literal[WorkflowStatus.draft] = WorkflowStatus.draft
    review_reason: Literal[None] = None

    @model_validator(mode="after")
    def monetary_values_must_not_be_negative(self) -> "ProductCreate":
        for field in ("purchase_price", "current_value"):
            value = getattr(self, field)
            if value is not None and value < 0:
                raise ValueError(f"{field} must not be negative")
        return self


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    brand: str | None = None
    model: str | None = None
    category: str | None = None
    condition: ProductCondition | None = None
    purchase_price: float | None = Field(default=None, ge=0)
    purchase_date: date | None = None
    current_value: float | None = Field(default=None, ge=0)
    currency: str | None = None
    storage_location: str | None = None
    serial_number: str | None = None
    notes_md: str | None = None
    workflow_status: WorkflowStatus | None = None
    review_reason: str | None = None

    @field_validator("title")
    @classmethod
    def product_title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @model_validator(mode="after")
    def required_patch_fields_must_not_be_null(self) -> "ProductUpdate":
        for field in ("title", "condition", "currency", "workflow_status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_ids: list[uuid.UUID] = Field(default_factory=list)
    status_changed_at: datetime
    reviewed_by_id: uuid.UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProductTransactionCreate(BaseModel):
    type: TransactionType
    date: date
    amount: float | None = Field(default=None, ge=0)
    currency: str = "EUR"
    counterparty: str | None = None
    notes: str | None = None


class ProductTransactionOut(ProductTransactionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID


class ProductValueHistoryCreate(BaseModel):
    date: date
    value: float = Field(ge=0)
    currency: str = "EUR"
    source: ValueSource = ValueSource.manual


class ProductValueHistoryOut(ProductValueHistoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID


class ProductStatusChange(BaseModel):
    status: ProductStatus
    date: date
    amount: float | None = Field(default=None, ge=0)
    currency: str = "EUR"
    notes: str | None = None
    counterparty: str | None = None


class InventoryCsvImportRequest(BaseModel):
    csv_text: str = Field(min_length=1, description="Raw CSV (including header row)")
    delimiter: str = Field(default="auto", min_length=1, max_length=8)
    quotechar: str = Field(default='"', min_length=1, max_length=1)
    column_map: dict[str, str] = Field(description="Mapping of product field -> CSV column header")
    defaults: dict[str, Any] | None = Field(
        default=None, description="Fallback values for missing columns"
    )
    dry_run: bool = Field(default=True, description="If true, validates without inserting records")
    idempotency_mode: str = Field(
        default="skip_existing",
        description="Idempotency mode: 'none' or 'skip_existing'",
    )
    idempotency_fields: list[str] | None = Field(
        default=None,
        description="Fields used as idempotency key (default: title, brand, model, serial_number)",
    )
    continue_on_error: bool = Field(
        default=True,
        description="Continue processing after row errors to allow partial successful imports",
    )


class InventoryCsvImportResult(BaseModel):
    dry_run: bool
    rows_total: int
    ready: int
    inserted: int
    skipped: int = 0
    errors: list[dict[str, Any]]
    row_warnings: list[dict[str, Any]] = Field(default_factory=list)
    quality_issues: list[dict[str, Any]] = Field(default_factory=list)
    preview: list[dict[str, Any]]
    warnings: list[str] | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    idempotency: dict[str, Any] = Field(default_factory=dict)
