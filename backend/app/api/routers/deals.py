from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.api.querying import apply_sorting, pagination_params, to_page
from app.models.deal import DealDraft, DealDraftStatus
from app.models.user import User, UserRole
from app.schemas.common import Page, SortOrder
from app.schemas.deal import DealDraftIntakeRequest, DealDraftOut, DealDraftUpdate
from app.services import deal_service
from app.services.errors import NotFoundError

router = APIRouter()


@router.get("", response_model=Page[DealDraftOut])
def list_deal_drafts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    status: DealDraftStatus | None = None,
    thread_id: uuid.UUID | None = None,
    paging: tuple[int, int, str, SortOrder] = Depends(pagination_params),
) -> Page[DealDraftOut]:
    limit, offset, sort_by, sort_order = paging
    qry = db.query(DealDraft)
    if status:
        qry = qry.filter(DealDraft.status == status)
    if thread_id:
        qry = qry.filter(DealDraft.thread_id == thread_id)

    total = qry.order_by(None).count()
    qry, selected_sort, selected_order = apply_sorting(
        qry,
        model=DealDraft,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields={"created_at", "updated_at", "status"},
        fallback="created_at",
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


@router.get("/by-thread/{thread_id}", response_model=DealDraftOut)
def get_deal_by_thread(
    thread_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DealDraftOut:
    try:
        return deal_service.get_deal_by_thread(db, thread_id=thread_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/intake", response_model=DealDraftOut)
def create_or_update_deal_from_email(
    payload: DealDraftIntakeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> DealDraftOut:
    try:
        return deal_service.create_or_update_from_email(
            db,
            payload=payload,
            actor=current_user,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{deal_id}", response_model=DealDraftOut)
def update_deal_draft(
    deal_id: uuid.UUID,
    payload: DealDraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> DealDraftOut:
    try:
        return deal_service.update_deal_draft(
            db,
            deal_id=deal_id,
            payload=payload,
            actor=current_user,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
