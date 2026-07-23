from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.models.asset import Asset, AssetKind, AssetOwnerType, AssetReviewState, AssetSource
from app.models.content import (
    ContentItem,
    ContentPlatform,
    ContentStatus,
    ContentType,
    EditorialStatus,
)
from app.models.user import UserRole
from app.models.workflow import WorkflowStatus
from tests.factories import create_user


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color=(12, 34, 56)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_upload_rejects_invalid_upload_purpose(client, app, db_session: Session) -> None:
    admin = create_user(db_session, username="assets_admin", role=UserRole.admin)
    app.dependency_overrides[deps.get_current_user] = lambda: admin

    response = client.post(
        "/api/assets/upload",
        data={
            "owner_type": "email",
            "owner_id": str(uuid.uuid4()),
            "kind": "pdf",
            "title": "invalid-purpose",
        },
        files={"file": ("proof.pdf", b"%PDF-1.7\n%%EOF", "application/pdf")},
    )

    assert response.status_code == 400
    assert "selected upload purpose" in response.json()["message"]


def test_upload_rejects_invalid_image_signature(client, app, db_session: Session) -> None:
    admin = create_user(db_session, username="assets_admin_bad_sig", role=UserRole.admin)
    app.dependency_overrides[deps.get_current_user] = lambda: admin

    response = client.post(
        "/api/assets/upload",
        data={
            "owner_type": "product",
            "owner_id": str(uuid.uuid4()),
            "kind": "image",
        },
        files={"file": ("image.png", b"not-an-image", "image/png")},
    )

    assert response.status_code == 400
    assert (
        "signature" in response.json()["message"].lower()
        or "unknown" in response.json()["message"].lower()
    )


