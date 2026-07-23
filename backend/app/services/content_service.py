from __future__ import annotations

import uuid
from contextlib import nullcontext
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetOwnerType, AssetReviewState
from app.models.base import utcnow
from app.models.content import (
    ChecklistPhase,
    ContentChecklistSnapshot,
    ContentChecklistTemplate,
    ContentChecklistTemplateItem,
    ContentItem,
    ContentItemRevision,
    ContentPlatformProfile,
    ContentStatus,
    ContentTask,
    ContentTaskView,
    EditorialStatus,
    TaskStatus,
    TaskType,
)
from app.models.product import Product, ProductStatus
from app.models.user import User, UserRole
from app.models.workflow import WorkflowStatus
from app.schemas.common import SortOrder
from app.schemas.content import (
    ContentChecklistTemplateCreate,
    ContentChecklistTemplateUpdate,
    ContentItemCreate,
    ContentItemUpdate,
    ContentPlatformProfileCreate,
    ContentPlatformProfileUpdate,
    ContentTaskCreate,
    ContentTaskFilterParams,
    ContentTaskUpdate,
    ContentTaskViewCreate,
    ContentTemplateApplyRequest,
)
from app.services.audit import record_audit_log
from app.services.content_task_defaults import ensure_default_tasks_for_item
from app.services.domain_events import emit_domain_event
from app.services.domain_rules import validate_content_status_change
from app.services.errors import BusinessRuleViolation, NotFoundError
from app.services.transactions import transaction_boundary
from app.services.workflow import (
    apply_workflow_change,
    auto_re_review_reason,
    requires_re_review,
    validate_workflow_status_change,
)

CONTENT_RE_REVIEW_FIELDS: set[str] = {
    "product_id",
    "platform",
    "type",
    "title",
    "hook",
    "script_md",
    "description_md",
    "tags_csv",
    "planned_date",
    "publish_date",
    "external_url",
}
CONTENT_REVISION_FIELDS: set[str] = CONTENT_RE_REVIEW_FIELDS | {
    "status",
    "workflow_status",
    "review_reason",
    "editorial_status",
    "editorial_owner_id",
    "editorial_owner_name",
    "last_change_summary",
}

CONTENT_STATUS_TO_EDITORIAL: dict[ContentStatus, EditorialStatus] = {
    ContentStatus.idea: EditorialStatus.backlog,
    ContentStatus.draft: EditorialStatus.drafting,
    ContentStatus.recorded: EditorialStatus.drafting,
    ContentStatus.edited: EditorialStatus.in_review,
    ContentStatus.scheduled: EditorialStatus.ready_to_publish,
    ContentStatus.published: EditorialStatus.published,
}

VALID_TEMPLATE_MERGE_MODES: set[str] = {"replace", "append"}


def _serialize_value(value):
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _is_missing_value(value) -> bool:
    return value is None or value == "" or value == []


def _active_platform_profile(
    db: Session,
    *,
    platform,
) -> ContentPlatformProfile | None:
    return (
        db.query(ContentPlatformProfile)
        .filter(
            ContentPlatformProfile.platform == platform,
            ContentPlatformProfile.is_active.is_(True),
        )
        .order_by(ContentPlatformProfile.version.desc(), ContentPlatformProfile.updated_at.desc())
        .first()
    )


def _validate_platform_meta(
    db: Session,
    *,
    platform,
    platform_meta_json: dict[str, str | int | bool | float | None] | None,
) -> list[str]:
    profile = _active_platform_profile(db, platform=platform)
    payload = platform_meta_json or {}
    if not isinstance(payload, dict):
        raise BusinessRuleViolation("platform_meta_json must be an object")
    if profile is None:
        return []

    schema = profile.schema_json if isinstance(profile.schema_json, dict) else {}
    fields = schema.get("fields")
    if not isinstance(fields, list):
        return []

    allowed_keys: set[str] = set()
    required_keys: set[str] = set()
    for field in fields:
        if not isinstance(field, dict):
            continue
        key = field.get("key")
        if not isinstance(key, str) or not key.strip():
            continue
        key = key.strip()
        allowed_keys.add(key)
        if bool(field.get("required")):
            required_keys.add(key)

    unknown = sorted(k for k in payload.keys() if k not in allowed_keys)
    if unknown:
        raise BusinessRuleViolation("Unknown platform fields: " + ", ".join(unknown))

    missing_required = sorted(key for key in required_keys if _is_missing_value(payload.get(key)))
    return missing_required


def _active_platform_schema(db: Session, *, platform) -> dict:
    profile = _active_platform_profile(db, platform=platform)
    if profile is None or not isinstance(profile.schema_json, dict):
        return {}
    return profile.schema_json


def _missing_required_base_fields(db: Session, *, item: ContentItem) -> list[str]:
    schema = _active_platform_schema(db, platform=item.platform)
    required_base_fields = schema.get("required_base_fields")
    if not isinstance(required_base_fields, list):
        return []

    missing: list[str] = []
    for raw_field in required_base_fields:
        if not isinstance(raw_field, str) or not raw_field.strip():
            continue
        field = raw_field.strip()
        if not hasattr(item, field):
            continue
        value = getattr(item, field)
        if _is_missing_value(value):
            missing.append(field)
    return sorted(set(missing))


def _compute_readiness_score(
    *,
    missing_base_fields: list[str] | None = None,
    missing_platform_fields: list[str],
    open_required_tasks: int,
    approved_assets: int,
) -> int:
    score = 100
    if missing_base_fields:
        score -= min(30, len(missing_base_fields) * 10)
    if missing_platform_fields:
        score -= min(40, len(missing_platform_fields) * 10)
    if open_required_tasks > 0:
        score -= min(40, open_required_tasks * 10)
    if approved_assets <= 0:
        score -= 20
    if score < 0:
        return 0
    return score


