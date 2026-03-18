from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import UserRole
from tests.factories import create_tokens_for_user, create_user


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_csv_import_route_requires_privileged_role(client, db_session: Session) -> None:
    viewer = create_user(db_session, username="csv_viewer", role=UserRole.viewer)
    token, _ = create_tokens_for_user(db_session, user=viewer)

    response = client.post(
        "/api/products/import/csv",
        json={
            "csv_text": "title;currency\nPhone;EUR",
            "delimiter": ";",
            "quotechar": '"',
            "column_map": {"title": "title", "currency": "currency"},
            "dry_run": True,
        },
        headers=_auth_header(token),
    )

    assert response.status_code == 403


def test_csv_import_route_accepts_editor(client, db_session: Session) -> None:
    editor = create_user(db_session, username="csv_editor", role=UserRole.editor)
    token, _ = create_tokens_for_user(db_session, user=editor)

    response = client.post(
        "/api/products/import/csv",
        json={
            "csv_text": "title;currency\nPhone;EUR",
            "delimiter": ";",
            "quotechar": '"',
            "column_map": {"title": "title", "currency": "currency"},
            "dry_run": True,
        },
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rows_total"] == 1
    assert body["ready"] == 1
    assert body["inserted"] == 0
