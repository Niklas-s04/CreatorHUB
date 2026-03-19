from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db, require_role
from app.api.querying import apply_sorting, pagination_params, to_page
from app.models.product import (
    Product,
    ProductStatus,
    ProductTransaction,
    ProductValueHistory,
)
from app.models.user import User, UserRole
from app.schemas.common import Page, SortOrder
from app.schemas.product import (
    InventoryCsvImportRequest,
    InventoryCsvImportResult,
    ProductCreate,
    ProductOut,
    ProductStatusChange,
    ProductTransactionCreate,
    ProductTransactionOut,
    ProductUpdate,
    ProductValueHistoryCreate,
    ProductValueHistoryOut,
)
from app.services.audit import record_audit_log
from app.services.auto_archive import apply_auto_archive_rules
from app.services.domain_events import emit_domain_event
from app.services.domain_rules import product_status_side_effect, validate_product_status_change
from app.services.errors import BusinessRuleViolation
from app.services.exports import (
    export_products_csv,
    export_transactions_csv,
    export_value_history_csv,
)
from app.services.inventory_import import CsvImportConfig, import_products_from_csv

router = APIRouter()


def _normalize_years(years: list[int] | None) -> list[int]:
    if not years:
        return []
    normalized = set()
    for year in years:
        if year is None:
            continue
        y = int(year)
        if 1900 <= y <= 9999:
            normalized.add(y)
    cleaned = sorted(normalized)
    return cleaned


def _apply_year_filter_date(qry, column, years: list[int]):
    if not years:
        return qry
    clauses = []
    for year in years:
        start = date(year, 1, 1)
        end = date(year + 1, 1, 1)
        clauses.append(and_(column >= start, column < end))
    if not clauses:
        return qry
    return qry.filter(or_(*clauses))


def _apply_year_filter_datetime(qry, column, years: list[int]):
    if not years:
        return qry
    clauses = []
    for year in years:
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        clauses.append(and_(column >= start, column < end))
    if not clauses:
        return qry
    return qry.filter(or_(*clauses))


def _product_in_years(product: Product, years_set: set[int]) -> bool:
    if not years_set:
        return True
    purchase_date = getattr(product, "purchase_date", None)
    if purchase_date and purchase_date.year in years_set:
        return True
    created_at = getattr(product, "created_at", None)
    if created_at and created_at.year in years_set:
        return True
    return False


class CSVExportKind(str, Enum):
    products = "products"
    transactions = "transactions"
    value_history = "value_history"