def _resolve_editorial_status(
    *,
    item_status: ContentStatus,
    workflow_status: WorkflowStatus,
    fallback: EditorialStatus,
) -> EditorialStatus:
    if item_status == ContentStatus.published:
        return EditorialStatus.published
    if workflow_status == WorkflowStatus.rejected:
        return EditorialStatus.changes_requested
    if workflow_status == WorkflowStatus.in_review:
        return EditorialStatus.in_review
    if workflow_status == WorkflowStatus.approved and item_status == ContentStatus.scheduled:
        return EditorialStatus.ready_to_publish
    if workflow_status == WorkflowStatus.approved:
        return EditorialStatus.approved
    return CONTENT_STATUS_TO_EDITORIAL.get(item_status, fallback)


def _ensure_product_link_valid(db: Session, *, product_id: uuid.UUID | None) -> None:
    if product_id is None:
        return
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise BusinessRuleViolation("Linked product not found")
    if product.status == ProductStatus.archived:
        raise BusinessRuleViolation("Archived products cannot be linked to new content")


def _ensure_primary_asset_link_valid(
    db: Session,
    *,
    content_item_id: uuid.UUID,
    primary_asset_id: uuid.UUID | None,
) -> None:
    if primary_asset_id is None:
        return
    asset = db.query(Asset).filter(Asset.id == primary_asset_id).first()
    if not asset:
        raise BusinessRuleViolation("Primary asset not found")
    if asset.owner_type != AssetOwnerType.content or asset.owner_id != content_item_id:
        raise BusinessRuleViolation("Primary asset must belong to the content item")
    if asset.review_state != AssetReviewState.approved:
        raise BusinessRuleViolation("Primary asset must be approved")


def _asset_counts(db: Session, *, content_item_id: uuid.UUID) -> tuple[int, int, int]:
    rows = db.query(Asset.review_state).filter(
        Asset.owner_type == AssetOwnerType.content,
        Asset.owner_id == content_item_id,
    )
    total = 0
    approved = 0
    pending = 0
    for (state,) in rows.all():
        total += 1
        if state == AssetReviewState.approved:
            approved += 1
        elif state in {
            AssetReviewState.pending,
            AssetReviewState.pending_review,
            AssetReviewState.needs_review,
            AssetReviewState.quarantine,
        }:
            pending += 1
    return total, approved, pending


def _enrich_content_item(item: ContentItem, db: Session) -> ContentItem:
    total, approved, pending = _asset_counts(db, content_item_id=item.id)
    item.asset_count = total
    item.approved_asset_count = approved
    item.pending_asset_count = pending
    return item


def enrich_content_item(db: Session, item: ContentItem) -> ContentItem:
    return _enrich_content_item(item, db)


def _append_item_revision(
    db: Session,
    *,
    item: ContentItem,
    before: dict[str, str | int | bool | None],
    after: dict[str, str | int | bool | None],
    actor: User | None,
    change_summary: str | None,
) -> None:
    changed_fields = sorted(set(before.keys()) | set(after.keys()))
    if not changed_fields:
        return
    last_revision_number = (
        db.query(ContentItemRevision.revision_number)
        .filter(ContentItemRevision.content_item_id == item.id)
        .order_by(ContentItemRevision.revision_number.desc())
        .first()
    )
    next_revision_number = (last_revision_number[0] if last_revision_number else 0) + 1
    db.add(
        ContentItemRevision(
            content_item_id=item.id,
            revision_number=next_revision_number,
            changed_fields=changed_fields,
            before_json=before,
            after_json=after,
            workflow_status=item.workflow_status,
            editorial_status=item.editorial_status,
            content_status=item.status,
            review_reason=item.review_reason,
            change_summary=change_summary,
            changed_by_id=actor.id if actor else None,
            changed_by_name=actor.username if actor else None,
        )
    )


def _ensure_publish_ready(item: ContentItem, db: Session) -> None:
    if item.workflow_status != WorkflowStatus.approved:
        raise BusinessRuleViolation("Content must be approved before publishing")

    blocking_tasks = (
        db.query(ContentTask.id)
        .filter(
            ContentTask.content_item_id == item.id,
            ContentTask.status != TaskStatus.done,
            ContentTask.required_for_publish.is_(True),
            ContentTask.can_block_publish.is_(True),
        )
        .count()
    )
    if blocking_tasks > 0:
        raise BusinessRuleViolation("Required checklist tasks are still open")

    missing_required_base_fields = _missing_required_base_fields(db, item=item)
    if missing_required_base_fields:
        raise BusinessRuleViolation(
            "Missing required content fields: " + ", ".join(missing_required_base_fields)
        )

    missing_required_platform_fields = _validate_platform_meta(
        db,
        platform=item.platform,
        platform_meta_json=item.platform_meta_json,
    )
    if missing_required_platform_fields:
        raise BusinessRuleViolation(
            "Missing required platform fields: " + ", ".join(missing_required_platform_fields)
        )

    approved_assets = (
        db.query(Asset.id)
        .filter(
            Asset.owner_type == AssetOwnerType.content,
            Asset.owner_id == item.id,
            Asset.review_state == AssetReviewState.approved,
        )
        .count()
    )
    if approved_assets == 0:
        raise BusinessRuleViolation(
            "At least one approved content asset is required for publishing"
        )


def _refresh_item_readiness(db: Session, *, item: ContentItem) -> None:
    db.flush()
    missing_required_base_fields = _missing_required_base_fields(db, item=item)
    missing_required_platform_fields = _validate_platform_meta(
        db,
        platform=item.platform,
        platform_meta_json=item.platform_meta_json,
    )
    required_open_tasks = (
        db.query(ContentTask.id)
        .filter(
            ContentTask.content_item_id == item.id,
            ContentTask.status != TaskStatus.done,
            ContentTask.required_for_publish.is_(True),
            ContentTask.can_block_publish.is_(True),
        )
        .count()
    )
    approved_assets = (
        db.query(Asset.id)
        .filter(
            Asset.owner_type == AssetOwnerType.content,
            Asset.owner_id == item.id,
            Asset.review_state == AssetReviewState.approved,
        )
        .count()
    )
    item.readiness_score = _compute_readiness_score(
        missing_base_fields=missing_required_base_fields,
        missing_platform_fields=missing_required_platform_fields,
        open_required_tasks=required_open_tasks,
        approved_assets=approved_assets,
    )


