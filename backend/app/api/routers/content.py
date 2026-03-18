from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.content import ContentItem, ContentTask
from app.models.user import User, UserRole
from app.schemas.content import (
    ContentItemCreate,
    ContentItemOut,
    ContentItemUpdate,
    ContentTaskCreate,
    ContentTaskOut,
    ContentTaskUpdate,
)
from app.services.content_task_defaults import ensure_default_tasks_for_item

router = APIRouter()


@router.get("/items", response_model=list[ContentItemOut])
def list_items(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    product_id: uuid.UUID | None = None,
) -> list[ContentItemOut]:
    q = db.query(ContentItem)
    if product_id:
        q = q.filter(ContentItem.product_id == product_id)
    return q.order_by(ContentItem.updated_at.desc()).all()


@router.post("/items", response_model=ContentItemOut)
def create_item(
    payload: ContentItemCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> ContentItemOut:
    item = ContentItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    ensure_default_tasks_for_item(db, item)
    return item


@router.patch("/items/{item_id}", response_model=ContentItemOut)
def update_item(
    item_id: uuid.UUID,
    payload: ContentItemUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> ContentItemOut:
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{item_id}")
def delete_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> dict:
    item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    db.delete(item)
    db.commit()
    return {"deleted": True}


@router.get("/tasks", response_model=list[ContentTaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    content_item_id: uuid.UUID | None = None,
) -> list[ContentTaskOut]:
    q = db.query(ContentTask)
    if content_item_id:
        q = q.filter(ContentTask.content_item_id == content_item_id)
    return q.order_by(ContentTask.updated_at.desc()).all()


@router.post("/tasks", response_model=ContentTaskOut)
def create_task(
    payload: ContentTaskCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> ContentTaskOut:
    task = ContentTask(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/tasks/{task_id}", response_model=ContentTaskOut)
def update_task(
    task_id: uuid.UUID,
    payload: ContentTaskUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> ContentTaskOut:
    task = db.query(ContentTask).filter(ContentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Content task not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> dict:
    task = db.query(ContentTask).filter(ContentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Content task not found")
    db.delete(task)
    db.commit()
    return {"deleted": True}
