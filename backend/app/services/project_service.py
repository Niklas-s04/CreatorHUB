from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.content import ContentItem
from app.models.product import Product, ProductStatus, ProductValueHistory
from app.models.project import PreviewStatus, Project, ProjectCategory
from app.models.user import User
from app.schemas.content import ContentItemCreate
from app.schemas.product import ProductCreate
from app.schemas.project import (
    ProjectCategoryCreate,
    ProjectCategoryUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from app.services import content_service
from app.services.audit import record_audit_log
from app.services.errors import BusinessRuleViolation, NotFoundError
from app.services.transactions import transaction_boundary
from app.services.workflow import validate_workflow_status_change


def _normalized_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _get_project(db: Session, project_id: uuid.UUID) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundError("Project not found")
    return project


def get_project(db: Session, project_id: uuid.UUID) -> Project:
    return enrich_project(_get_project(db, project_id))


def _get_category(db: Session, category_id: uuid.UUID) -> ProjectCategory:
    category = db.query(ProjectCategory).filter(ProjectCategory.id == category_id).first()
    if not category:
        raise BusinessRuleViolation("Project category not found")
    return category


def _ensure_unique_category_name(
    db: Session, *, name: str, exclude_id: uuid.UUID | None = None
) -> None:
    query = db.query(ProjectCategory.id).filter(
        func.lower(ProjectCategory.name) == name.strip().lower()
    )
    if exclude_id:
        query = query.filter(ProjectCategory.id != exclude_id)
    if query.first():
        raise BusinessRuleViolation("A project category with this name already exists")


def _validate_dates(start_date: date | None, due_date: date | None) -> None:
    if start_date and due_date and due_date < start_date:
        raise BusinessRuleViolation("Due date must not be before start date")


def _sync_preview_state(project: Project) -> None:
    if not project.preview_required:
        project.preview_status = PreviewStatus.not_required
        project.preview_due_date = None
    elif project.preview_status == PreviewStatus.not_required:
        project.preview_status = PreviewStatus.pending


def enrich_project(project: Project) -> Project:
    project.content_count = len(project.content_items)
    project.product_count = len(project.products)
    today = date.today()
    project.overdue = bool(
        project.due_date
        and project.due_date < today
        and project.status.value not in {"completed", "archived"}
    )
    project.preview_attention_required = bool(
        project.preview_required
        and project.preview_status
        in {
            PreviewStatus.pending,
            PreviewStatus.requested,
            PreviewStatus.changes_requested,
        }
    )
    return project


def list_categories(db: Session, *, include_inactive: bool = False) -> list[ProjectCategory]:
    query = db.query(ProjectCategory)
    if not include_inactive:
        query = query.filter(ProjectCategory.is_active.is_(True))
    return query.order_by(ProjectCategory.name.asc()).all()


def create_category(db: Session, *, payload: ProjectCategoryCreate, actor: User) -> ProjectCategory:
    name = payload.name.strip()
    _ensure_unique_category_name(db, name=name)
    category = ProjectCategory(
        **payload.model_dump(exclude={"name", "description"}),
        name=name,
        description=_normalized_text(payload.description),
    )
    with transaction_boundary(db):
        db.add(category)
        db.flush()
        record_audit_log(
            db,
            actor=actor,
            action="project.category.create",
            entity_type="project_category",
            entity_id=str(category.id),
            after={"name": category.name, "color": category.color},
        )
    db.refresh(category)
    return category


def update_category(
    db: Session,
    *,
    category_id: uuid.UUID,
    payload: ProjectCategoryUpdate,
    actor: User,
) -> ProjectCategory:
    category = db.query(ProjectCategory).filter(ProjectCategory.id == category_id).first()
    if not category:
        raise NotFoundError("Project category not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        updates["name"] = updates["name"].strip()
        _ensure_unique_category_name(db, name=updates["name"], exclude_id=category.id)
    if "description" in updates:
        updates["description"] = _normalized_text(updates["description"])
    before = {key: getattr(category, key) for key in updates}
    with transaction_boundary(db):
        for key, value in updates.items():
            setattr(category, key, value)
        record_audit_log(
            db,
            actor=actor,
            action="project.category.update",
            entity_type="project_category",
            entity_id=str(category.id),
            before=before,
            after=updates,
        )
    db.refresh(category)
    return category


def delete_category(db: Session, *, category_id: uuid.UUID, actor: User) -> None:
    category = db.query(ProjectCategory).filter(ProjectCategory.id == category_id).first()
    if not category:
        raise NotFoundError("Project category not found")
    with transaction_boundary(db):
        record_audit_log(
            db,
            actor=actor,
            action="project.category.delete",
            entity_type="project_category",
            entity_id=str(category.id),
            before={"name": category.name},
        )
        db.delete(category)


def _resolve_content_items(db: Session, ids: list[uuid.UUID]) -> list[ContentItem]:
    unique_ids = list(dict.fromkeys(ids))
    if not unique_ids:
        return []
    items = db.query(ContentItem).filter(ContentItem.id.in_(unique_ids)).all()
    if len(items) != len(unique_ids):
        raise BusinessRuleViolation("One or more linked content items were not found")
    return items


def _resolve_products(db: Session, ids: list[uuid.UUID]) -> list[Product]:
    unique_ids = list(dict.fromkeys(ids))
    if not unique_ids:
        return []
    products = db.query(Product).filter(Product.id.in_(unique_ids)).all()
    if len(products) != len(unique_ids):
        raise BusinessRuleViolation("One or more linked products were not found")
    if any(product.status == ProductStatus.archived for product in products):
        raise BusinessRuleViolation("Archived products cannot be linked to projects")
    return products


def create_project(db: Session, *, payload: ProjectCreate, actor: User) -> Project:
    if payload.category_id:
        _get_category(db, payload.category_id)
    content_items = _resolve_content_items(db, payload.content_item_ids)
    products = _resolve_products(db, payload.product_ids)
    fields = payload.model_dump(exclude={"content_item_ids", "product_ids"})
    fields["title"] = payload.title.strip()
    for key in ("owner_name", "goal", "brief_md", "requirements_md", "notes_md", "preview_notes"):
        fields[key] = _normalized_text(fields.get(key))
    project = Project(**fields)
    project.content_items = content_items
    project.products = products
    _sync_preview_state(project)
    with transaction_boundary(db):
        db.add(project)
        db.flush()
        record_audit_log(
            db,
            actor=actor,
            action="project.create",
            entity_type="project",
            entity_id=str(project.id),
            after={
                "title": project.title,
                "status": project.status.value,
                "category_id": str(project.category_id) if project.category_id else None,
                "content_count": len(content_items),
                "product_count": len(products),
            },
        )
    db.refresh(project)
    return enrich_project(project)


def update_project(
    db: Session, *, project_id: uuid.UUID, payload: ProjectUpdate, actor: User
) -> Project:
    project = _get_project(db, project_id)
    updates = payload.model_dump(exclude_unset=True)
    if "category_id" in updates and updates["category_id"]:
        _get_category(db, updates["category_id"])
    if "title" in updates:
        updates["title"] = updates["title"].strip()
    for key in ("owner_name", "goal", "brief_md", "requirements_md", "notes_md", "preview_notes"):
        if key in updates:
            updates[key] = _normalized_text(updates[key])
    start_date = updates.get("start_date", project.start_date)
    due_date = updates.get("due_date", project.due_date)
    _validate_dates(start_date, due_date)
    before = {
        key: getattr(project, key).value
        if hasattr(getattr(project, key), "value")
        else getattr(project, key)
        for key in updates
    }
    with transaction_boundary(db):
        for key, value in updates.items():
            setattr(project, key, value)
        _sync_preview_state(project)
        record_audit_log(
            db,
            actor=actor,
            action="project.update",
            entity_type="project",
            entity_id=str(project.id),
            before=before,
            after={
                key: getattr(project, key).value
                if hasattr(getattr(project, key), "value")
                else getattr(project, key)
                for key in updates
            },
        )
    db.refresh(project)
    return enrich_project(project)


def delete_project(db: Session, *, project_id: uuid.UUID, actor: User) -> None:
    project = _get_project(db, project_id)
    with transaction_boundary(db):
        record_audit_log(
            db,
            actor=actor,
            action="project.delete",
            entity_type="project",
            entity_id=str(project.id),
            before={"title": project.title},
        )
        db.delete(project)


def link_content(
    db: Session, *, project_id: uuid.UUID, content_item_id: uuid.UUID, actor: User
) -> Project:
    project = _get_project(db, project_id)
    content_item = db.query(ContentItem).filter(ContentItem.id == content_item_id).first()
    if not content_item:
        raise NotFoundError("Content item not found")
    if content_item not in project.content_items:
        with transaction_boundary(db):
            project.content_items.append(content_item)
            record_audit_log(
                db,
                actor=actor,
                action="project.content.link",
                entity_type="project",
                entity_id=str(project.id),
                metadata={"content_item_id": str(content_item.id)},
            )
    return enrich_project(project)


def unlink_content(
    db: Session, *, project_id: uuid.UUID, content_item_id: uuid.UUID, actor: User
) -> Project:
    project = _get_project(db, project_id)
    content_item = next(
        (item for item in project.content_items if item.id == content_item_id), None
    )
    if not content_item:
        raise NotFoundError("Content item is not linked to this project")
    with transaction_boundary(db):
        project.content_items.remove(content_item)
        record_audit_log(
            db,
            actor=actor,
            action="project.content.unlink",
            entity_type="project",
            entity_id=str(project.id),
            metadata={"content_item_id": str(content_item.id)},
        )
    return enrich_project(project)


def link_product(
    db: Session, *, project_id: uuid.UUID, product_id: uuid.UUID, actor: User
) -> Project:
    project = _get_project(db, project_id)
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise NotFoundError("Product not found")
    if product.status == ProductStatus.archived:
        raise BusinessRuleViolation("Archived products cannot be linked to projects")
    if product not in project.products:
        with transaction_boundary(db):
            project.products.append(product)
            record_audit_log(
                db,
                actor=actor,
                action="project.product.link",
                entity_type="project",
                entity_id=str(project.id),
                metadata={"product_id": str(product.id)},
            )
    return enrich_project(project)


def unlink_product(
    db: Session, *, project_id: uuid.UUID, product_id: uuid.UUID, actor: User
) -> Project:
    project = _get_project(db, project_id)
    product = next((item for item in project.products if item.id == product_id), None)
    if not product:
        raise NotFoundError("Product is not linked to this project")
    with transaction_boundary(db):
        project.products.remove(product)
        record_audit_log(
            db,
            actor=actor,
            action="project.product.unlink",
            entity_type="project",
            entity_id=str(project.id),
            metadata={"product_id": str(product.id)},
        )
    return enrich_project(project)


def create_linked_content(
    db: Session, *, project_id: uuid.UUID, payload: ContentItemCreate, actor: User
) -> Project:
    project = _get_project(db, project_id)
    content_item = content_service.create_item(db, payload=payload, actor=actor)
    return link_content(db, project_id=project.id, content_item_id=content_item.id, actor=actor)


def create_linked_product(
    db: Session, *, project_id: uuid.UUID, payload: ProductCreate, actor: User
) -> Project:
    project = _get_project(db, project_id)
    product = Product(**payload.model_dump())
    validate_workflow_status_change(
        current_status=product.workflow_status,
        target_status=product.workflow_status,
        review_reason=product.review_reason,
    )
    with transaction_boundary(db):
        db.add(product)
        db.flush()
        if product.current_value is not None:
            db.add(
                ProductValueHistory(
                    product_id=product.id,
                    date=date.today(),
                    value=float(product.current_value),
                    currency=product.currency,
                )
            )
        project.products.append(product)
        record_audit_log(
            db,
            actor=actor,
            action="project.product.create_linked",
            entity_type="project",
            entity_id=str(project.id),
            metadata={"product_id": str(product.id), "title": product.title},
        )
    return enrich_project(project)