def refresh_item_readiness(db: Session, *, item_id: uuid.UUID) -> ContentItem | None:
    """Recompute persisted readiness after a related task or asset mutation."""
    db.flush()
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if item is None:
        return None
    _refresh_item_readiness(db, item=item)
    return item


def list_items(db: Session, *, product_id: uuid.UUID | None = None) -> list[ContentItem]:
    q = db.query(ContentItem)
    if product_id:
        q = q.filter(ContentItem.product_id == product_id)
    items = q.order_by(ContentItem.updated_at.desc()).all()
    return [_enrich_content_item(item, db) for item in items]


def create_item(
    db: Session,
    *,
    payload: ContentItemCreate,
    actor: User | None,
    commit: bool = True,
) -> ContentItem:
    """Create a content item, optionally inside a caller-owned transaction."""
    _ensure_product_link_valid(db, product_id=payload.product_id)
    item_data = payload.model_dump()
    item_data["title"] = _normalize_optional_text(item_data.get("title"))
    item_data["hook"] = _normalize_optional_text(item_data.get("hook"))
    item_data["script_md"] = _normalize_optional_text(item_data.get("script_md"))
    item_data["description_md"] = _normalize_optional_text(item_data.get("description_md"))
    item_data["tags_csv"] = _normalize_optional_text(item_data.get("tags_csv"))
    item_data["external_url"] = _normalize_optional_text(item_data.get("external_url"))
    item_data["review_reason"] = _normalize_optional_text(item_data.get("review_reason"))
    item_data["editorial_owner_name"] = _normalize_optional_text(
        item_data.get("editorial_owner_name")
    )
    item_data["last_change_summary"] = _normalize_optional_text(
        item_data.get("last_change_summary")
    )
    item_data["platform_meta_json"] = item_data.get("platform_meta_json") or {}
    _validate_platform_meta(
        db,
        platform=item_data.get("platform"),
        platform_meta_json=item_data.get("platform_meta_json"),
    )
    item = ContentItem(**item_data)
    validate_content_status_change(
        current_status=item.status,
        target_status=item.status,
        planned_date=item.planned_date,
        publish_date=item.publish_date,
        external_url=item.external_url,
    )
    validate_workflow_status_change(
        current_status=item.workflow_status,
        target_status=item.workflow_status,
        review_reason=item.review_reason,
    )
    transaction = transaction_boundary(db) if commit else nullcontext()
    with transaction:
        db.add(item)
        db.flush()
        _ensure_primary_asset_link_valid(
            db, content_item_id=item.id, primary_asset_id=item.primary_asset_id
        )
        item.editorial_status = _resolve_editorial_status(
            item_status=item.status,
            workflow_status=item.workflow_status,
            fallback=item.editorial_status,
        )
        created_tasks = ensure_default_tasks_for_item(db, item)
        _refresh_item_readiness(db, item=item)
        _append_item_revision(
            db,
            item=item,
            before={},
            after={
                "status": item.status.value,
                "workflow_status": item.workflow_status.value,
                "editorial_status": item.editorial_status.value,
                "type": item.type.value,
            },
            actor=actor,
            change_summary=item.last_change_summary or "Initial content item",
        )
        record_audit_log(
            db,
            actor=actor,
            action="content.item.create",
            entity_type="content_item",
            entity_id=str(item.id),
            description=f"Created content item '{item.title or item.id}'",
            after={
                "status": item.status.value,
                "workflow_status": item.workflow_status.value,
                "editorial_status": item.editorial_status.value,
                "platform": item.platform.value,
                "type": item.type.value,
                "product_id": str(item.product_id) if item.product_id else None,
                "primary_asset_id": str(item.primary_asset_id) if item.primary_asset_id else None,
                "default_tasks_created": created_tasks,
            },
        )
        db.flush()
    db.refresh(item)
    return _enrich_content_item(item, db)


