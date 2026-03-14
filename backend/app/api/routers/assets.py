from __future__ import annotations

import enum
import os
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.models.asset import Asset, AssetOwnerType, AssetKind, AssetSource, AssetReviewState
from app.models.user import User, UserRole
from app.schemas.asset import AssetOut, AssetCreateWeb, AssetUpdate
from app.services.storage import save_upload, cache_download, ensure_thumbnail
from app.services.audit import record_audit_log

router = APIRouter()


class LicenseFilter(str, enum.Enum):
    any = "any"
    licensed = "licensed"
    missing = "missing"


@router.get("", response_model=list[AssetOut])
def list_assets(
    owner_type: AssetOwnerType,
    owner_id: uuid.UUID,
    include_pending: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AssetOut]:
    q = db.query(Asset).filter(Asset.owner_type == owner_type, Asset.owner_id == owner_id)
    if not include_pending:
        q = q.filter(Asset.review_state == AssetReviewState.approved)
    return q.order_by(Asset.created_at.desc()).all()


@router.get("/library", response_model=list[AssetOut])
def list_library_assets(
    search: str | None = None,
    owner_type: AssetOwnerType | None = None,
    kind: AssetKind | None = None,
    primary_only: bool = False,
    approved_only: bool = True,
    license_filter: LicenseFilter = LicenseFilter.any,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AssetOut]:
    q = db.query(Asset)
    if owner_type:
        q = q.filter(Asset.owner_type == owner_type)
    if kind:
        q = q.filter(Asset.kind == kind)
    if primary_only:
        q = q.filter(Asset.is_primary.is_(True))
    if approved_only:
        q = q.filter(Asset.review_state == AssetReviewState.approved)
    if search:
        pattern = f"%{search.lower()}%"
        q = q.filter(
            or_(
                Asset.title.ilike(pattern),
                Asset.source_name.ilike(pattern),
                Asset.source_url.ilike(pattern),
            )
        )
    if license_filter == LicenseFilter.licensed:
        q = q.filter(or_(Asset.license_type.isnot(None), Asset.license_url.isnot(None)))
    elif license_filter == LicenseFilter.missing:
        q = q.filter(Asset.license_type.is_(None), Asset.license_url.is_(None))

    safe_limit = max(1, min(limit, 200))
    return q.order_by(Asset.created_at.desc()).limit(safe_limit).all()


@router.post("/upload", response_model=AssetOut)
async def upload_asset(
    owner_type: AssetOwnerType = Form(...),
    owner_id: uuid.UUID = Form(...),
    kind: AssetKind = Form(AssetKind.image),
    title: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> AssetOut:
    data = await file.read()
    owner_folder = f"{owner_type.value}/{owner_id}"
    stored = save_upload(owner_folder=owner_folder, filename=file.filename or "upload.bin", data=data)

    asset = Asset(
        owner_type=owner_type,
        owner_id=owner_id,
        kind=kind,
        source=AssetSource.upload,
        local_path=stored.local_path,
        title=title or file.filename,
        license_type=None,
        attribution=None,
        width=stored.width,
        height=stored.height,
        size_bytes=stored.size_bytes,
        hash=stored.sha256,
        perceptual_hash=stored.perceptual_hash,
        review_state=AssetReviewState.approved,
        is_primary=False,
    )
    # Duplikate per Hash vermeiden und vorhandenes Asset wiederverwenden.
    existing = db.query(Asset).filter(Asset.hash == stored.sha256).first()
    if existing:
        # Keine doppelte Datenbankzeile anlegen.
        return existing

    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.post("/web", response_model=AssetOut)
def create_web_asset(payload: AssetCreateWeb, db: Session = Depends(get_db), _: User = Depends(require_role(UserRole.admin, UserRole.editor))) -> AssetOut:
    existing = None
    if payload.hash:
        existing = db.query(Asset).filter(Asset.hash == payload.hash).first()
    if existing:
        return existing
    asset = Asset(**payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.patch("/{asset_id}", response_model=AssetOut)
def update_asset(
    asset_id: uuid.UUID,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> AssetOut:
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    data = payload.model_dump(exclude_unset=True)
    original_review_state = asset.review_state

    # Primär-Flag nur bei Produktbildern exklusiv setzen.
    if data.get("is_primary") is True and asset.owner_type == AssetOwnerType.product and asset.kind == AssetKind.image:
        db.query(Asset).filter(
            Asset.owner_type == asset.owner_type,
            Asset.owner_id == asset.owner_id,
            Asset.kind == AssetKind.image,
        ).update({Asset.is_primary: False})
        asset.is_primary = True
        data.pop("is_primary", None)

    for k, v in data.items():
        setattr(asset, k, v)

    if "review_state" in data and data.get("review_state") and original_review_state != asset.review_state:
        record_audit_log(
            db,
            actor=current_user,
            action="asset.review_state_change",
            entity_type="asset",
            entity_id=str(asset.id),
            description=f"Review state {original_review_state.value} -> {asset.review_state.value}",
            before={"review_state": original_review_state.value},
            after={"review_state": asset.review_state.value},
            metadata={
                "owner_type": asset.owner_type.value,
                "owner_id": str(asset.owner_id),
            },
        )
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/{asset_id}/file")
def get_asset_file(asset_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> FileResponse:
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    path = asset.local_path
    if not path and asset.url:
        stored = cache_download(asset.url, subdir="web")
        asset.local_path = stored.local_path
        asset.hash = asset.hash or stored.sha256
        asset.size_bytes = stored.size_bytes
        asset.width = stored.width
        asset.height = stored.height
        db.commit()
        path = stored.local_path

    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not available")
    return FileResponse(path, filename=os.path.basename(path))


@router.get("/{asset_id}/thumb")
def get_asset_thumb(asset_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> FileResponse:
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    path = asset.local_path
    if not path and asset.url:
        stored = cache_download(asset.url, subdir="web")
        asset.local_path = stored.local_path
        asset.hash = asset.hash or stored.sha256
        asset.size_bytes = stored.size_bytes
        asset.width = stored.width
        asset.height = stored.height
        db.commit()
        path = stored.local_path

    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not available")

    thumb = ensure_thumbnail(path)
    return FileResponse(thumb, filename=os.path.basename(thumb))