def test_upload_rejects_files_above_kind_limit(
    client, app, db_session: Session, monkeypatch
) -> None:
    admin = create_user(db_session, username="assets_admin_too_large", role=UserRole.admin)
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    monkeypatch.setattr(settings, "UPLOAD_MAX_IMAGE_BYTES", 8)

    response = client.post(
        "/api/assets/upload",
        data={
            "owner_type": "product",
            "owner_id": str(uuid.uuid4()),
            "kind": "image",
        },
        files={"file": ("image.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 413


def test_upload_deduplicates_by_hash(client, app, db_session: Session) -> None:
    admin = create_user(db_session, username="assets_admin_dup", role=UserRole.admin)
    app.dependency_overrides[deps.get_current_user] = lambda: admin

    owner_id = str(uuid.uuid4())
    payload = {
        "owner_type": "product",
        "owner_id": owner_id,
        "kind": "image",
    }

    first = client.post(
        "/api/assets/upload",
        data=payload,
        files={"file": ("item.png", _png_bytes(), "image/png")},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/assets/upload",
        data=payload,
        files={"file": ("item-copy.png", _png_bytes(), "image/png")},
    )
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    stored_files = list(Path(settings.UPLOADS_DIR).rglob("*"))
    stored_files = [path for path in stored_files if path.is_file()]
    assert len(stored_files) == 1


def test_upload_allows_same_hash_for_different_owner(client, app, db_session: Session) -> None:
    admin = create_user(db_session, username="assets_admin_dup_owner", role=UserRole.admin)
    app.dependency_overrides[deps.get_current_user] = lambda: admin

    first = client.post(
        "/api/assets/upload",
        data={
            "owner_type": "product",
            "owner_id": str(uuid.uuid4()),
            "kind": "image",
        },
        files={"file": ("item.png", _png_bytes(), "image/png")},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/assets/upload",
        data={
            "owner_type": "product",
            "owner_id": str(uuid.uuid4()),
            "kind": "image",
        },
        files={"file": ("item-copy.png", _png_bytes(), "image/png")},
    )
    assert second.status_code == 200
    assert first.json()["id"] != second.json()["id"]


def test_upload_starts_in_quarantine_state(client, app, db_session: Session) -> None:
    admin = create_user(db_session, username="assets_admin_quarantine", role=UserRole.admin)
    app.dependency_overrides[deps.get_current_user] = lambda: admin

    response = client.post(
        "/api/assets/upload",
        data={
            "owner_type": "product",
            "owner_id": str(uuid.uuid4()),
            "kind": "image",
        },
        files={"file": ("item.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["review_state"] == "quarantine"


def test_web_asset_rejects_local_path_and_server_metadata(
    client, app, db_session: Session, tmp_path: Path
) -> None:
    admin = create_user(db_session, username="assets_admin_web_injection", role=UserRole.admin)
    app.dependency_overrides[deps.get_current_user] = lambda: admin

    response = client.post(
        "/api/assets/web",
        json={
            "owner_type": "product",
            "owner_id": str(uuid.uuid4()),
            "kind": "image",
            "url": "https://example.com/image.png",
            "local_path": str(tmp_path / "secret.txt"),
            "source": "upload",
            "hash": "client-controlled",
            "size_bytes": 1,
            "review_state": "approved",
            "workflow_status": "approved",
        },
    )

    assert response.status_code == 422
    assert db_session.query(Asset).count() == 0


def test_web_asset_sets_security_sensitive_fields_server_side(
    client, app, db_session: Session
) -> None:
    admin = create_user(db_session, username="assets_admin_web_safe", role=UserRole.admin)
    app.dependency_overrides[deps.get_current_user] = lambda: admin

    response = client.post(
        "/api/assets/web",
        json={
            "owner_type": "product",
            "owner_id": str(uuid.uuid4()),
            "kind": "image",
            "url": "https://example.com/image.png",
            "title": "Safe web image",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "web"
    assert body["local_path"] is None
    assert body["hash"] is None
    assert body["size_bytes"] is None
    assert body["review_state"] == "needs_review"
    assert body["workflow_status"] == "draft"


def test_web_primary_product_image_replaces_previous_primary(
    client, app, db_session: Session
) -> None:
    admin = create_user(db_session, username="assets_admin_primary_web", role=UserRole.admin)
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()
    previous_primary = Asset(
        owner_type=AssetOwnerType.product,
        owner_id=owner_id,
        kind=AssetKind.image,
        source=AssetSource.web,
        url="https://example.com/previous.png",
        is_primary=True,
    )
    other_owner_primary = Asset(
        owner_type=AssetOwnerType.product,
        owner_id=other_owner_id,
        kind=AssetKind.image,
        source=AssetSource.web,
        url="https://example.com/other.png",
        is_primary=True,
    )
    db_session.add_all([previous_primary, other_owner_primary])
    db_session.commit()

    response = client.post(
        "/api/assets/web",
        json={
            "owner_type": "product",
            "owner_id": str(owner_id),
            "kind": "image",
            "url": "https://example.com/new.png",
            "is_primary": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["is_primary"] is True
    db_session.refresh(previous_primary)
    db_session.refresh(other_owner_primary)
    assert previous_primary.is_primary is False
    assert other_owner_primary.is_primary is True
    assert (
        db_session.query(Asset)
        .filter(
            Asset.owner_type == AssetOwnerType.product,
            Asset.owner_id == owner_id,
            Asset.kind == AssetKind.image,
            Asset.is_primary.is_(True),
        )
        .count()
        == 1
    )


def test_database_rejects_duplicate_primary_product_images(db_session: Session) -> None:
    owner_id = uuid.uuid4()
    db_session.add_all(
        [
            Asset(
                owner_type=AssetOwnerType.product,
                owner_id=owner_id,
                kind=AssetKind.image,
                source=AssetSource.web,
                url=f"https://example.com/{index}.png",
                is_primary=True,
            )
            for index in range(2)
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_asset_delivery_rejects_paths_outside_storage_roots(
    client, app, db_session: Session, tmp_path: Path
) -> None:
    admin = create_user(db_session, username="assets_admin_path_escape", role=UserRole.admin)
    app.dependency_overrides[deps.get_current_user] = lambda: admin

    upload_root = Path(settings.UPLOADS_DIR)
    upload_root.mkdir(parents=True, exist_ok=True)
    secret_path = tmp_path / "secret.png"
    secret_path.write_bytes(_png_bytes())
    escaped_path = upload_root / ".." / secret_path.name
    asset = Asset(
        owner_type=AssetOwnerType.product,
        owner_id=uuid.uuid4(),
        kind=AssetKind.image,
        source=AssetSource.upload,
        local_path=str(escaped_path),
        review_state=AssetReviewState.approved,
        workflow_status=WorkflowStatus.approved,
    )
    db_session.add(asset)
    db_session.commit()

    file_response = client.get(f"/api/assets/{asset.id}/file")
    thumb_response = client.get(f"/api/assets/{asset.id}/thumb")

    assert file_response.status_code == 404
    assert thumb_response.status_code == 404
    assert secret_path.read_bytes() == _png_bytes()


def test_asset_delivery_allows_files_inside_upload_root(client, app, db_session: Session) -> None:
    admin = create_user(db_session, username="assets_admin_path_safe", role=UserRole.admin)
    app.dependency_overrides[deps.get_current_user] = lambda: admin

    safe_path = Path(settings.UPLOADS_DIR) / "product" / "safe.png"
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _png_bytes()
    safe_path.write_bytes(payload)
    asset = Asset(
        owner_type=AssetOwnerType.product,
        owner_id=uuid.uuid4(),
        kind=AssetKind.image,
        source=AssetSource.upload,
        local_path=str(safe_path),
        review_state=AssetReviewState.approved,
        workflow_status=WorkflowStatus.approved,
    )
    db_session.add(asset)
    db_session.commit()

    response = client.get(f"/api/assets/{asset.id}/file")
    thumb_response = client.get(f"/api/assets/{asset.id}/thumb")

    assert response.status_code == 200
    assert response.content == payload
    assert thumb_response.status_code == 200
    assert thumb_response.headers["content-type"].startswith("image/")


def test_content_asset_create_and_review_refresh_readiness(
    client, app, db_session: Session
) -> None:
    admin = create_user(db_session, username="assets_admin_readiness", role=UserRole.admin)
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    item = ContentItem(
        platform=ContentPlatform.youtube,
        type=ContentType.review,
        status=ContentStatus.draft,
        title="Readiness item",
        platform_meta_json={},
        workflow_status=WorkflowStatus.draft,
        editorial_status=EditorialStatus.backlog,
        readiness_score=13,
    )
    db_session.add(item)
    db_session.commit()

    created = client.post(
        "/api/assets/web",
        json={
            "owner_type": "content",
            "owner_id": str(item.id),
            "kind": "image",
            "url": "https://example.com/content-image.png",
        },
    )

    assert created.status_code == 200
    db_session.refresh(item)
    assert item.readiness_score == 80

    pending = client.patch(
        f"/api/assets/{created.json()['id']}",
        json={"review_state": "pending"},
    )
    assert pending.status_code == 200

    approved = client.patch(
        f"/api/assets/{created.json()['id']}",
        json={"review_state": "approved", "review_reason": "Image verified"},
    )

    assert approved.status_code == 200
    db_session.refresh(item)
    assert item.readiness_score == 100