def update_item(
    db: Session,
    *,
    item_id: uuid.UUID,
    payload: ContentItemUpdate,
    actor: User | None,
) -> ContentItem:
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise NotFoundError("Content item not found")

    updates = payload.model_dump(exclude_unset=True)
    for key in {
        "title",
        "hook",
        "script_md",
        "description_md",
        "tags_csv",
        "external_url",
        "review_reason",
        "editorial_owner_name",
        "last_change_summary",
    }:
        if key in updates:
            updates[key] = _normalize_optional_text(updates.get(key))

    if "platform_meta_json" in updates:
        candidate_platform = updates.get("platform", item.platform)
        _validate_platform_meta(
            db,
            platform=candidate_platform,
            platform_meta_json=updates.get("platform_meta_json") or {},
        )

    if "product_id" in updates:
        _ensure_product_link_valid(db, product_id=updates.get("product_id"))

    requested_workflow_status = updates.pop("workflow_status", None)
    explicit_review_reason = updates.pop("review_reason", None)
    target_status = updates.get("status", item.status)
    target_planned_date = updates.get("planned_date", item.planned_date)
    target_publish_date = updates.get("publish_date", item.publish_date)
    target_external_url = updates.get("external_url", item.external_url)

    validate_content_status_change(
        current_status=item.status,
        target_status=target_status,
        planned_date=target_planned_date,
        publish_date=target_publish_date,
        external_url=target_external_url,
    )

    previous_status = item.status
    previous_workflow_status = item.workflow_status
    previous_review_reason = item.review_reason
    before: dict[str, str | int | bool | None] = {}
    after: dict[str, str | int | bool | None] = {}
    changed_fields: set[str] = set()

    for key, value in updates.items():
        if getattr(item, key) != value:
            changed_fields.add(key)

    target_workflow_status = requested_workflow_status or item.workflow_status
    review_reason = (
        explicit_review_reason if explicit_review_reason is not None else item.review_reason
    )
    if requested_workflow_status is None and requires_re_review(
        current_status=item.workflow_status,
        changed_fields=changed_fields,
        relevant_fields=CONTENT_RE_REVIEW_FIELDS,
    ):
        target_workflow_status = WorkflowStatus.in_review
        if explicit_review_reason is None:
            review_reason = auto_re_review_reason(changed_fields)

    validate_workflow_status_change(
        current_status=item.workflow_status,
        target_status=target_workflow_status,
        review_reason=review_reason,
    )

    with transaction_boundary(db):
        if (
            target_status != previous_status
            and target_status == ContentStatus.published
            and not target_publish_date
        ):
            updates["publish_date"] = date.today()

        for key, value in updates.items():
            current = getattr(item, key)
            if current == value:
                continue
            before[key] = _serialize_value(current)
            setattr(item, key, value)
            after[key] = _serialize_value(value)

        _ensure_primary_asset_link_valid(
            db,
            content_item_id=item.id,
            primary_asset_id=item.primary_asset_id,
        )

        if previous_workflow_status != target_workflow_status:
            apply_workflow_change(
                entity=item,
                target_status=target_workflow_status,
                review_reason=review_reason,
                actor=actor,
            )
            before["workflow_status"] = previous_workflow_status.value
            after["workflow_status"] = item.workflow_status.value
            before["review_reason"] = previous_review_reason
            after["review_reason"] = item.review_reason
        elif explicit_review_reason is not None and explicit_review_reason != item.review_reason:
            before["review_reason"] = item.review_reason
            item.review_reason = explicit_review_reason.strip() or None
            after["review_reason"] = item.review_reason

        if (
            previous_workflow_status != item.workflow_status
            and item.workflow_status == WorkflowStatus.approved
        ):
            before["review_cycle"] = item.review_cycle
            item.review_cycle += 1
            after["review_cycle"] = item.review_cycle

        _refresh_item_readiness(db, item=item)

        if target_status == ContentStatus.published and previous_status != ContentStatus.published:
            _ensure_publish_ready(item, db)
            before["published_at"] = item.published_at.isoformat() if item.published_at else None
            before["published_by_id"] = str(item.published_by_id) if item.published_by_id else None
            before["published_by_name"] = item.published_by_name
            item.published_at = utcnow()
            item.published_by_id = actor.id if actor else None
            item.published_by_name = actor.username if actor else None
            after["published_at"] = item.published_at.isoformat()
            after["published_by_id"] = str(item.published_by_id) if item.published_by_id else None
            after["published_by_name"] = item.published_by_name

        if target_status != ContentStatus.published and item.published_at is not None:
            before["published_at"] = item.published_at.isoformat()
            item.published_at = None
            item.published_by_id = None
            item.published_by_name = None
            after["published_at"] = None

        resolved_editorial_status = _resolve_editorial_status(
            item_status=item.status,
            workflow_status=item.workflow_status,
            fallback=item.editorial_status,
        )
        if item.editorial_status != resolved_editorial_status:
            before["editorial_status"] = item.editorial_status.value
            item.editorial_status = resolved_editorial_status
            after["editorial_status"] = item.editorial_status.value

        if before and any(field in before for field in CONTENT_REVISION_FIELDS):
            _append_item_revision(
                db,
                item=item,
                before={k: _serialize_value(v) for k, v in before.items()},
                after={k: _serialize_value(v) for k, v in after.items()},
                actor=actor,
                change_summary=item.last_change_summary,
            )

        if before:
            record_audit_log(
                db,
                actor=actor,
                action="content.item.update",
                entity_type="content_item",
                entity_id=str(item.id),
                description=f"Updated content item '{item.title or item.id}'",
                before=before,
                after=after,
            )

        if previous_status != item.status:
            emit_domain_event(
                db,
                actor=actor,
                event_name="content.status.changed",
                entity_type="content_item",
                entity_id=str(item.id),
                payload={
                    "from": previous_status.value,
                    "to": item.status.value,
                    "planned_date": (
                        item.planned_date.isoformat()
                        if getattr(item, "planned_date", None)
                        else None
                    ),
                    "publish_date": (
                        item.publish_date.isoformat()
                        if getattr(item, "publish_date", None)
                        else None
                    ),
                },
                description=f"Content status changed: {previous_status.value} -> {item.status.value}",
            )

        if previous_workflow_status != item.workflow_status:
            emit_domain_event(
                db,
                actor=actor,
                event_name="content.workflow.changed",
                entity_type="content_item",
                entity_id=str(item.id),
                payload={
                    "from": previous_workflow_status.value,
                    "to": item.workflow_status.value,
                    "review_reason": item.review_reason,
                    "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
                    "reviewed_by_id": str(item.reviewed_by_id) if item.reviewed_by_id else None,
                    "reviewed_by_name": item.reviewed_by_name,
                },
                description=(
                    f"Content workflow changed: {previous_workflow_status.value} -> {item.workflow_status.value}"
                ),
            )

    db.refresh(item)
    return _enrich_content_item(item, db)


def delete_item(db: Session, *, item_id: uuid.UUID, actor: User | None) -> None:
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise NotFoundError("Content item not found")

    snapshot = {
        "title": item.title,
        "status": item.status.value,
        "platform": item.platform.value,
        "type": item.type.value,
    }
    with transaction_boundary(db):
        record_audit_log(
            db,
            actor=actor,
            action="content.item.delete",
            entity_type="content_item",
            entity_id=str(item.id),
            description=f"Deleted content item '{item.title or item.id}'",
            before=snapshot,
        )
        db.delete(item)


def list_tasks(db: Session, *, content_item_id: uuid.UUID | None = None) -> list[ContentTask]:
    filters = ContentTaskFilterParams(content_item_id=content_item_id)
    q = _apply_task_filters(db.query(ContentTask), filters=filters)
    return q.order_by(ContentTask.updated_at.desc()).all()


