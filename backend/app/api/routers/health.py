from __future__ import annotations

from sqlalchemy import text
from redis import Redis

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.db.session import SessionLocal

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/health/live")
def liveness() -> dict:
    return {"status": "alive"}


@router.get("/health/ready")
def readiness(response: Response) -> dict:
    db_ok = False
    redis_ok = False

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        db.close()

    try:
        redis_client = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        redis_ok = bool(redis_client.ping())
    except Exception:
        redis_ok = False

    ready = db_ok and redis_ok
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready else "not_ready",
        "db": db_ok,
        "redis": redis_ok,
    }
