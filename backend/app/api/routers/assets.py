from __future__ import annotations

import enum
import os
import mimetypes
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.models.asset import Asset, AssetOwnerType, AssetKind, AssetSource, AssetReviewState
from app.models.user import User, UserRole
from app.schemas.asset import AssetOut, AssetCreateWeb, AssetUpdate
from app.services.storage import save_upload_validated, cache_download, ensure_thumbnail
from app.services.audit import record_audit_log

router = APIRouter()


class LicenseFilter(str, enum.Enum):
    any = "any"
    licensed = "licensed"
    missing = "missing"


def _expected_kind(kind: AssetKind) -> str:
    if kind == AssetKind.image:
        return "image"
    if kind == AssetKind.pdf:
        return "pdf"
    raise HTTPException(status_code=400, detail="Only image and pdf uploads are allowed")


def _upload_purpose_allowed(owner_type: AssetOwnerType, kind: AssetKind) -> bool:
    if kind == AssetKind.pdf and owner_type not in {AssetOwnerType.product, AssetOwnerType.deal, AssetOwnerType.content}:
        return False
    if kind == AssetKind.image:
        return True
    return False


def _enforce_asset_access(current_user: User, asset: Asset) -> None:
    privileged = current_user.role in {UserRole.admin, UserRole.editor}
    if asset.review_state != AssetReviewState.approved and not privileged:
        raise HTTPException(status_code=403, detail="Asset not approved")


def _delivery_headers(asset: Asset, path: str) -> tuple[str | None, str, dict[str, str]]:
    media_type = asset.kind.value
    if asset.kind == AssetKind.image:
        guessed, _ = mimetypes.guess_type(path)
        media_type = guessed or "application/octet-stream"
        disposition = "inline"
    elif asset.kind == AssetKind.pdf:
        media_type = "application/pdf"
        disposition = "inline"
    else:
        media_type = "application/octet-stream"
        disposition = "attachment"

    filename = os.path.basename(path)
    cache_control = "private, max-age=300" if asset.review_state == AssetReviewState.approved else "no-store"
    headers = {
        "Content-Disposition": f'{disposition}; filename="{filename}"',
        "Cache-Control": cache_control,
    }
    return media_type, filename, headers


@router.get("", response_model=list[AssetOut])
def list_assets(
    owner_type: AssetOwnerType,
    owner_id: uuid.UUID,
    include_pending: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AssetOut]:
    q = db.query(Asset).filter(Asset.owner_type == owner_type, Asset.owner_id == owner_id)
    if current_user.role == UserRole.viewer:
        q = q.filter(Asset.review_state == AssetReviewState.approved)
    elif not include_pending:
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
    current_user: User = Depends(get_current_user),
) -> list[AssetOut]:
    q = db.query(Asset)
    if owner_type:
        q = q.filter(Asset.owner_type == owner_type)
    if kind:
        q = q.filter(Asset.kind == kind)
    if primary_only:
        q = q.filter(Asset.is_primary.is_(True))
    if current_user.role == UserRole.viewer:
        q = q.filter(Asset.review_state == AssetReviewState.approved)
    elif approved_only:
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
    if not _upload_purpose_allowed(owner_type, kind):
        raise HTTPException(status_code=400, detail="This file type is not allowed for the selected upload purpose")

    data = await file.read()
    owner_folder = f"{owner_type.value}/{owner_id}"
    try:
        stored = save_upload_validated(
            owner_folder=owner_folder,
            filename=file.filename or "upload.bin",
            data=data,
            expected_kind=_expected_kind(kind),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    asset = Asset(
        owner_type=owner_type,
        owner_id=owner_id,
        kind=kind,
        source=AssetSource.upload,
        local_path=stored.local_path,
        title=title or stored.safe_filename,
        license_type=None,
        attribution=None,
        source_name="upload",
        width=stored.width,
        height=stored.height,
        size_bytes=stored.size_bytes,
        hash=stored.sha256,
        perceptual_hash=stored.perceptual_hash,
        review_state=AssetReviewState.pending_review,
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
    data = payload.model_dump()
    data["review_state"] = AssetReviewState.needs_review
    asset = Asset(**data)
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
def get_asset_file(asset_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FileResponse:
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    _enforce_asset_access(current_user, asset)

    path = asset.local_path
    if not path and asset.url:
        expected_kind = "image" if asset.kind == AssetKind.image else "pdf" if asset.kind == AssetKind.pdf else None
        if expected_kind is None:
            raise HTTPException(status_code=400, detail="Unsupported remote asset kind")
        try:
            stored = cache_download(asset.url, subdir="web", db=db, expected_kind=expected_kind)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        asset.local_path = stored.local_path
        asset.hash = asset.hash or stored.sha256
        asset.size_bytes = stored.size_bytes
        asset.width = stored.width
        asset.height = stored.height
        db.commit()
        path = stored.local_path

    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not available")
    size = asset.size_bytes or os.path.getsize(path)
    if size > settings.ASSET_MAX_DELIVERY_BYTES:
        raise HTTPException(status_code=413, detail="Asset exceeds delivery size limit")

    media_type, filename, headers = _delivery_headers(asset, path)
    return FileResponse(path, filename=filename, media_type=media_type, headers=headers)


@router.get("/{asset_id}/thumb")
def get_asset_thumb(asset_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FileResponse:
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    _enforce_asset_access(current_user, asset)
    if asset.kind != AssetKind.image:
        raise HTTPException(status_code=400, detail="Thumbnails are only available for images")

    path = asset.local_path
    if not path and asset.url:
        try:
            stored = cache_download(asset.url, subdir="web", db=db, expected_kind="image")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        asset.local_path = stored.local_path
        asset.hash = asset.hash or stored.sha256
        asset.size_bytes = stored.size_bytes
        asset.width = stored.width
        asset.height = stored.height
        db.commit()
        path = stored.local_path

    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not available")

    try:
        thumb = ensure_thumbnail(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    headers = {
        "Content-Disposition": f'inline; filename="{os.path.basename(thumb)}"',
        "Cache-Control": "private, max-age=300",
    }
    thumb_mime, _ = mimetypes.guess_type(thumb)
    return FileResponse(thumb, filename=os.path.basename(thumb), media_type=thumb_mime or "application/octet-stream", headers=headers)


@router.get("/review-queue", response_model=list[AssetOut])
def review_queue(
    owner_type: AssetOwnerType | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
) -> list[AssetOut]:
    q = db.query(Asset).filter(
        Asset.review_state.in_([
            AssetReviewState.quarantine,
            AssetReviewState.pending_review,
            AssetReviewState.needs_review,
            AssetReviewState.pending,
        ])
    )
    if owner_type:
        q = q.filter(Asset.owner_type == owner_type)
    return q.order_by(Asset.created_at.asc()).limit(max(1, min(limit, 500))).all()