def list_tasks_filtered(db: Session, *, filters: ContentTaskFilterParams) -> list[ContentTask]:
    q = _apply_task_filters(db.query(ContentTask), filters=filters)
    return q.order_by(ContentTask.updated_at.desc()).all()


def list_personal_tasks(
    db: Session,
    *,
    user: User,
    filters: ContentTaskFilterParams,
) -> list[ContentTask]:
    q = _apply_task_filters(db.query(ContentTask), filters=filters)
    q = q.filter(
        (ContentTask.assignee_user_id == user.id)
        | ((ContentTask.assignee_user_id.is_(None)) & (ContentTask.assignee_role == user.role))
    )
    return q.order_by(
        ContentTask.priority.desc(), ContentTask.due_date.asc(), ContentTask.updated_at.desc()
    ).all()


def list_personal_tasks_page(
    db: Session,
    *,
    user: User,
    filters: ContentTaskFilterParams,
    limit: int,
    offset: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[ContentTask], int, str]:
    q = _apply_task_filters(db.query(ContentTask), filters=filters)
    q = q.filter(
        (ContentTask.assignee_user_id == user.id)
        | ((ContentTask.assignee_user_id.is_(None)) & (ContentTask.assignee_role == user.role))
    )
    total = q.order_by(None).count()
    allowed_sort_fields = {
        "created_at",
        "updated_at",
        "status",
        "type",
        "due_date",
        "priority",
    }
    selected_sort = sort_by if sort_by in allowed_sort_fields else "updated_at"
    sort_column = getattr(ContentTask, selected_sort)
    ordering = sort_column.asc() if sort_order == SortOrder.asc else sort_column.desc()
    items = q.order_by(ordering).offset(offset).limit(limit).all()
    return items, total, selected_sort


def list_task_views(db: Session, *, user: User) -> list[ContentTaskView]:
    return (
        db.query(ContentTaskView)
        .filter((ContentTaskView.user_id == user.id) | (ContentTaskView.is_shared.is_(True)))
        .order_by(ContentTaskView.updated_at.desc())
        .all()
    )


def create_task_view(db: Session, *, user: User, payload: ContentTaskViewCreate) -> ContentTaskView:
    view = ContentTaskView(
        user_id=user.id,
        name=payload.name.strip(),
        is_shared=payload.is_shared,
        filters=payload.filters,
    )
    with transaction_boundary(db):
        db.add(view)
        db.flush()
        record_audit_log(
            db,
            actor=user,
            action="content.task_view.create",
            entity_type="content_task_view",
            entity_id=str(view.id),
            description=f"Created task view '{view.name}'",
            after={"is_shared": view.is_shared, "filters": view.filters},
        )
    db.refresh(view)
    return view


def delete_task_view(db: Session, *, view_id: uuid.UUID, user: User) -> None:
    view = db.query(ContentTaskView).filter(ContentTaskView.id == view_id).first()
    if not view:
        raise NotFoundError("Task view not found")
    if view.user_id != user.id:
        raise NotFoundError("Task view not found")

    with transaction_boundary(db):
        record_audit_log(
            db,
            actor=user,
            action="content.task_view.delete",
            entity_type="content_task_view",
            entity_id=str(view.id),
            description=f"Deleted task view '{view.name}'",
            before={"is_shared": view.is_shared, "filters": view.filters},
        )
        db.delete(view)


def create_task(db: Session, *, payload: ContentTaskCreate, actor: User | None) -> ContentTask:
    task_data = payload.model_dump()
    task_data["title"] = _normalize_optional_text(task_data.get("title"))
    task = ContentTask(**task_data)
    if task.title is None:
        task.title = task.type.value.replace("_", " ").title()
    _validate_task_assignment(task.assignee_user_id, task.assignee_role)
    _validate_task_dependency(
        db,
        task_id=task.id,
        content_item_id=task.content_item_id,
        blocked_by_task_id=task.blocked_by_task_id,
    )
    with transaction_boundary(db):
        db.add(task)
        db.flush()
        _sync_task_completion(task)
        _apply_task_notification_and_escalation(task, actor=actor, db=db)
        record_audit_log(
            db,
            actor=actor,
            action="content.task.create",
            entity_type="content_task",
            entity_id=str(task.id),
            description=f"Created content task '{task.title or task.type.value}'",
            after={
                "title": task.title,
                "status": task.status.value,
                "priority": task.priority.value,
                "type": task.type.value,
                "assignee_user_id": str(task.assignee_user_id) if task.assignee_user_id else None,
                "assignee_role": task.assignee_role.value if task.assignee_role else None,
                "blocked_by_task_id": (
                    str(task.blocked_by_task_id) if task.blocked_by_task_id else None
                ),
                "content_item_id": str(task.content_item_id),
            },
        )
        item = db.query(ContentItem).filter(ContentItem.id == task.content_item_id).first()
        if item:
            _refresh_item_readiness(db, item=item)
    db.refresh(task)
    return task


