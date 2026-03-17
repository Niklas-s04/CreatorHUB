from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_token
from app.models.bootstrap_state import BootstrapState


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_bootstrap_state(db: Session) -> BootstrapState:
    state = db.query(BootstrapState).order_by(BootstrapState.created_at.asc()).first()
    if state:
        return state

    configured_token = (settings.BOOTSTRAP_INSTALL_TOKEN or "").strip()
    token_hash = hash_token(configured_token) if configured_token else None
    state = BootstrapState(
        setup_enabled=True,
        install_token_hash=token_hash,
    )
    db.add(state)
    db.flush()
    return state


def assert_bootstrap_active(db: Session) -> BootstrapState:
    state = get_or_create_bootstrap_state(db)
    if not state.setup_enabled or state.setup_completed_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return state


def assert_valid_bootstrap_token(db: Session, provided_token: str | None) -> BootstrapState:
    state = assert_bootstrap_active(db)
    if state.install_token_consumed_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    candidate = (provided_token or "").strip()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bootstrap token required")

    expected_hash = state.install_token_hash
    if not expected_hash:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bootstrap token not configured")

    if hash_token(candidate) != expected_hash:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bootstrap token")

    return state


def finalize_bootstrap(state: BootstrapState, *, completed_by: str) -> None:
    now = utcnow()
    state.setup_enabled = False
    state.setup_completed_at = now
    state.setup_completed_by = completed_by
    state.install_token_consumed_at = now
