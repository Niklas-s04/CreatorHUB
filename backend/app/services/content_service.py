from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.content import (
    ContentItem,
    ContentStatus,
    ContentTask,
    ContentTaskView,
    TaskStatus,
)
from app.models.user import User, UserRole
from app.models.workflow import WorkflowStatus
from app.schemas.content import (
    ContentItemCreate,
    ContentItemUpdate,
    ContentTaskCreate,
    ContentTaskFilterParams,
    ContentTaskUpdate,
    ContentTaskViewCreate,
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


def list_items(db: Session, *, product_id: uuid.UUID | None = None) -> list[ContentItem]:
    q = db.query(ContentItem)
    if product_id:
        q = q.filter(ContentItem.product_id == product_id)
    return q.order_by(ContentItem.updated_at.desc()).all()


def create_item(db: Session, *, payload: ContentItemCreate, actor: User | None) -> ContentItem:
    item = ContentItem(**payload.model_dump())
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
    with transaction_boundary(db):
        db.add(item)
        db.flush()
        created_tasks = ensure_default_tasks_for_item(db, item)
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
                "platform": item.platform.value,
                "type": item.type.value,
                "default_tasks_created": created_tasks,
            },
        )
    db.refresh(item)
    return item


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
    before: dict[str, str | None] = {}
    after: dict[str, str | None] = {}
    changed_fields: set[str] = set()

    for key, value in updates.items():
        if getattr(item, key) != value:
            changed_fields.add(key)

    target_workflow_status = requested_workflow_status or item.workflow_status
    review_reason = explicit_review_reason
    if requested_workflow_status is None and requires_re_review(
        current_status=item.workflow_status,
        changed_fields=changed_fields,
        relevant_fields=CONTENT_RE_REVIEW_FIELDS,
    ):
        target_workflow_status = WorkflowStatus.in_review
        review_reason = review_reason or auto_re_review_reason(changed_fields)

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
            before[key] = getattr(current, "value", current)
            setattr(item, key, value)
            after[key] = getattr(value, "value", value)

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
    return item


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
    task = ContentTask(**payload.model_dump())
    _validate_task_assignment(task.assignee_user_id, task.assignee_role)
    with transaction_boundary(db):
        db.add(task)
        db.flush()
        _apply_task_notification_and_escalation(task, actor=actor, db=db)
        record_audit_log(
            db,
            actor=actor,
            action="content.task.create",
            entity_type="content_task",
            entity_id=str(task.id),
            description=f"Created content task '{task.type.value}'",
            after={
                "status": task.status.value,
                "priority": task.priority.value,
                "type": task.type.value,
                "assignee_user_id": str(task.assignee_user_id) if task.assignee_user_id else None,
                "assignee_role": task.assignee_role.value if task.assignee_role else None,
                "content_item_id": str(task.content_item_id),
            },
        )
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
    before: dict[str, str | None] = {}
    after: dict[str, str | None] = {}

    target_assignee_user_id = updates.get("assignee_user_id", task.assignee_user_id)
    target_assignee_role = updates.get("assignee_role", task.assignee_role)
    _validate_task_assignment(target_assignee_user_id, target_assignee_role)

    with transaction_boundary(db):
        for key, value in updates.items():
            current = getattr(task, key)
            if current == value:
                continue
            before[key] = getattr(current, "value", current)
            setattr(task, key, value)
            after[key] = getattr(value, "value", value)

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
        db.delete(task)


def _validate_task_assignment(
    assignee_user_id: uuid.UUID | None,
    assignee_role: UserRole | None,
) -> None:
    if assignee_user_id is not None and assignee_role is not None:
        raise BusinessRuleViolation("assign either assignee_user_id or assignee_role, not both")


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
