from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import Request
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings
from app.db.session import SessionLocal

logger = logging.getLogger("app.observability")
alert_logger = logging.getLogger("app.alerting")

DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

_metrics_lock = threading.Lock()
_counter_values: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
_gauge_values: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
_hist_values: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, Any]] = {}

_alert_state_lock = threading.Lock()
_alert_state: dict[str, dict[str, Any]] = {}
_failure_counters = {
    "db": 0,
    "redis": 0,
    "worker": 0,
}

_db_instrumented = False


def _label_items(labels: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    labels = labels or {}
    return tuple(sorted((str(k), str(v)) for k, v in labels.items()))


def _labels_str(items: tuple[tuple[str, str], ...]) -> str:
    if not items:
        return ""
    values = ",".join(f'{k}="{v}"' for k, v in items)
    return "{" + values + "}"


def inc_counter(name: str, value: float = 1.0, **labels: Any) -> None:
    key = (name, _label_items(labels))
    with _metrics_lock:
        _counter_values[key] += float(value)


def set_gauge(name: str, value: float, **labels: Any) -> None:
    key = (name, _label_items(labels))
    with _metrics_lock:
        _gauge_values[key] = float(value)


def observe_histogram(name: str, value: float, *, buckets: tuple[float, ...] = DEFAULT_BUCKETS, **labels: Any) -> None:
    key = (name, _label_items(labels))
    with _metrics_lock:
        state = _hist_values.get(key)
        if state is None:
            state = {
                "buckets": tuple(sorted(buckets)),
                "bucket_counts": defaultdict(float),
                "sum": 0.0,
                "count": 0.0,
            }
            _hist_values[key] = state

        state["sum"] += float(value)
        state["count"] += 1.0
        for upper in state["buckets"]:
            if value <= upper:
                state["bucket_counts"][upper] += 1.0
        state["bucket_counts"][float("inf")] += 1.0


def get_metrics_prometheus_text() -> str:
    lines: list[str] = []
    with _metrics_lock:
        for (name, labels), value in sorted(_counter_values.items(), key=lambda item: item[0][0]):
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name}{_labels_str(labels)} {value}")

        for (name, labels), value in sorted(_gauge_values.items(), key=lambda item: item[0][0]):
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name}{_labels_str(labels)} {value}")

        for (name, labels), state in sorted(_hist_values.items(), key=lambda item: item[0][0]):
            lines.append(f"# TYPE {name} histogram")
            for upper in state["buckets"]:
                bucket_labels = labels + (("le", str(upper)),)
                count = state["bucket_counts"].get(upper, 0.0)
                lines.append(f"{name}_bucket{_labels_str(bucket_labels)} {count}")
            inf_labels = labels + (("le", "+Inf"),)
            lines.append(
                f"{name}_bucket{_labels_str(inf_labels)} {state['bucket_counts'].get(float('inf'), 0.0)}"
            )
            lines.append(f"{name}_sum{_labels_str(labels)} {state['sum']}")
            lines.append(f"{name}_count{_labels_str(labels)} {state['count']}")

    return "\n".join(lines) + "\n"


def get_alert_state() -> dict[str, dict[str, Any]]:
    with _alert_state_lock:
        return {k: dict(v) for k, v in _alert_state.items()}


def _set_alert(code: str, *, active: bool, severity: str, message: str) -> None:
    with _alert_state_lock:
        previous = _alert_state.get(code)
        current = {
            "active": active,
            "severity": severity,
            "message": message,
            "updated_at_unix": int(time.time()),
        }
        _alert_state[code] = current

    if previous is None or bool(previous.get("active")) != active:
        level = logging.ERROR if active else logging.INFO
        alert_logger.log(level, "Observability alert state changed", extra={"alert_code": code, **current})


