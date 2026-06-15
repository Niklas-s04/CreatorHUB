from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.models.user import UserRole
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
    assert "selected upload purpose" in response.json()["detail"]


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
        "signature" in response.json()["detail"].lower()
        or "unknown" in response.json()["detail"].lower()
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
