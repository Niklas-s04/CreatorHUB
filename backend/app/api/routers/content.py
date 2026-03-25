from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    SensitiveActionContext,
    get_current_user,
    get_db,
    require_permission,
    require_sensitive_action,
)
from app.api.querying import apply_sorting, pagination_params, to_page
from app.core.authorization import Permission
from app.models.content import ContentItem, ContentTask, TaskPriority, TaskStatus
from app.models.user import UserRole
from app.models.user import User
from app.schemas.common import Page, SortOrder
from app.schemas.content import (
    ContentItemCreate,
    ContentItemOut,
    ContentItemUpdate,
    ContentTaskCreate,
    ContentTaskFilterParams,
    ContentTaskOut,
    ContentTaskUpdate,
    ContentTaskViewCreate,
    ContentTaskViewOut,
)
from app.services import content_service
from app.services.errors import BusinessRuleViolation, NotFoundError

router = APIRouter()


@router.get("/items", response_model=Page[ContentItemOut])
def list_items(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    product_id: uuid.UUID | None = None,
    paging: tuple[int, int, str, SortOrder] = Depends(pagination_params),
) -> Page[ContentItemOut]:
    limit, offset, sort_by, sort_order = paging
    qry = db.query(ContentItem)
    if product_id:
        qry = qry.filter(ContentItem.product_id == product_id)

    total = qry.order_by(None).count()
    qry, selected_sort, selected_order = apply_sorting(
        qry,
        model=ContentItem,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields={"created_at", "updated_at", "status", "platform", "type"},
        fallback="updated_at",
    )
    items = qry.offset(offset).limit(limit).all()
    return to_page(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=selected_sort,
        sort_order=selected_order,
    )


@router.post("/items", response_model=ContentItemOut)
def create_item(
    payload: ContentItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
) -> ContentItemOut:
    return content_service.create_item(db, payload=payload, actor=current_user)


@router.patch("/items/{item_id}", response_model=ContentItemOut)
def update_item(
    item_id: uuid.UUID,
    payload: ContentItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
) -> ContentItemOut:
    try:
        return content_service.update_item(
            db,
            item_id=item_id,
            payload=payload,
            actor=current_user,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/items/{item_id}")
def delete_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
    _: SensitiveActionContext = Depends(require_sensitive_action("content.item.delete")),
) -> dict:
    try:
        content_service.delete_item(db, item_id=item_id, actor=current_user)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}


@router.get("/tasks", response_model=Page[ContentTaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    content_item_id: uuid.UUID | None = None,
    assignee_user_id: uuid.UUID | None = None,
    assignee_role: UserRole | None = None,
    priority: TaskPriority | None = None,
    status: TaskStatus | None = None,
    overdue_only: bool = Query(default=False),
    paging: tuple[int, int, str, SortOrder] = Depends(pagination_params),
) -> Page[ContentTaskOut]:
    limit, offset, sort_by, sort_order = paging
    qry = db.query(ContentTask)
    filters = ContentTaskFilterParams(
        content_item_id=content_item_id,
        assignee_user_id=assignee_user_id,
        assignee_role=assignee_role,
        priority=priority,
        status=status,
        overdue_only=overdue_only,
    )
    qry = content_service._apply_task_filters(qry, filters=filters)

    total = qry.order_by(None).count()
    qry, selected_sort, selected_order = apply_sorting(
        qry,
        model=ContentTask,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields={"created_at", "updated_at", "status", "type", "due_date"},
        fallback="updated_at",
    )
    items = qry.offset(offset).limit(limit).all()
    return to_page(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=selected_sort,
        sort_order=selected_order,
    )


@router.get("/tasks/me", response_model=Page[ContentTaskOut])
def list_my_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    priority: TaskPriority | None = None,
    status: TaskStatus | None = None,
    overdue_only: bool = Query(default=False),
    paging: tuple[int, int, str, SortOrder] = Depends(pagination_params),
) -> Page[ContentTaskOut]:
    limit, offset, sort_by, sort_order = paging
    filters = ContentTaskFilterParams(
        priority=priority,
        status=status,
        overdue_only=overdue_only,
    )
    items = content_service.list_personal_tasks(db, user=current_user, filters=filters)
    total = len(items)
    sliced = items[offset : offset + limit]
    return to_page(
        items=sliced,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/tasks/views", response_model=list[ContentTaskViewOut])
def list_task_views(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ContentTaskViewOut]:
    return content_service.list_task_views(db, user=current_user)


@router.post("/tasks/views", response_model=ContentTaskViewOut)
def create_task_view(
    payload: ContentTaskViewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContentTaskViewOut:
    return content_service.create_task_view(db, user=current_user, payload=payload)


@router.delete("/tasks/views/{view_id}")
def delete_task_view(
    view_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        content_service.delete_task_view(db, view_id=view_id, user=current_user)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}


@router.post("/tasks", response_model=ContentTaskOut)
def create_task(
    payload: ContentTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
) -> ContentTaskOut:
    try:
        return content_service.create_task(db, payload=payload, actor=current_user)
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/tasks/{task_id}", response_model=ContentTaskOut)
def update_task(
    task_id: uuid.UUID,
    payload: ContentTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
) -> ContentTaskOut:
    try:
        return content_service.update_task(
            db,
            task_id=task_id,
            payload=payload,
            actor=current_user,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
    _: SensitiveActionContext = Depends(require_sensitive_action("content.task.delete")),
) -> dict:
    try:
        content_service.delete_task(db, task_id=task_id, actor=current_user)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}
