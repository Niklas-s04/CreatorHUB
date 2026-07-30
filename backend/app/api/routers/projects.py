from __future__ import annotations

import uuid
from datetime import date
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import (
    SensitiveActionContext,
    get_db,
    require_permission,
    require_sensitive_action,
)
from app.api.querying import apply_sorting, pagination_params, to_page
from app.core.authorization import Permission
from app.models.project import PreviewStatus, Project, ProjectCategory, ProjectStatus
from app.models.user import User
from app.schemas.common import Page, SortOrder
from app.schemas.content import ContentItemCreate
from app.schemas.product import ProductCreate
from app.schemas.project import (
    ProjectCategoryCreate,
    ProjectCategoryOut,
    ProjectCategoryUpdate,
    ProjectCreate,
    ProjectDetailOut,
    ProjectOut,
    ProjectUpdate,
)
from app.services import project_service
from app.services.errors import BusinessRuleViolation, NotFoundError

router = APIRouter()


def _raise_service_error(exc: Exception) -> NoReturn:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/categories", response_model=list[ProjectCategoryOut])
def list_categories(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.project_read)),
) -> list[ProjectCategoryOut]:
    return project_service.list_categories(db, include_inactive=include_inactive)


@router.post("/categories", response_model=ProjectCategoryOut)
def create_category(
    payload: ProjectCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.project_manage)),
) -> ProjectCategoryOut:
    try:
        return project_service.create_category(db, payload=payload, actor=current_user)
    except BusinessRuleViolation as exc:
        _raise_service_error(exc)


@router.patch("/categories/{category_id}", response_model=ProjectCategoryOut)
def update_category(
    category_id: uuid.UUID,
    payload: ProjectCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.project_manage)),
) -> ProjectCategoryOut:
    try:
        return project_service.update_category(
            db, category_id=category_id, payload=payload, actor=current_user
        )
    except (NotFoundError, BusinessRuleViolation) as exc:
        _raise_service_error(exc)


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.project_manage)),
) -> dict[str, bool]:
    try:
        project_service.delete_category(db, category_id=category_id, actor=current_user)
    except NotFoundError as exc:
        _raise_service_error(exc)
    return {"deleted": True}


@router.get("", response_model=Page[ProjectOut])
def list_projects(
    q: str | None = None,
    status: ProjectStatus | None = None,
    category_id: uuid.UUID | None = None,
    preview_status: PreviewStatus | None = None,
    due_before: date | None = None,
    attention_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.project_read)),
    paging: tuple[int, int, str, SortOrder] = Depends(pagination_params),
) -> Page[ProjectOut]:
    limit, offset, sort_by, sort_order = paging
    query = db.query(Project).options(
        selectinload(Project.category),
        selectinload(Project.content_items),
        selectinload(Project.products),
    )
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Project.title.ilike(like),
                Project.goal.ilike(like),
                Project.brief_md.ilike(like),
                Project.owner_name.ilike(like),
                Project.category.has(ProjectCategory.name.ilike(like)),
            )
        )
    if status:
        query = query.filter(Project.status == status)
    if category_id:
        query = query.filter(Project.category_id == category_id)
    if preview_status:
        query = query.filter(Project.preview_status == preview_status)
    if due_before:
        query = query.filter(Project.due_date.isnot(None), Project.due_date <= due_before)
    if attention_only:
        today = date.today()
        query = query.filter(
            or_(
                Project.due_date < today,
                Project.preview_status.in_(
                    [
                        PreviewStatus.pending,
                        PreviewStatus.requested,
                        PreviewStatus.changes_requested,
                    ]
                ),
            )
        )
    total = query.order_by(None).count()
    query, selected_sort, selected_order = apply_sorting(
        query,
        model=Project,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields={
            "created_at",
            "updated_at",
            "title",
            "status",
            "priority",
            "due_date",
            "publish_date",
            "progress_percent",
        },
        fallback="updated_at",
    )
    projects = [
        project_service.enrich_project(project)
        for project in query.offset(offset).limit(limit).all()
    ]
    return to_page(
        items=projects,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=selected_sort,
        sort_order=selected_order,
    )


