from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetOwnerType
from app.models.content import ContentItem
from app.models.deal import DealDraft, DealDraftStatus
from app.models.product import Product
from app.models.user import User
from app.models.workflow import WorkflowStatus
from app.services.audit import record_audit_log
from app.services.domain_events import emit_domain_event
from app.services.workflow import apply_workflow_change, validate_workflow_status_change


def finalize_product_sale(
    db: Session,
    *,
    product: Product,
    sold_date: date,
    actor: User | None,
    reason: str | None,
) -> None:
    review_reason = (reason or "Product sold; archive linked workflow artifacts").strip()

    linked_deals = db.query(DealDraft).filter(DealDraft.product_id == product.id).all()
    archived_deals = 0
    for deal in linked_deals:
        if deal.status != DealDraftStatus.won:
            deal.status = DealDraftStatus.won
        if deal.workflow_status != WorkflowStatus.archived:
            validate_workflow_status_change(
                current_status=deal.workflow_status,
                target_status=WorkflowStatus.archived,
                review_reason=review_reason,
            )
            apply_workflow_change(
                entity=deal,
                target_status=WorkflowStatus.archived,
                review_reason=review_reason,
                actor=actor,
            )
            archived_deals += 1

    linked_content = db.query(ContentItem).filter(ContentItem.product_id == product.id).all()
    archived_content = 0
    for content_item in linked_content:
        if content_item.workflow_status != WorkflowStatus.archived:
            validate_workflow_status_change(
                current_status=content_item.workflow_status,
                target_status=WorkflowStatus.archived,
                review_reason=review_reason,
            )
            apply_workflow_change(
                entity=content_item,
                target_status=WorkflowStatus.archived,
                review_reason=review_reason,
                actor=actor,
            )
            archived_content += 1

    linked_assets = (
        db.query(Asset)
        .filter(
            Asset.owner_type == AssetOwnerType.product,
            Asset.owner_id == product.id,
        )
        .all()
    )
    archived_assets = 0
    for asset in linked_assets:
        if asset.workflow_status != WorkflowStatus.archived:
            validate_workflow_status_change(
                current_status=asset.workflow_status,
                target_status=WorkflowStatus.archived,
                review_reason=review_reason,
            )
            apply_workflow_change(
                entity=asset,
                target_status=WorkflowStatus.archived,
                review_reason=review_reason,
                actor=actor,
            )
            archived_assets += 1

    record_audit_log(
        db,
        actor=actor,
        action="sales.workflow.finalized",
        entity_type="product",
        entity_id=str(product.id),
        description="Finalized sale workflow with linked archive/historization",
        metadata={
            "sold_date": sold_date.isoformat(),
            "archived_deals": archived_deals,
            "archived_content": archived_content,
            "archived_assets": archived_assets,
        },
    )

    emit_domain_event(
        db,
        actor=actor,
        event_name="sales.closed",
        entity_type="product",
        entity_id=str(product.id),
        payload={
            "sold_date": sold_date.isoformat(),
            "archived_deals": archived_deals,
            "archived_content": archived_content,
            "archived_assets": archived_assets,
        },
        description="Sales closure workflow completed",
    )