def get_alert_definitions(settings: Settings) -> dict[str, Any]:
    return {
        "db_unavailable": {
            "severity": "critical",
            "trigger": f">= {settings.ALERT_DB_FAILURE_CONSECUTIVE} consecutive DB check failures",
        },
        "redis_unavailable": {
            "severity": "critical",
            "trigger": f">= {settings.ALERT_REDIS_FAILURE_CONSECUTIVE} consecutive Redis check failures",
        },
        "worker_unavailable": {
            "severity": "high",
            "trigger": f">= {settings.ALERT_WORKER_FAILURE_CONSECUTIVE} consecutive worker check failures",
        },
        "queue_depth_high": {
            "severity": "high",
            "trigger": f"queue length >= {settings.ALERT_QUEUE_LENGTH_WARN}",
        },
        "queue_depth_critical": {
            "severity": "critical",
            "trigger": f"queue length >= {settings.ALERT_QUEUE_LENGTH_CRITICAL}",
        },
        "failed_jobs_spike": {
            "severity": "critical",
            "trigger": f"failed jobs >= {settings.ALERT_FAILED_JOBS_CRITICAL}",
        },
    }


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        method = request.method.upper()
        status_code = 500
        route_path = request.url.path
        try:
            response = await call_next(request)
            status_code = response.status_code
            route_obj = request.scope.get("route")
            route_path = getattr(route_obj, "path", route_path)
            return response
        except Exception:
            route_obj = request.scope.get("route")
            route_path = getattr(route_obj, "path", route_path)
            inc_counter(
                "api_errors_total",
                method=method,
                path=route_path,
                status="500",
            )
            raise
        finally:
            duration = max(0.0, time.perf_counter() - started)
            inc_counter(
                "api_requests_total",
                method=method,
                path=route_path,
                status=str(status_code),
            )
            observe_histogram(
                "api_request_latency_seconds",
                duration,
                method=method,
                path=route_path,
                status=str(status_code),
            )
            if status_code >= 500:
                inc_counter(
                    "api_errors_total",
                    method=method,
                    path=route_path,
                    status=str(status_code),
                )


def setup_db_observability(engine: Engine) -> None:
    global _db_instrumented
    if _db_instrumented:
        return

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._obs_started = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        started = getattr(context, "_obs_started", None)
        if started is None:
            return
        duration = max(0.0, time.perf_counter() - started)
        observe_histogram("db_query_latency_seconds", duration, statement="sql")
        inc_counter("db_queries_total", statement="sql", status="ok")

    @event.listens_for(engine, "handle_error")
    def _handle_error(exception_context):
        inc_counter("db_queries_total", statement="sql", status="error")
        inc_counter("db_query_errors_total", statement="sql")

    _db_instrumented = True


def observe_redis_call(command: str, func: Callable[[], Any]) -> Any:
    started = time.perf_counter()
    try:
        result = func()
        duration = max(0.0, time.perf_counter() - started)
        inc_counter("redis_commands_total", command=command, status="ok")
        observe_histogram("redis_command_latency_seconds", duration, command=command, status="ok")
        return result
    except Exception:
        duration = max(0.0, time.perf_counter() - started)
        inc_counter("redis_commands_total", command=command, status="error")
        inc_counter("redis_command_errors_total", command=command)
        observe_histogram(
            "redis_command_latency_seconds",
            duration,
            command=command,
            status="error",
        )
        raise


def collect_worker_snapshot(redis_conn: Any, queue_names: list[str] | None = None) -> dict[str, Any]:
    from rq import Queue
    from rq.registry import FailedJobRegistry, FinishedJobRegistry, StartedJobRegistry

    queue_names = queue_names or ["default"]
    summary: dict[str, Any] = {
        "queues": {},
        "worker_ok": True,
        "max_queue_length": 0,
        "failed_jobs_total": 0,
    }

    for queue_name in queue_names:
        queue = Queue(queue_name, connection=redis_conn)
        queued = int(queue.count)
        started = int(len(StartedJobRegistry(queue=queue).get_job_ids()))
        failed = int(len(FailedJobRegistry(queue=queue).get_job_ids()))
        finished = int(len(FinishedJobRegistry(queue=queue).get_job_ids()))

        summary["queues"][queue_name] = {
            "queued": queued,
            "started": started,
            "failed": failed,
            "finished": finished,
        }
        summary["max_queue_length"] = max(int(summary["max_queue_length"]), queued)
        summary["failed_jobs_total"] = int(summary["failed_jobs_total"]) + failed

        set_gauge("worker_queue_length", queued, queue=queue_name)
        set_gauge("worker_jobs_visible", started, queue=queue_name, state="started")
        set_gauge("worker_jobs_visible", failed, queue=queue_name, state="failed")
        set_gauge("worker_jobs_visible", finished, queue=queue_name, state="finished")

    return summary


def _check_db() -> tuple[bool, float]:
    started = time.perf_counter()
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True, max(0.0, time.perf_counter() - started)
    except Exception:
        return False, max(0.0, time.perf_counter() - started)
    finally:
        db.close()


