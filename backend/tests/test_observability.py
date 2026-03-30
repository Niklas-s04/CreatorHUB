from __future__ import annotations

from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import health
from app.core import observability
from app.core.config import settings


def _health_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health.router)
    app.state.startup_complete = True
    app.state.bootstrap_complete = True
    app.state.auto_archive_task = None
    app.state.redis_client = Mock()
    app.state.redis_client.ping.return_value = True
    return app


def test_metrics_endpoint_returns_prometheus_payload(monkeypatch) -> None:
    monkeypatch.setattr(settings, "OBSERVABILITY_METRICS_ENABLED", True)
    observability.inc_counter("api_requests_total", method="GET", path="/health", status="200")

    app = _health_app()
    with TestClient(app) as client:
        response = client.get("/health/metrics")

    assert response.status_code == 200
    assert "api_requests_total" in response.text
    assert "# TYPE api_requests_total counter" in response.text


def test_alerts_endpoint_returns_definitions_and_state(monkeypatch) -> None:
    monkeypatch.setattr(health, "monitor_once", lambda app, cfg: {"ok": True})
    app = _health_app()

    with TestClient(app) as client:
        response = client.get("/health/alerts")

    assert response.status_code == 200
    payload = response.json()
    assert "definitions" in payload
    assert "db_unavailable" in payload["definitions"]
    assert "active" in payload


def test_background_jobs_endpoint_exposes_queue_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(health, "monitor_once", lambda app, cfg: {"ok": True})
    monkeypatch.setattr(
        health,
        "collect_worker_snapshot",
        lambda redis_conn, queue_names=None: {
            "worker_ok": True,
            "queues": {"default": {"queued": 3, "started": 1, "failed": 0, "finished": 2}},
            "max_queue_length": 3,
            "failed_jobs_total": 0,
        },
    )

    app = _health_app()
    with TestClient(app) as client:
        response = client.get("/health/background-jobs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["queue"]["max_queue_length"] == 3
    assert payload["queue"]["worker_ok"] is True