@router.post("", response_model=ProjectDetailOut)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.project_manage)),
) -> ProjectDetailOut:
    try:
        return project_service.create_project(db, payload=payload, actor=current_user)
    except BusinessRuleViolation as exc:
        _raise_service_error(exc)


@router.get("/{project_id}", response_model=ProjectDetailOut)
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.project_read)),
) -> ProjectDetailOut:
    try:
        return project_service.get_project(db, project_id)
    except NotFoundError as exc:
        _raise_service_error(exc)


@router.patch("/{project_id}", response_model=ProjectDetailOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.project_manage)),
) -> ProjectDetailOut:
    try:
        return project_service.update_project(
            db, project_id=project_id, payload=payload, actor=current_user
        )
    except (NotFoundError, BusinessRuleViolation) as exc:
        _raise_service_error(exc)


@router.delete("/{project_id}")
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.project_delete)),
    _: SensitiveActionContext = Depends(
        require_sensitive_action(
            "project.delete",
            confirmation_required=True,
            step_up_required=False,
        )
    ),
) -> dict[str, bool]:
    try:
        project_service.delete_project(db, project_id=project_id, actor=current_user)
    except NotFoundError as exc:
        _raise_service_error(exc)
    return {"deleted": True}


@router.post("/{project_id}/content/{content_item_id}", response_model=ProjectDetailOut)
def link_content(
    project_id: uuid.UUID,
    content_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.project_manage)),
) -> ProjectDetailOut:
    try:
        return project_service.link_content(
            db,
            project_id=project_id,
            content_item_id=content_item_id,
            actor=current_user,
        )
    except (NotFoundError, BusinessRuleViolation) as exc:
        _raise_service_error(exc)


@router.delete("/{project_id}/content/{content_item_id}", response_model=ProjectDetailOut)
def unlink_content(
    project_id: uuid.UUID,
    content_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.project_manage)),
) -> ProjectDetailOut:
    try:
        return project_service.unlink_content(
            db,
            project_id=project_id,
            content_item_id=content_item_id,
            actor=current_user,
        )
    except (NotFoundError, BusinessRuleViolation) as exc:
        _raise_service_error(exc)


@router.post("/{project_id}/content", response_model=ProjectDetailOut)
def create_linked_content(
    project_id: uuid.UUID,
    payload: ContentItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.content_manage)),
    _: User = Depends(require_permission(Permission.project_manage)),
) -> ProjectDetailOut:
    try:
        return project_service.create_linked_content(
            db, project_id=project_id, payload=payload, actor=current_user
        )
    except (NotFoundError, BusinessRuleViolation) as exc:
        _raise_service_error(exc)


@router.post("/{project_id}/products/{product_id}", response_model=ProjectDetailOut)
def link_product(
    project_id: uuid.UUID,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.project_manage)),
) -> ProjectDetailOut:
    try:
        return project_service.link_product(
            db, project_id=project_id, product_id=product_id, actor=current_user
        )
    except (NotFoundError, BusinessRuleViolation) as exc:
        _raise_service_error(exc)


@router.delete("/{project_id}/products/{product_id}", response_model=ProjectDetailOut)
def unlink_product(
    project_id: uuid.UUID,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.project_manage)),
) -> ProjectDetailOut:
    try:
        return project_service.unlink_product(
            db, project_id=project_id, product_id=product_id, actor=current_user
        )
    except (NotFoundError, BusinessRuleViolation) as exc:
        _raise_service_error(exc)


@router.post("/{project_id}/products", response_model=ProjectDetailOut)
def create_linked_product(
    project_id: uuid.UUID,
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.product_write)),
    _: User = Depends(require_permission(Permission.project_manage)),
) -> ProjectDetailOut:
    try:
        return project_service.create_linked_product(
            db, project_id=project_id, payload=payload, actor=current_user
        )
    except (NotFoundError, BusinessRuleViolation) as exc:
        _raise_service_error(exc)
