from __future__ import annotations

import uuid
from datetime import date

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
from app.models.content import (
    ContentItem,
    ContentPlatform,
    ContentTask,
    ContentType,
    EditorialStatus,
    TaskPriority,
    TaskStatus,
)
from app.models.user import User, UserRole
from app.schemas.common import Page, SortOrder
from app.schemas.content import (
    ContentChecklistTemplateCreate,
    ContentChecklistTemplateOut,
    ContentChecklistTemplateUpdate,
    ContentItemCreate,
    ContentItemOut,
    ContentItemUpdate,
    ContentPlanningViewOut,
    ContentPlatformProfileCreate,
    ContentPlatformProfileOut,
    ContentPlatformProfileUpdate,
    ContentTaskCreate,
    ContentTaskFilterParams,
    ContentTaskOut,
    ContentTaskUpdate,
    ContentTaskViewCreate,
    ContentTaskViewOut,
    ContentTemplateApplyRequest,
    ContentTemplateApplyResult,
)
from app.services import content_service
from app.services.errors import BusinessRuleViolation, NotFoundError

router = APIRouter()


@router.get("/items", response_model=Page[ContentItemOut])
def list_items(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    product_id: uuid.UUID | None = None,
    platform: ContentPlatform | None = None,
    editorial_status: EditorialStatus | None = None,
    publish_window_from: date | None = None,
    publish_window_to: date | None = None,
    readiness_min: int | None = None,
    paging: tuple[int, int, str, SortOrder] = Depends(pagination_params),
) -> Page[ContentItemOut]:
    limit, offset, sort_by, sort_order = paging
    qry = db.query(ContentItem)
    if product_id:
        qry = qry.filter(ContentItem.product_id == product_id)
    if platform:
        qry = qry.filter(ContentItem.platform == platform)
    if editorial_status:
        qry = qry.filter(ContentItem.editorial_status == editorial_status)
    if publish_window_from:
        qry = qry.filter(
            ContentItem.publish_date.isnot(None), ContentItem.publish_date >= publish_window_from
        )
    if publish_window_to:
        qry = qry.filter(
            ContentItem.publish_date.isnot(None), ContentItem.publish_date <= publish_window_to
        )
    if readiness_min is not None:
        qry = qry.filter(ContentItem.readiness_score >= readiness_min)

    total = qry.order_by(None).count()
    qry, selected_sort, selected_order = apply_sorting(
        qry,
        model=ContentItem,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields={
            "created_at",
            "updated_at",
            "status",
            "platform",
            "type",
            "editorial_status",
            "publish_date",
            "review_cycle",
        },
        fallback="updated_at",
    )
    raw_items = qry.offset(offset).limit(limit).all()
    items = [content_service.enrich_content_item(db, item) for item in raw_items]
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
    try:
        return content_service.create_item(db, payload=payload, actor=current_user)
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.get("/items/{item_id}/planning-view", response_model=ContentPlanningViewOut)
def get_item_planning_view(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ContentPlanningViewOut:
    try:
        item, tasks, blockers, publish_ready = content_service.get_planning_view(
            db, item_id=item_id
        )
        required_open_count = sum(
            1 for task in tasks if task.required_for_publish and task.status != TaskStatus.done
        )
        return ContentPlanningViewOut(
            item=item,
            tasks=tasks,
            open_task_count=sum(1 for task in tasks if task.status != TaskStatus.done),
            required_open_count=required_open_count,
            readiness_score=item.readiness_score,
            publish_ready=publish_ready,
            blockers=blockers,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/items/{item_id}/apply-template", response_model=ContentTemplateApplyResult)
def apply_template_to_item(
    item_id: uuid.UUID,
    payload: ContentTemplateApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
) -> ContentTemplateApplyResult:
    try:
        item, created_count, warnings = content_service.apply_checklist_template(
            db,
            item_id=item_id,
            payload=payload,
            actor=current_user,
        )
        return ContentTemplateApplyResult(
            item=item, created_tasks_count=created_count, warnings=warnings
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.get("/platform-profiles", response_model=list[ContentPlatformProfileOut])
def list_platform_profiles(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    platform: ContentPlatform | None = None,
) -> list[ContentPlatformProfileOut]:
    return content_service.list_platform_profiles(db, platform=platform)


@router.post("/platform-profiles", response_model=ContentPlatformProfileOut)
def create_platform_profile(
    payload: ContentPlatformProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
) -> ContentPlatformProfileOut:
    try:
        return content_service.create_platform_profile(db, payload=payload, actor=current_user)
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/platform-profiles/{profile_id}", response_model=ContentPlatformProfileOut)
def update_platform_profile(
    profile_id: uuid.UUID,
    payload: ContentPlatformProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
) -> ContentPlatformProfileOut:
    try:
        return content_service.update_platform_profile(
            db,
            profile_id=profile_id,
            payload=payload,
            actor=current_user,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/platform-profiles/{profile_id}")
def delete_platform_profile(
    profile_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
) -> dict:
    try:
        content_service.delete_platform_profile(db, profile_id=profile_id, actor=current_user)
        return {"deleted": True}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/checklist-templates", response_model=list[ContentChecklistTemplateOut])
def list_checklist_templates(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    platform: ContentPlatform | None = None,
    content_type: ContentType | None = None,
) -> list[ContentChecklistTemplateOut]:
    return content_service.list_checklist_templates(
        db,
        platform=platform,
        content_type=content_type,
    )


@router.post("/checklist-templates", response_model=ContentChecklistTemplateOut)
def create_checklist_template(
    payload: ContentChecklistTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
) -> ContentChecklistTemplateOut:
    try:
        return content_service.create_checklist_template(db, payload=payload, actor=current_user)
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/checklist-templates/{template_id}", response_model=ContentChecklistTemplateOut)
def update_checklist_template(
    template_id: uuid.UUID,
    payload: ContentChecklistTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
) -> ContentChecklistTemplateOut:
    try:
        return content_service.update_checklist_template(
            db,
            template_id=template_id,
            payload=payload,
            actor=current_user,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/checklist-templates/{template_id}")
def delete_checklist_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
) -> dict:
    try:
        content_service.delete_checklist_template(db, template_id=template_id, actor=current_user)
        return {"deleted": True}
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