def monitor_once(app, settings: Settings) -> dict[str, Any]:
    db_ok, db_latency = _check_db()
    observe_histogram("dependency_check_latency_seconds", db_latency, component="db")
    set_gauge("service_availability", 1.0 if db_ok else 0.0, component="db")

    redis_client = getattr(app.state, "redis_client", None)
    redis_ok = False
    redis_latency = 0.0
    if redis_client is not None:
        started = time.perf_counter()
        try:
            redis_ok = bool(observe_redis_call("ping", lambda: redis_client.ping()))
        except Exception:
            redis_ok = False
        redis_latency = max(0.0, time.perf_counter() - started)
    observe_histogram("dependency_check_latency_seconds", redis_latency, component="redis")
    set_gauge("service_availability", 1.0 if redis_ok else 0.0, component="redis")

    worker_ok = True
    worker_snapshot: dict[str, Any] = {
        "queues": {},
        "worker_ok": False,
        "max_queue_length": 0,
        "failed_jobs_total": 0,
    }
    try:
        from app.workers.queue import redis_conn

        worker_snapshot = collect_worker_snapshot(redis_conn, queue_names=["default"])
        worker_ok = bool(worker_snapshot.get("worker_ok", True))
    except Exception:
        worker_ok = False
    set_gauge("service_availability", 1.0 if worker_ok else 0.0, component="worker")

    _failure_counters["db"] = _failure_counters["db"] + 1 if not db_ok else 0
    _failure_counters["redis"] = _failure_counters["redis"] + 1 if not redis_ok else 0
    _failure_counters["worker"] = _failure_counters["worker"] + 1 if not worker_ok else 0

    _set_alert(
        "db_unavailable",
        active=_failure_counters["db"] >= settings.ALERT_DB_FAILURE_CONSECUTIVE,
        severity="critical",
        message="Database readiness checks are failing repeatedly",
    )
    _set_alert(
        "redis_unavailable",
        active=_failure_counters["redis"] >= settings.ALERT_REDIS_FAILURE_CONSECUTIVE,
        severity="critical",
        message="Redis readiness checks are failing repeatedly",
    )
    _set_alert(
        "worker_unavailable",
        active=_failure_counters["worker"] >= settings.ALERT_WORKER_FAILURE_CONSECUTIVE,
        severity="high",
        message="Worker checks are failing repeatedly",
    )

    queue_len = int(worker_snapshot.get("max_queue_length") or 0)
    failed_jobs = int(worker_snapshot.get("failed_jobs_total") or 0)
    _set_alert(
        "queue_depth_high",
        active=queue_len >= settings.ALERT_QUEUE_LENGTH_WARN,
        severity="high",
        message=f"Queue depth warning: {queue_len}",
    )
    _set_alert(
        "queue_depth_critical",
        active=queue_len >= settings.ALERT_QUEUE_LENGTH_CRITICAL,
        severity="critical",
        message=f"Queue depth critical: {queue_len}",
    )
    _set_alert(
        "failed_jobs_spike",
        active=failed_jobs >= settings.ALERT_FAILED_JOBS_CRITICAL,
        severity="critical",
        message=f"Failed jobs threshold exceeded: {failed_jobs}",
    )

    snapshot = {
        "db_ok": db_ok,
        "db_latency_seconds": db_latency,
        "redis_ok": redis_ok,
        "redis_latency_seconds": redis_latency,
        "worker_ok": worker_ok,
        "queue_max_length": queue_len,
        "failed_jobs_total": failed_jobs,
        "alerts": get_alert_state(),
    }
    setattr(app.state, "observability_snapshot", snapshot)
    return snapshot


async def observability_monitor_daemon(app, settings: Settings) -> None:
    interval = max(5, int(settings.OBSERVABILITY_MONITOR_INTERVAL_SECONDS))
    while True:
        try:
            monitor_once(app, settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Observability monitor cycle failed")
            inc_counter("observability_monitor_errors_total")
        await asyncio.sleep(interval)


@dataclass
class TracingInitResult:
    enabled: bool
    reason: str


def configure_otel_tracing(app, settings: Settings, engine: Engine) -> TracingInitResult:
    if not settings.OTEL_ENABLED:
        return TracingInitResult(enabled=False, reason="disabled_by_config")

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    except Exception as exc:
        logger.warning("OpenTelemetry not available", extra={"reason": exc.__class__.__name__})
        return TracingInitResult(enabled=False, reason="otel_packages_missing")

    if not (settings.OTEL_EXPORTER_OTLP_ENDPOINT or "").strip():
        logger.warning("OpenTelemetry enabled but no OTLP endpoint configured")
        return TracingInitResult(enabled=False, reason="missing_otlp_endpoint")

    provider = TracerProvider(
        sampler=TraceIdRatioBased(float(settings.OTEL_SAMPLE_RATIO)),
        resource=Resource.create({"service.name": settings.OTEL_SERVICE_NAME}),
    )
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                insecure=bool(settings.OTEL_EXPORTER_OTLP_INSECURE),
            )
        )
    )
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    RequestsInstrumentor().instrument()
    RedisInstrumentor().instrument()

    logger.info("OpenTelemetry tracing enabled")
    return TracingInitResult(enabled=True, reason="ok")
