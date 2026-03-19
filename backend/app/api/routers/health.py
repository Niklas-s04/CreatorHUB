from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import text

from app.db.session import SessionLocal

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    startup_complete = bool(getattr(request.app.state, "startup_complete", False))
    bootstrap_complete = bool(getattr(request.app.state, "bootstrap_complete", False))
    return {
        "status": "ok" if startup_complete else "starting",
        "startup_complete": startup_complete,
        "bootstrap_complete": bootstrap_complete,
    }


@router.get("/health/live")
def liveness() -> dict:
    return {"status": "alive"}


def _db_ready() -> bool:
    db_ok = False
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        db.close()
    return db_ok


@router.get("/health/ready")
def readiness(request: Request, response: Response) -> dict:
    startup_complete = bool(getattr(request.app.state, "startup_complete", False))
    bootstrap_complete = bool(getattr(request.app.state, "bootstrap_complete", False))
    auto_archive_task = getattr(request.app.state, "auto_archive_task", None)
    redis_client = getattr(request.app.state, "redis_client", None)

    db_ok = _db_ready()
    redis_ok = False
    try:
        if redis_client is not None:
            redis_ok = bool(redis_client.ping())
    except Exception:
        redis_ok = False

    worker_ok = auto_archive_task is None or not auto_archive_task.done()
    ready = startup_complete and bootstrap_complete and db_ok and redis_ok and worker_ok
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready else "not_ready",
        "startup_complete": startup_complete,
        "bootstrap_complete": bootstrap_complete,
        "db": db_ok,
        "redis": redis_ok,
        "worker": worker_ok,
    }