def update_task(
    db: Session,
    *,
    task_id: uuid.UUID,
    payload: ContentTaskUpdate,
    actor: User | None,
) -> ContentTask:
    task = db.query(ContentTask).filter(ContentTask.id == task_id).first()
    if not task:
        raise NotFoundError("Content task not found")

    updates = payload.model_dump(exclude_unset=True)
    if "title" in updates:
        updates["title"] = _normalize_optional_text(updates.get("title"))
    before: dict[str, str | int | bool | None] = {}
    after: dict[str, str | int | bool | None] = {}

    target_assignee_user_id = updates.get("assignee_user_id", task.assignee_user_id)
    target_assignee_role = updates.get("assignee_role", task.assignee_role)
    _validate_task_assignment(target_assignee_user_id, target_assignee_role)
    target_blocked_by = updates.get("blocked_by_task_id", task.blocked_by_task_id)
    _validate_task_dependency(
        db,
        task_id=task.id,
        content_item_id=task.content_item_id,
        blocked_by_task_id=target_blocked_by,
    )

    with transaction_boundary(db):
        for key, value in updates.items():
            current = getattr(task, key)
            if current == value:
                continue
            before[key] = _serialize_value(current)
            setattr(task, key, value)
            after[key] = _serialize_value(value)

        _sync_task_completion(task)

        _apply_task_notification_and_escalation(task, actor=actor, db=db)

        if before:
            record_audit_log(
                db,
                actor=actor,
                action="content.task.update",
                entity_type="content_task",
                entity_id=str(task.id),
                description=f"Updated content task '{task.id}'",
                before=before,
                after=after,
            )

        item = db.query(ContentItem).filter(ContentItem.id == task.content_item_id).first()
        if item:
            _refresh_item_readiness(db, item=item)

    db.refresh(task)
    return task


def delete_task(db: Session, *, task_id: uuid.UUID, actor: User | None) -> None:
    task = db.query(ContentTask).filter(ContentTask.id == task_id).first()
    if not task:
        raise NotFoundError("Content task not found")

    snapshot = {
        "status": task.status.value,
        "type": task.type.value,
        "content_item_id": str(task.content_item_id),
    }
    with transaction_boundary(db):
        record_audit_log(
            db,
            actor=actor,
            action="content.task.delete",
            entity_type="content_task",
            entity_id=str(task.id),
            description=f"Deleted content task '{task.id}'",
            before=snapshot,
        )
        item = db.query(ContentItem).filter(ContentItem.id == task.content_item_id).first()
        db.delete(task)
        if item:
            _refresh_item_readiness(db, item=item)


def _validate_task_assignment(
    assignee_user_id: uuid.UUID | None,
    assignee_role: UserRole | None,
) -> None:
    if assignee_user_id is not None and assignee_role is not None:
        raise BusinessRuleViolation("assign either assignee_user_id or assignee_role, not both")


def _validate_task_dependency(
    db: Session,
    *,
    task_id: uuid.UUID,
    content_item_id: uuid.UUID,
    blocked_by_task_id: uuid.UUID | None,
) -> None:
    if blocked_by_task_id is None:
        return
    if blocked_by_task_id == task_id:
        raise BusinessRuleViolation("task cannot be blocked by itself")
    blocked_by = db.query(ContentTask).filter(ContentTask.id == blocked_by_task_id).first()
    if not blocked_by:
        raise BusinessRuleViolation("blocked_by_task_id not found")
    if blocked_by.content_item_id != content_item_id:
        raise BusinessRuleViolation("task dependency must belong to the same content item")


def _sync_task_completion(task: ContentTask) -> None:
    if task.status == TaskStatus.done and task.completed_at is None:
        task.completed_at = utcnow()
    if task.status != TaskStatus.done and task.completed_at is not None:
        task.completed_at = None


def _apply_task_filters(query, *, filters: ContentTaskFilterParams):
    if filters.content_item_id:
        query = query.filter(ContentTask.content_item_id == filters.content_item_id)
    if filters.assignee_user_id:
        query = query.filter(ContentTask.assignee_user_id == filters.assignee_user_id)
    if filters.assignee_role:
        query = query.filter(ContentTask.assignee_role == filters.assignee_role)
    if filters.priority:
        query = query.filter(ContentTask.priority == filters.priority)
    if filters.status:
        query = query.filter(ContentTask.status == filters.status)
    if filters.overdue_only:
        query = query.filter(
            ContentTask.due_date.isnot(None),
            ContentTask.due_date < date.today(),
            ContentTask.status != TaskStatus.done,
        )
    return query


def _apply_task_notification_and_escalation(
    task: ContentTask,
    *,
    actor: User | None,
    db: Session,
) -> None:
    if task.status == TaskStatus.done:
        return
    now = utcnow()
    if task.due_date is not None and task.notified_at is None:
        if (task.due_date - date.today()).days <= 1:
            task.notified_at = now
            emit_domain_event(
                db,
                actor=actor,
                event_name="content.task.notification_due_soon",
                entity_type="content_task",
                entity_id=str(task.id),
                payload={
                    "due_date": task.due_date.isoformat(),
                    "priority": task.priority.value,
                },
                description="Task due soon notification emitted",
            )

    if task.due_date is not None and task.due_date < date.today() and task.escalated_at is None:
        task.escalated_at = now
        emit_domain_event(
            db,
            actor=actor,
            event_name="content.task.escalated_overdue",
            entity_type="content_task",
            entity_id=str(task.id),
            payload={
                "due_date": task.due_date.isoformat(),
                "priority": task.priority.value,
            },
            description="Task overdue escalation emitted",
        )


def list_platform_profiles(
    db: Session,
    *,
    platform=None,
) -> list[ContentPlatformProfile]:
    query = db.query(ContentPlatformProfile)
    if platform is not None:
        query = query.filter(ContentPlatformProfile.platform == platform)
    return query.order_by(
        ContentPlatformProfile.platform.asc(), ContentPlatformProfile.updated_at.desc()
    ).all()


def create_platform_profile(
    db: Session,
    *,
    payload: ContentPlatformProfileCreate,
    actor: User,
) -> ContentPlatformProfile:
    profile = ContentPlatformProfile(
        platform=payload.platform,
        name=payload.name.strip(),
        schema_json=payload.profile_schema,
        is_active=payload.is_active,
        is_system=payload.is_system,
        owner_user_id=actor.id,
    )
    with transaction_boundary(db):
        db.add(profile)
        db.flush()
        record_audit_log(
            db,
            actor=actor,
            action="content.platform_profile.create",
            entity_type="content_platform_profile",
            entity_id=str(profile.id),
            description=f"Created content platform profile '{profile.name}'",
            after={
                "platform": profile.platform.value,
                "is_active": profile.is_active,
                "version": profile.version,
            },
        )
    db.refresh(profile)
    return profile