@router.get("", response_model=Page[ProductOut])
def list_products(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    q: str | None = None,
    status: ProductStatus | None = None,
    category: str | None = None,
    condition: str | None = None,
    storage_location: str | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    paging: tuple[int, int, str, SortOrder] = Depends(pagination_params),
) -> Page[ProductOut]:
    limit, offset, sort_by, sort_order = paging
    qry = db.query(Product)
    if q:
        like = f"%{q}%"
        qry = qry.filter(
            or_(
                Product.title.ilike(like),
                Product.brand.ilike(like),
                Product.model.ilike(like),
                Product.category.ilike(like),
            )
        )
    if status:
        qry = qry.filter(Product.status == status)
    if category:
        qry = qry.filter(Product.category == category)
    if condition:
        qry = qry.filter(Product.condition == condition)
    if storage_location:
        qry = qry.filter(Product.storage_location == storage_location)
    if min_value is not None:
        qry = qry.filter(Product.current_value >= min_value)
    if max_value is not None:
        qry = qry.filter(Product.current_value <= max_value)

    total = qry.order_by(None).count()
    qry, selected_sort, selected_order = apply_sorting(
        qry,
        model=Product,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields={
            "created_at",
            "updated_at",
            "title",
            "status",
            "current_value",
            "purchase_date",
            "status_changed_at",
        },
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


@router.post("", response_model=ProductOut)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> ProductOut:
    p = Product(**payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    # Optionalen Startwert in die Wert-Historie übernehmen.
    if p.current_value is not None:
        vh = ProductValueHistory(
            product_id=p.id,
            date=p.created_at.date(),
            value=float(p.current_value),
            currency=p.currency,
        )
        db.add(vh)
        db.commit()
    return p


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> ProductOut:
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return p


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> ProductOut:
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    updates = payload.model_dump(exclude_unset=True)
    maybe_status = updates.pop("status", None)
    if maybe_status and maybe_status != p.status:
        try:
            validate_product_status_change(
                current_status=p.status,
                target_status=maybe_status,
                amount=None,
            )
        except BusinessRuleViolation as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        before_status = p.status
        p.status = maybe_status
        p.status_changed_at = datetime.now(timezone.utc)
        record_audit_log(
            db,
            actor=current_user,
            action="product.status_update",
            entity_type="product",
            entity_id=str(p.id),
            description=f"Status {before_status.value} -> {maybe_status.value}",
            before={"status": before_status.value},
            after={"status": maybe_status.value},
        )
        emit_domain_event(
            db,
            actor=current_user,
            event_name="product.status.changed",
            entity_type="product",
            entity_id=str(p.id),
            payload={
                "from": before_status.value,
                "to": maybe_status.value,
                "source": "products.patch",
            },
            description=f"Product status changed: {before_status.value} -> {maybe_status.value}",
        )
    for k, v in updates.items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{product_id}")
def delete_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
) -> dict:
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(p)
    db.commit()
    return {"deleted": True}


@router.get("/{product_id}/transactions", response_model=list[ProductTransactionOut])
def list_transactions(
    product_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[ProductTransactionOut]:
    return (
        db.query(ProductTransaction)
        .filter(ProductTransaction.product_id == product_id)
        .order_by(ProductTransaction.date.desc())
        .all()
    )


@router.post("/{product_id}/transactions", response_model=ProductTransactionOut)
def create_transaction(
    product_id: uuid.UUID,
    payload: ProductTransactionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> ProductTransactionOut:
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    t = ProductTransaction(product_id=product_id, **payload.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.get("/{product_id}/value_history", response_model=list[ProductValueHistoryOut])
def list_value_history(
    product_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[ProductValueHistoryOut]:
    return (
        db.query(ProductValueHistory)
        .filter(ProductValueHistory.product_id == product_id)
        .order_by(ProductValueHistory.date.desc())
        .all()
    )


@router.post("/{product_id}/value_history", response_model=ProductValueHistoryOut)
def create_value_history(
    product_id: uuid.UUID,
    payload: ProductValueHistoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> ProductValueHistoryOut:
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    vh = ProductValueHistory(product_id=product_id, **payload.model_dump())
    db.add(vh)
    # Produktwert mit dem neuesten manuellen Eintrag synchron halten.
    p.current_value = payload.value
    p.currency = payload.currency
    db.commit()
    db.refresh(vh)
    return vh


@router.post("/{product_id}/status", response_model=ProductOut)
def change_status(
    product_id: uuid.UUID,
    payload: ProductStatusChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> ProductOut:
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        validate_product_status_change(
            current_status=p.status,
            target_status=payload.status,
            amount=payload.amount,
        )
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tx_type, _ = product_status_side_effect(payload.status)

    if tx_type:
        tx = ProductTransaction(
            product_id=p.id,
            type=tx_type,
            date=payload.date,
            amount=payload.amount,
            currency=payload.currency,
            counterparty=payload.counterparty,
            notes=payload.notes,
        )
        db.add(tx)
        emit_domain_event(
            db,
            actor=current_user,
            event_name="product.transaction.created",
            entity_type="product",
            entity_id=str(p.id),
            payload={
                "transaction_type": tx_type.value,
                "date": payload.date.isoformat(),
                "amount": payload.amount,
                "currency": payload.currency,
            },
            description=f"Transaction side effect for status change: {tx_type.value}",
        )

    if p.status != payload.status:
        before_status = p.status
        p.status = payload.status
        p.status_changed_at = datetime.now(timezone.utc)
        record_audit_log(
            db,
            actor=current_user,
            action="product.status_change",
            entity_type="product",
            entity_id=str(p.id),
            description=f"Status {before_status.value} -> {payload.status.value}",
            before={"status": before_status.value},
            after={"status": payload.status.value},
            metadata={
                "date": payload.date.isoformat(),
                "amount": payload.amount,
                "currency": payload.currency,
            },
        )
        emit_domain_event(
            db,
            actor=current_user,
            event_name="product.status.changed",
            entity_type="product",
            entity_id=str(p.id),
            payload={
                "from": before_status.value,
                "to": payload.status.value,
                "date": payload.date.isoformat(),
            },
            description=f"Product status changed: {before_status.value} -> {payload.status.value}",
        )
    db.commit()
    db.refresh(p)
    return p


@router.post("/import/csv", response_model=InventoryCsvImportResult)
def import_products_csv(
    payload: InventoryCsvImportRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> InventoryCsvImportResult:
    config = CsvImportConfig(
        csv_text=payload.csv_text,
        delimiter=payload.delimiter,
        quotechar=payload.quotechar,
        column_map=payload.column_map,
        defaults=payload.defaults,
        dry_run=payload.dry_run,
    )
    try:
        result = import_products_from_csv(db, config=config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InventoryCsvImportResult(**result)


@router.post("/auto-archive/run")
def trigger_auto_archive(
    db: Session = Depends(get_db), _: User = Depends(require_role(UserRole.admin))
) -> dict:
    summary = apply_auto_archive_rules(db)
    return summary


@router.get("/export/csv")
def export_csv(
    dataset: CSVExportKind = Query(default=CSVExportKind.products),
    years: list[int] | None = Query(
        default=None, description="Optional years filter (?years=2023&years=2024)"
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> FileResponse:
    year_list = _normalize_years(years)
    year_set = set(year_list)
    if dataset == CSVExportKind.products:
        qry = db.query(Product).order_by(Product.created_at.desc())
        items = qry.all()
        if year_set:
            items = [p for p in items if _product_in_years(p, year_set)]
        path = export_products_csv(items)
    elif dataset == CSVExportKind.transactions:
        qry = (
            db.query(ProductTransaction)
            .options(joinedload(ProductTransaction.product))
            .order_by(ProductTransaction.date.desc(), ProductTransaction.created_at.desc())
        )
        if year_list:
            qry = _apply_year_filter_date(qry, ProductTransaction.date, year_list)
        items = qry.all()
        path = export_transactions_csv(items)
    else:
        qry = (
            db.query(ProductValueHistory)
            .options(joinedload(ProductValueHistory.product))
            .order_by(ProductValueHistory.date.desc(), ProductValueHistory.created_at.desc())
        )
        if year_list:
            qry = _apply_year_filter_date(qry, ProductValueHistory.date, year_list)
        items = qry.all()
        path = export_value_history_csv(items)

    return FileResponse(path, filename=path.split("/")[-1], media_type="text/csv")
