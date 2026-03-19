from __future__ import annotations

from datetime import date

import pytest

from app.models.asset import AssetKind, AssetOwnerType, AssetReviewState
from app.models.content import ContentStatus
from app.models.product import ProductStatus
from app.models.registration_request import RegistrationRequestStatus
from app.services.domain_rules import (
    validate_asset_consistency,
    validate_asset_review_state_change,
    validate_content_status_change,
    validate_product_status_change,
    validate_registration_status_change,
)
from app.services.errors import BusinessRuleViolation


def test_product_status_transition_rejects_invalid_reopen_from_archived() -> None:
    with pytest.raises(BusinessRuleViolation):
        validate_product_status_change(
            current_status=ProductStatus.archived,
            target_status=ProductStatus.active,
            amount=None,
        )


def test_product_status_transition_requires_amount_for_sold() -> None:
    with pytest.raises(BusinessRuleViolation, match="amount required for sold"):
        validate_product_status_change(
            current_status=ProductStatus.active,
            target_status=ProductStatus.sold,
            amount=None,
        )


def test_content_status_scheduled_requires_planning_or_publish_date() -> None:
    with pytest.raises(BusinessRuleViolation):
        validate_content_status_change(
            current_status=ContentStatus.draft,
            target_status=ContentStatus.scheduled,
            planned_date=None,
            publish_date=None,
            external_url=None,
        )


def test_asset_consistency_rejects_primary_non_product_image() -> None:
    with pytest.raises(BusinessRuleViolation):
        validate_asset_consistency(
            owner_type=AssetOwnerType.content,
            kind=AssetKind.image,
            is_primary=True,
            review_state=AssetReviewState.pending_review,
            local_path="/tmp/file.jpg",
            url=None,
        )


def test_asset_review_transition_blocks_direct_rejected_to_approved() -> None:
    with pytest.raises(BusinessRuleViolation):
        validate_asset_review_state_change(
            current_state=AssetReviewState.rejected,
            target_state=AssetReviewState.approved,
        )


def test_registration_request_transition_allows_reopen_from_rejected() -> None:
    validate_registration_status_change(
        current_status=RegistrationRequestStatus.rejected,
        target_status=RegistrationRequestStatus.pending,
    )


def test_content_status_published_accepts_external_url_without_publish_date() -> None:
    validate_content_status_change(
        current_status=ContentStatus.edited,
        target_status=ContentStatus.published,
        planned_date=date(2026, 3, 19),
        publish_date=None,
        external_url="https://example.com/video",
    )
