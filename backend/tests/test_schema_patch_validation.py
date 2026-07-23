from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.asset import AssetUpdate
from app.schemas.content import ContentItemUpdate, ContentTaskUpdate
from app.schemas.knowledge import KnowledgeDocUpdate
from app.schemas.product import (
    ProductCreate,
    ProductStatusChange,
    ProductTransactionCreate,
    ProductUpdate,
    ProductValueHistoryCreate,
)
from app.schemas.project import ProjectUpdate


@pytest.mark.parametrize(
    ("schema", "field"),
    [
        (ProductUpdate, "title"),
        (ProductUpdate, "currency"),
        (ContentItemUpdate, "status"),
        (ContentItemUpdate, "platform_meta_json"),
        (ContentTaskUpdate, "priority"),
        (ContentTaskUpdate, "required_for_publish"),
        (KnowledgeDocUpdate, "title"),
        (KnowledgeDocUpdate, "source_review_status"),
        (KnowledgeDocUpdate, "is_outdated"),
        (AssetUpdate, "review_state"),
        (AssetUpdate, "workflow_status"),
        (AssetUpdate, "is_primary"),
        (ProjectUpdate, "preview_status"),
    ],
)
def test_patch_schema_rejects_null_for_persisted_required_fields(schema, field: str) -> None:
    with pytest.raises(ValidationError, match=f"{field} must not be null"):
        schema.model_validate({field: None})


def test_patch_schemas_still_allow_null_for_nullable_fields() -> None:
    assert ProductUpdate(brand=None).brand is None
    assert ContentItemUpdate(publish_date=None).publish_date is None
    assert ContentTaskUpdate(assignee_user_id=None).assignee_user_id is None
    assert KnowledgeDocUpdate(source_url=None).source_url is None


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "Camera", "purchase_price": -1},
        {"title": "Camera", "current_value": -1},
    ],
)
def test_product_create_rejects_negative_monetary_values(payload) -> None:
    with pytest.raises(ValidationError, match="must not be negative"):
        ProductCreate.model_validate(payload)


@pytest.mark.parametrize("schema", [ProductCreate, ProductUpdate])
def test_product_title_is_trimmed_and_must_not_be_blank(schema) -> None:
    assert schema.model_validate({"title": "  Camera  "}).title == "Camera"
    with pytest.raises(ValidationError, match="title must not be blank"):
        schema.model_validate({"title": "   "})


def test_product_value_history_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        ProductValueHistoryCreate.model_validate({"date": "2026-07-23", "value": -1})


def test_product_transaction_rejects_negative_amount() -> None:
    with pytest.raises(ValidationError):
        ProductTransactionCreate.model_validate(
            {"type": "purchase", "date": "2026-07-23", "amount": -1}
        )


def test_product_status_change_rejects_negative_amount() -> None:
    with pytest.raises(ValidationError):
        ProductStatusChange.model_validate({"status": "sold", "date": "2026-07-23", "amount": -1})
