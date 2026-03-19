from __future__ import annotations

from datetime import date

from app.models.asset import AssetKind, AssetOwnerType, AssetReviewState
from app.models.content import ContentStatus
from app.models.product import ProductStatus, TransactionType
from app.models.registration_request import RegistrationRequestStatus
from app.services.errors import BusinessRuleViolation

PRODUCT_STATUS_TRANSITIONS: dict[ProductStatus, set[ProductStatus]] = {
    ProductStatus.active: {
        ProductStatus.sold,
        ProductStatus.gifted,
        ProductStatus.returned,
        ProductStatus.broken,
        ProductStatus.archived,
    },
    ProductStatus.sold: {ProductStatus.returned, ProductStatus.archived},
    ProductStatus.gifted: {ProductStatus.archived},
    ProductStatus.returned: {ProductStatus.active, ProductStatus.broken, ProductStatus.archived},
    ProductStatus.broken: {ProductStatus.returned, ProductStatus.archived},
    ProductStatus.archived: set(),
}

CONTENT_STATUS_TRANSITIONS: dict[ContentStatus, set[ContentStatus]] = {
    ContentStatus.idea: {ContentStatus.draft},
    ContentStatus.draft: {ContentStatus.recorded, ContentStatus.scheduled},
    ContentStatus.recorded: {ContentStatus.edited},
    ContentStatus.edited: {ContentStatus.scheduled, ContentStatus.published},
    ContentStatus.scheduled: {ContentStatus.published, ContentStatus.draft},
    ContentStatus.published: set(),
}

ASSET_REVIEW_TRANSITIONS: dict[AssetReviewState, set[AssetReviewState]] = {
    AssetReviewState.quarantine: {AssetReviewState.pending_review, AssetReviewState.rejected},
    AssetReviewState.pending_review: {
        AssetReviewState.needs_review,
        AssetReviewState.pending,
        AssetReviewState.approved,
        AssetReviewState.rejected,
        AssetReviewState.quarantine,
    },
    AssetReviewState.needs_review: {
        AssetReviewState.pending,
        AssetReviewState.approved,
        AssetReviewState.rejected,
    },
    AssetReviewState.pending: {
        AssetReviewState.needs_review,
        AssetReviewState.approved,
        AssetReviewState.rejected,
    },
    AssetReviewState.approved: {AssetReviewState.needs_review, AssetReviewState.rejected},
    AssetReviewState.rejected: {AssetReviewState.pending_review, AssetReviewState.needs_review},
}

REGISTRATION_STATUS_TRANSITIONS: dict[RegistrationRequestStatus, set[RegistrationRequestStatus]] = {
    RegistrationRequestStatus.pending: {
        RegistrationRequestStatus.approved,
        RegistrationRequestStatus.rejected,
    },
    RegistrationRequestStatus.approved: set(),
    RegistrationRequestStatus.rejected: {RegistrationRequestStatus.pending},
}


def _ensure_status_transition(
    *,
    domain: str,
    current,
    target,
    transitions: dict,
) -> None:
    if current == target:
        return
    allowed = transitions.get(current, set())
    if target not in allowed:
        allowed_text = ", ".join(sorted(value.value for value in allowed)) or "<none>"
        raise BusinessRuleViolation(
            f"Invalid {domain} transition: {current.value} -> {target.value}. Allowed: {allowed_text}"
        )


def product_status_side_effect(status: ProductStatus) -> tuple[TransactionType | None, bool]:
    if status == ProductStatus.sold:
        return TransactionType.sale, True
    if status == ProductStatus.gifted:
        return TransactionType.gift, False
    if status == ProductStatus.returned:
        return TransactionType.return_, False
    if status == ProductStatus.broken:
        return TransactionType.repair, False
    return None, False


def validate_product_status_change(
    *,
    current_status: ProductStatus,
    target_status: ProductStatus,
    amount: float | None,
) -> None:
    _ensure_status_transition(
        domain="product status",
        current=current_status,
        target=target_status,
        transitions=PRODUCT_STATUS_TRANSITIONS,
    )
    _, amount_required = product_status_side_effect(target_status)
    if amount_required and amount is None:
        raise BusinessRuleViolation("amount required for sold")


def validate_content_status_change(
    *,
    current_status: ContentStatus,
    target_status: ContentStatus,
    planned_date: date | None,
    publish_date: date | None,
    external_url: str | None,
) -> None:
    _ensure_status_transition(
        domain="content status",
        current=current_status,
        target=target_status,
        transitions=CONTENT_STATUS_TRANSITIONS,
    )

    if target_status == ContentStatus.scheduled and not (planned_date or publish_date):
        raise BusinessRuleViolation("planned_date or publish_date required for scheduled status")
    if target_status == ContentStatus.published and not (publish_date or external_url):
        raise BusinessRuleViolation("publish_date or external_url required for published status")


def validate_asset_review_state_change(
    *,
    current_state: AssetReviewState,
    target_state: AssetReviewState,
) -> None:
    _ensure_status_transition(
        domain="asset review_state",
        current=current_state,
        target=target_state,
        transitions=ASSET_REVIEW_TRANSITIONS,
    )


def validate_asset_consistency(
    *,
    owner_type: AssetOwnerType,
    kind: AssetKind,
    is_primary: bool,
    review_state: AssetReviewState,
    local_path: str | None,
    url: str | None,
) -> None:
    if is_primary and not (owner_type == AssetOwnerType.product and kind == AssetKind.image):
        raise BusinessRuleViolation("is_primary is only allowed for product images")
    if review_state == AssetReviewState.approved and not (local_path or url):
        raise BusinessRuleViolation("approved assets require local_path or url")


def validate_registration_status_change(
    *,
    current_status: RegistrationRequestStatus,
    target_status: RegistrationRequestStatus,
) -> None:
    _ensure_status_transition(
        domain="registration request",
        current=current_status,
        target=target_status,
        transitions=REGISTRATION_STATUS_TRANSITIONS,
    )
