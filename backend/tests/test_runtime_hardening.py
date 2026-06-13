from __future__ import annotations

import asyncio
import sys
import types

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.core import observability, web_security
from app.core.config import settings
from app.main import create_app


class _FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _statement):
        return None


class _FakeRedisPool:
    def disconnect(self):
        return None


class _FakeRedisClient:
    def __init__(self):
        self.connection_pool = _FakeRedisPool()

    def ping(self):
        return True

    def close(self):
        return None


async def _idle_daemon() -> None:
    while True:
        await asyncio.sleep(3600)


async def _idle_daemon_with_args(*_args, **_kwargs) -> None:
    await _idle_daemon()


def test_create_app_initializes_and_shuts_down(monkeypatch) -> None:
    monkeypatch.setattr("app.main.configure_logging", lambda _settings: None)
    monkeypatch.setattr("app.main.setup_db_observability", lambda _engine: None)
    monkeypatch.setattr("app.main.bootstrap_if_needed", lambda: None)
    monkeypatch.setattr("app.main.auto_archive_daemon", _idle_daemon)
    monkeypatch.setattr("app.main.purge_deleted_users_daemon", _idle_daemon)
    monkeypatch.setattr("app.main.observability_monitor_daemon", _idle_daemon_with_args)
    monkeypatch.setattr(
        "app.main.engine",
        type("E", (), {"connect": lambda self: _FakeConnection(), "dispose": lambda self: None})(),
    )
    monkeypatch.setattr("app.main.Redis.from_url", lambda *args, **kwargs: _FakeRedisClient())

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert app.state.startup_complete is True
        assert app.state.bootstrap_complete is True

    assert app.state.startup_complete is False


def test_security_headers_and_size_limits(monkeypatch) -> None:
    app = FastAPI()
    app.add_middleware(
        web_security.SecurityHeadersMiddleware,
        hsts_seconds=31536000,
        trust_proxy_headers=False,
        env="prod",
    )
    app.add_middleware(web_security.RequestSizeLimitMiddleware, max_body_size=8)

    @app.post("/echo")
    def echo() -> dict[str, str]:
        return {"ok": "true"}

    with TestClient(app, base_url="https://testserver") as client:
        response = client.post("/echo", content=b"1234")
        assert response.status_code == 200
        assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")
        assert response.headers["Content-Security-Policy"].startswith("default-src 'none'")

        rejected = client.post("/echo", content=b"123456789")
        assert rejected.status_code == 413

        invalid = client.post("/echo", headers={"content-length": "abc"}, content=b"1")
        assert invalid.status_code == 400


def test_rate_limit_and_csrf_helpers(monkeypatch) -> None:
    monkeypatch.setattr(
        web_security.Redis,
        "from_url",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("redis down")),
    )

    app = FastAPI()
    app.add_middleware(
        web_security.CsrfProtectionMiddleware,
        auth_cookie_name=settings.AUTH_ACCESS_COOKIE_NAME,
        csrf_cookie_name=settings.CSRF_COOKIE_NAME,
    )
    app.add_middleware(
        web_security.RateLimitMiddleware,
        redis_url="redis://localhost:6379/0",
        redis_prefix="rl",
        trust_proxy_headers=False,
        global_limit=1,
        window_seconds=60,
        auth_limit=1,
    )

    @app.post("/api/protected")
    def protected() -> JSONResponse:
        return JSONResponse({"ok": "true"})

    with TestClient(app) as client:
        first = client.post("/api/protected")
        second = client.post("/api/protected")
        assert first.status_code == 200
        assert second.status_code == 429


def test_auth_rate_limit_matches_versioned_and_legacy_paths(monkeypatch) -> None:
    monkeypatch.setattr(
        web_security.Redis,
        "from_url",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("redis down")),
    )

    middleware = web_security.RateLimitMiddleware(
        app=FastAPI(),
        redis_url="redis://localhost:6379/0",
        global_limit=240,
        auth_limit=10,
    )

    assert middleware._limit_for_path("/api/auth/token") == 10
    assert middleware._limit_for_path("/api/v1/auth/token") == 10
    assert middleware._limit_for_path("/api/auth/register-request") == 5
    assert middleware._limit_for_path("/api/v1/auth/register-request") == 5