def update_platform_profile(
    db: Session,
    *,
    profile_id: uuid.UUID,
    payload: ContentPlatformProfileUpdate,
    actor: User,
) -> ContentPlatformProfile:
    profile = (
        db.query(ContentPlatformProfile).filter(ContentPlatformProfile.id == profile_id).first()
    )
    if not profile:
        raise NotFoundError("Platform profile not found")

    updates = payload.model_dump(exclude_unset=True, by_alias=True)
    before: dict[str, str | int | bool | None] = {}
    after: dict[str, str | int | bool | None] = {}
    with transaction_boundary(db):
        for key, value in updates.items():
            current = getattr(profile, key)
            if current == value:
                continue
            before[key] = _serialize_value(current)
            setattr(profile, key, value)
            after[key] = _serialize_value(value)
        if before:
            before["version"] = profile.version
            profile.version += 1
            after["version"] = profile.version
            record_audit_log(
                db,
                actor=actor,
                action="content.platform_profile.update",
                entity_type="content_platform_profile",
                entity_id=str(profile.id),
                description=f"Updated content platform profile '{profile.name}'",
                before=before,
                after=after,
            )
    db.refresh(profile)
    return profile


def delete_platform_profile(db: Session, *, profile_id: uuid.UUID, actor: User) -> None:
    profile = (
        db.query(ContentPlatformProfile).filter(ContentPlatformProfile.id == profile_id).first()
    )
    if not profile:
        raise NotFoundError("Platform profile not found")
    with transaction_boundary(db):
        record_audit_log(
            db,
            actor=actor,
            action="content.platform_profile.delete",
            entity_type="content_platform_profile",
            entity_id=str(profile.id),
            description=f"Deleted content platform profile '{profile.name}'",
            before={"platform": profile.platform.value, "name": profile.name},
        )
        db.delete(profile)


def list_checklist_templates(
    db: Session,
    *,
    platform=None,
    content_type=None,
) -> list[ContentChecklistTemplate]:
    query = db.query(ContentChecklistTemplate)
    if platform is not None:
        query = query.filter(
            (ContentChecklistTemplate.applies_to_platform == platform)
            | (ContentChecklistTemplate.applies_to_platform.is_(None))
        )
    if content_type is not None:
        query = query.filter(
            (ContentChecklistTemplate.applies_to_type == content_type)
            | (ContentChecklistTemplate.applies_to_type.is_(None))
        )
    return query.order_by(ContentChecklistTemplate.updated_at.desc()).all()


def create_checklist_template(
    db: Session,
    *,
    payload: ContentChecklistTemplateCreate,
    actor: User,
) -> ContentChecklistTemplate:
    name = payload.name.strip()
    if not name:
        raise BusinessRuleViolation("Template name must not be empty")
    template = ContentChecklistTemplate(
        name=name,
        description=_normalize_optional_text(payload.description),
        applies_to_platform=payload.applies_to_platform,
        applies_to_type=payload.applies_to_type,
        is_shared=payload.is_shared,
        is_system=payload.is_system,
        owner_user_id=actor.id,
    )
    with transaction_boundary(db):
        db.add(template)
        db.flush()
        for index, item in enumerate(payload.items):
            db.add(
                ContentChecklistTemplateItem(
                    template_id=template.id,
                    title=item.title.strip(),
                    phase=item.phase,
                    required=item.required,
                    priority_default=item.priority_default,
                    due_offset_days=item.due_offset_days,
                    can_block_publish=item.can_block_publish,
                    sort_order=item.sort_order if item.sort_order is not None else index,
                )
            )
        db.flush()
        record_audit_log(
            db,
            actor=actor,
            action="content.checklist_template.create",
            entity_type="content_checklist_template",
            entity_id=str(template.id),
            description=f"Created checklist template '{template.name}'",
            after={
                "item_count": len(payload.items),
                "is_shared": template.is_shared,
                "applies_to_platform": (
                    template.applies_to_platform.value if template.applies_to_platform else None
                ),
                "applies_to_type": template.applies_to_type.value
                if template.applies_to_type
                else None,
            },
        )
    db.refresh(template)
    return template


def update_checklist_template(
    db: Session,
    *,
    template_id: uuid.UUID,
    payload: ContentChecklistTemplateUpdate,
    actor: User,
) -> ContentChecklistTemplate:
    template = (
        db.query(ContentChecklistTemplate)
        .filter(ContentChecklistTemplate.id == template_id)
        .first()
    )
    if not template:
        raise NotFoundError("Checklist template not found")

    updates = payload.model_dump(exclude_unset=True)
    before: dict[str, str | int | bool | None] = {}
    after: dict[str, str | int | bool | None] = {}
    with transaction_boundary(db):
        items_payload = updates.pop("items", None)
        if "name" in updates:
            updates["name"] = updates["name"].strip() if updates["name"] else ""
            if not updates["name"]:
                raise BusinessRuleViolation("Template name must not be empty")
        if "description" in updates:
            updates["description"] = _normalize_optional_text(updates.get("description"))

        for key, value in updates.items():
            current = getattr(template, key)
            if current == value:
                continue
            before[key] = _serialize_value(current)
            setattr(template, key, value)
            after[key] = _serialize_value(value)

        if items_payload is not None:
            before["item_count"] = len(template.items)
            db.query(ContentChecklistTemplateItem).filter(
                ContentChecklistTemplateItem.template_id == template.id
            ).delete()
            for index, item in enumerate(items_payload):
                db.add(
                    ContentChecklistTemplateItem(
                        template_id=template.id,
                        title=item["title"].strip(),
                        phase=item["phase"],
                        required=item["required"],
                        priority_default=item["priority_default"],
                        due_offset_days=item.get("due_offset_days"),
                        can_block_publish=item["can_block_publish"],
                        sort_order=item.get("sort_order", index),
                    )
                )
            after["item_count"] = len(items_payload)

        if before:
            before["version"] = template.version
            template.version += 1
            after["version"] = template.version
            record_audit_log(
                db,
                actor=actor,
                action="content.checklist_template.update",
                entity_type="content_checklist_template",
                entity_id=str(template.id),
                description=f"Updated checklist template '{template.name}'",
                before=before,
                after=after,
            )
    db.refresh(template)
    return template


