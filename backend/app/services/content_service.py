from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.content import ContentItem, ContentStatus, ContentTask
from app.models.user import User
from app.schemas.content import (
    ContentItemCreate,
    ContentItemUpdate,
    ContentTaskCreate,
    ContentTaskUpdate,
)
from app.services.audit import record_audit_log
from app.services.content_task_defaults import ensure_default_tasks_for_item
from app.services.domain_events import emit_domain_event
from app.services.domain_rules import validate_content_status_change
from app.services.errors import NotFoundError
from app.services.transactions import transaction_boundary


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
    before: dict[str, str | None] = {}
    after: dict[str, str | None] = {}

    with transaction_boundary(db):
        if target_status != previous_status and target_status == ContentStatus.published and not target_publish_date:
            updates["publish_date"] = date.today()

        for key, value in updates.items():
            current = getattr(item, key)
            if current == value:
                continue
            before[key] = getattr(current, "value", current)
            setattr(item, key, value)
            after[key] = getattr(value, "value", value)

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
                        item.planned_date.isoformat() if getattr(item, "planned_date", None) else None
                    ),
                    "publish_date": (
                        item.publish_date.isoformat() if getattr(item, "publish_date", None) else None
                    ),
                },
                description=f"Content status changed: {previous_status.value} -> {item.status.value}",
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
    q = db.query(ContentTask)
    if content_item_id:
        q = q.filter(ContentTask.content_item_id == content_item_id)
    return q.order_by(ContentTask.updated_at.desc()).all()


def create_task(db: Session, *, payload: ContentTaskCreate, actor: User | None) -> ContentTask:
    task = ContentTask(**payload.model_dump())
    with transaction_boundary(db):
        db.add(task)
        db.flush()
        record_audit_log(
            db,
            actor=actor,
            action="content.task.create",
            entity_type="content_task",
            entity_id=str(task.id),
            description=f"Created content task '{task.type.value}'",
            after={
                "status": task.status.value,
                "type": task.type.value,
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

    with transaction_boundary(db):
        for key, value in updates.items():
            current = getattr(task, key)
            if current == value:
                continue
            before[key] = getattr(current, "value", current)
            setattr(task, key, value)
            after[key] = getattr(value, "value", value)

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