def test_observability_helpers_and_metrics_rendering() -> None:
    observability.inc_counter("api_requests_total", method="GET", path="/health", status="200")
    observability.set_gauge("worker_queue_depth", 3, queue="default")
    observability.observe_histogram(
        "api_request_latency_seconds", 0.2, method="GET", path="/health"
    )
    payload = observability.get_metrics_prometheus_text()

    assert "api_requests_total" in payload
    assert "worker_queue_depth" in payload
    assert "api_request_latency_seconds" in payload

    definitions = observability.get_alert_definitions(settings)
    assert definitions["db_unavailable"]["severity"] == "critical"

    ok_value = observability.observe_redis_call("ping", lambda: "pong")
    assert ok_value == "pong"

    def _boom() -> None:
        raise RuntimeError("boom")

    try:
        observability.observe_redis_call("ping", _boom)
    except RuntimeError:
        pass


def test_observability_middleware_records_requests() -> None:
    app = FastAPI()
    app.add_middleware(observability.ObservabilityMiddleware)

    @app.get("/ok")
    def ok() -> dict[str, str]:
        return {"ok": "true"}

    with TestClient(app) as client:
        response = client.get("/ok")

    assert response.status_code == 200
    metrics = observability.get_metrics_prometheus_text()
    assert "api_requests_total" in metrics


def test_collect_worker_snapshot_aggregates_queue_state(monkeypatch) -> None:
    fake_rq = types.ModuleType("rq")
    fake_registry = types.ModuleType("rq.registry")

    class _FakeQueue:
        def __init__(self, queue_name, connection=None):
            self.queue_name = queue_name
            self.count = 4 if queue_name == "default" else 1

    class _BaseRegistry:
        def __init__(self, queue):
            self.queue = queue

    class _FakeStartedRegistry(_BaseRegistry):
        def get_job_ids(self):
            return ["s1"] if self.queue.queue_name == "default" else []

    class _FakeFailedRegistry(_BaseRegistry):
        def get_job_ids(self):
            return ["f1", "f2"] if self.queue.queue_name == "default" else ["f3"]

    class _FakeFinishedRegistry(_BaseRegistry):
        def get_job_ids(self):
            return ["done"] if self.queue.queue_name == "default" else ["done-2", "done-3"]

    fake_rq.Queue = _FakeQueue
    fake_registry.StartedJobRegistry = _FakeStartedRegistry
    fake_registry.FailedJobRegistry = _FakeFailedRegistry
    fake_registry.FinishedJobRegistry = _FakeFinishedRegistry
    monkeypatch.setitem(sys.modules, "rq", fake_rq)
    monkeypatch.setitem(sys.modules, "rq.registry", fake_registry)

    snapshot = observability.collect_worker_snapshot(object(), queue_names=["default", "bulk"])

    assert snapshot["worker_ok"] is True
    assert snapshot["max_queue_length"] == 4
    assert snapshot["failed_jobs_total"] == 3
    assert snapshot["queues"]["default"]["queued"] == 4
    assert snapshot["queues"]["bulk"]["failed"] == 1


def test_monitor_once_updates_alert_state(monkeypatch) -> None:
    class _FailingRedis:
        def ping(self):
            raise RuntimeError("redis unavailable")

    class _HealthyRedis:
        def ping(self):
            return True

    app = FastAPI()
    app.state.redis_client = _FailingRedis()

    monkeypatch.setattr(observability, "_check_db", lambda: (False, 0.05))
    monkeypatch.setattr(
        observability,
        "collect_worker_snapshot",
        lambda redis_conn, queue_names=None: {
            "queues": {"default": {"queued": 600, "started": 1, "failed": 20, "finished": 3}},
            "worker_ok": False,
            "max_queue_length": 600,
            "failed_jobs_total": 20,
        },
    )
    monkeypatch.setattr(
        observability,
        "_failure_counters",
        {"db": 0, "redis": 0, "worker": 0},
    )

    first = observability.monitor_once(app, settings)
    assert first["db_ok"] is False
    assert first["worker_ok"] is False
    assert first["alerts"]["db_unavailable"]["active"] is False
    assert first["alerts"]["queue_depth_critical"]["active"] is True

    app.state.redis_client = _HealthyRedis()
    monkeypatch.setattr(observability, "_check_db", lambda: (True, 0.02))
    monkeypatch.setattr(
        observability,
        "collect_worker_snapshot",
        lambda redis_conn, queue_names=None: {
            "queues": {"default": {"queued": 1, "started": 0, "failed": 0, "finished": 8}},
            "worker_ok": True,
            "max_queue_length": 1,
            "failed_jobs_total": 0,
        },
    )

    second = observability.monitor_once(app, settings)
    assert second["db_ok"] is True
    assert second["redis_ok"] is True
    assert second["worker_ok"] is True
    assert second["alerts"]["db_unavailable"]["active"] is False
    assert second["alerts"]["queue_depth_critical"]["active"] is False