def delete_checklist_template(db: Session, *, template_id: uuid.UUID, actor: User) -> None:
    template = (
        db.query(ContentChecklistTemplate)
        .filter(ContentChecklistTemplate.id == template_id)
        .first()
    )
    if not template:
        raise NotFoundError("Checklist template not found")
    with transaction_boundary(db):
        record_audit_log(
            db,
            actor=actor,
            action="content.checklist_template.delete",
            entity_type="content_checklist_template",
            entity_id=str(template.id),
            description=f"Deleted checklist template '{template.name}'",
            before={"name": template.name, "version": template.version},
        )
        db.delete(template)


def apply_checklist_template(
    db: Session,
    *,
    item_id: uuid.UUID,
    payload: ContentTemplateApplyRequest,
    actor: User,
) -> tuple[ContentItem, int, list[str]]:
    if payload.merge_mode not in VALID_TEMPLATE_MERGE_MODES:
        raise BusinessRuleViolation("merge_mode must be one of: replace, append")

    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise NotFoundError("Content item not found")
    template = (
        db.query(ContentChecklistTemplate)
        .filter(ContentChecklistTemplate.id == payload.template_id)
        .first()
    )
    if not template:
        raise NotFoundError("Checklist template not found")

    warnings: list[str] = []
    created_count = 0
    template_items = (
        db.query(ContentChecklistTemplateItem)
        .filter(ContentChecklistTemplateItem.template_id == template.id)
        .order_by(
            ContentChecklistTemplateItem.sort_order.asc(),
            ContentChecklistTemplateItem.created_at.asc(),
        )
        .all()
    )
    snapshot_payload: dict[str, str | int | bool | float | None] = {
        "template_name": template.name,
        "template_version": template.version,
        "platform": template.applies_to_platform.value if template.applies_to_platform else "",
        "content_type": template.applies_to_type.value if template.applies_to_type else "",
        "item_count": len(template_items),
    }

    with transaction_boundary(db):
        snapshot = ContentChecklistSnapshot(
            content_item_id=item.id,
            template_id=template.id,
            template_version=template.version,
            snapshot_json=snapshot_payload,
            created_by_user_id=actor.id,
        )
        db.add(snapshot)
        db.flush()

        if payload.merge_mode == "replace":
            existing_tasks = (
                db.query(ContentTask).filter(ContentTask.content_item_id == item.id).all()
            )
            for existing in existing_tasks:
                if payload.keep_done_tasks and existing.status == TaskStatus.done:
                    continue
                db.delete(existing)

        base_date = item.publish_date or item.planned_date
        for template_item in template_items:
            due_date = None
            if base_date is not None and template_item.due_offset_days is not None:
                due_date = base_date + timedelta(days=template_item.due_offset_days)
            db.add(
                ContentTask(
                    content_item_id=item.id,
                    type=TaskType.publish
                    if template_item.phase == ChecklistPhase.upload
                    else TaskType.record,
                    title=template_item.title,
                    status=TaskStatus.todo,
                    priority=template_item.priority_default,
                    due_date=due_date,
                    notes=f"Template: {template.name} ({template_item.phase.value})",
                    required_for_publish=template_item.required,
                    can_block_publish=template_item.can_block_publish,
                    checklist_snapshot_id=snapshot.id,
                )
            )
            created_count += 1

        item.applied_template_snapshot_id = snapshot.id
        _refresh_item_readiness(db, item=item)
        record_audit_log(
            db,
            actor=actor,
            action="content.checklist_template.apply",
            entity_type="content_item",
            entity_id=str(item.id),
            description=f"Applied checklist template '{template.name}'",
            after={
                "template_id": str(template.id),
                "template_version": template.version,
                "created_tasks_count": created_count,
                "merge_mode": payload.merge_mode,
                "keep_done_tasks": payload.keep_done_tasks,
            },
        )

    db.refresh(item)
    return _enrich_content_item(item, db), created_count, warnings


def get_planning_view(
    db: Session, *, item_id: uuid.UUID
) -> tuple[ContentItem, list[ContentTask], list[str], bool]:
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise NotFoundError("Content item not found")
    tasks = (
        db.query(ContentTask)
        .filter(ContentTask.content_item_id == item.id)
        .order_by(ContentTask.due_date.asc().nulls_last(), ContentTask.created_at.asc())
        .all()
    )
    missing_required_platform_fields = _validate_platform_meta(
        db,
        platform=item.platform,
        platform_meta_json=item.platform_meta_json,
    )
    missing_required_base_fields = _missing_required_base_fields(db, item=item)
    blockers: list[str] = []
    if missing_required_base_fields:
        blockers.append(
            "Missing required content fields: " + ", ".join(missing_required_base_fields)
        )
    if missing_required_platform_fields:
        blockers.append(
            "Missing required platform fields: " + ", ".join(missing_required_platform_fields)
        )

    required_open_tasks = [
        task
        for task in tasks
        if task.required_for_publish and task.can_block_publish and task.status != TaskStatus.done
    ]
    if required_open_tasks:
        blockers.append("Required checklist tasks are open")

    approved_assets = (
        db.query(Asset.id)
        .filter(
            Asset.owner_type == AssetOwnerType.content,
            Asset.owner_id == item.id,
            Asset.review_state == AssetReviewState.approved,
        )
        .count()
    )
    if approved_assets <= 0:
        blockers.append("No approved asset linked")

    _refresh_item_readiness(db, item=item)
    publish_ready = len(blockers) == 0
    return _enrich_content_item(item, db), tasks, blockers, publish_ready
