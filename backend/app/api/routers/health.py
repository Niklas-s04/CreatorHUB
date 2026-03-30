from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import text
from starlette.responses import PlainTextResponse

from app.core.config import settings
from app.core.observability import (
    collect_worker_snapshot,
    get_alert_definitions,
    get_alert_state,
    get_metrics_prometheus_text,
    monitor_once,
)
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


@router.get("/health/metrics", include_in_schema=False)
def metrics() -> PlainTextResponse:
    if not settings.OBSERVABILITY_METRICS_ENABLED:
        raise HTTPException(status_code=404, detail="Metrics endpoint disabled")
    return PlainTextResponse(
        get_metrics_prometheus_text(), media_type="text/plain; version=0.0.4; charset=utf-8"
    )


@router.get("/health/background-jobs")
def background_jobs(request: Request) -> dict:
    auto_archive_task = getattr(request.app.state, "auto_archive_task", None)
    auto_archive_state = {
        "enabled": bool(settings.AUTO_ARCHIVE_ENABLED),
        "running": bool(auto_archive_task and not auto_archive_task.done()),
        "done": bool(auto_archive_task.done()) if auto_archive_task else False,
    }

    queue_snapshot: dict[str, object]
    try:
        from app.workers.queue import redis_conn

        queue_snapshot = collect_worker_snapshot(redis_conn, queue_names=["default"])
    except Exception as exc:
        queue_snapshot = {
            "worker_ok": False,
            "error": exc.__class__.__name__,
            "queues": {},
            "max_queue_length": 0,
            "failed_jobs_total": 0,
        }

    snapshot = monitor_once(request.app, settings)
    return {
        "auto_archive": auto_archive_state,
        "queue": queue_snapshot,
        "latest_probe": snapshot,
    }


@router.get("/health/alerts")
def alerts(request: Request) -> dict:
    monitor_once(request.app, settings)
    state = get_alert_state()
    active = [
        {"code": code, **payload} for code, payload in state.items() if bool(payload.get("active"))
    ]
    return {
        "definitions": get_alert_definitions(settings),
        "active": active,
        "state": state,
    }
