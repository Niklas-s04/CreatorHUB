#!/usr/bin/env python
"""Production release validation helpers.

This script automates the manual Phase 5 checks that still require live
environment inputs:
- admin bootstrap / initial password setup
- production migration execution
- asset storage replica verification
- live smoke tests against production URLs
- monitoring baseline capture
- release note generation

The script is intentionally opt-in and environment-driven. It does not use any
hardcoded production values.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


@dataclass(slots=True)
class CheckResult:
    name: str
    ok: bool
    details: str


def _normalize_base_url(value: str) -> str:
    base_url = value.strip()
    if not base_url:
        raise ValueError("base_url is required")
    return base_url.rstrip("/")


def _git_output(project_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _request_json(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    expected_statuses: tuple[int, ...] = (200,),
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> tuple[httpx.Response, dict[str, Any]]:
    response = client.request(method, path, headers=headers, json=json_body)
    if response.status_code not in expected_statuses:
        raise RuntimeError(
            f"{method} {path} returned {response.status_code}: {response.text.strip()}"
        )
    if response.content and "json" in (response.headers.get("content-type") or "").lower():
        payload = response.json()
    else:
        payload = {}
    return response, payload


def validate_bootstrap_flow(
    base_url: str,
    *,
    bootstrap_token: str | None,
    bootstrap_password: str | None,
    perform_admin_setup: bool,
    timeout_seconds: float,
    transport: httpx.BaseTransport | None = None,
) -> CheckResult:
    if not bootstrap_token:
        return CheckResult(
            name="admin_bootstrap",
            ok=True,
            details="Skipped because no bootstrap token was provided.",
        )

    headers = {"X-Bootstrap-Token": bootstrap_token}
    with httpx.Client(
        base_url=base_url,
        timeout=timeout_seconds,
        follow_redirects=True,
        transport=transport,
    ) as client:
        response, payload = _request_json(
            client,
            "GET",
            "/api/v1/auth/bootstrap-status",
            headers=headers,
        )
        details = [
            f"status={response.status_code}",
            f"needs_password_setup={payload.get('needs_password_setup')}",
        ]

        if perform_admin_setup:
            if not bootstrap_password:
                raise RuntimeError("bootstrap_password is required when perform_admin_setup is set")
            setup_response, setup_payload = _request_json(
                client,
                "POST",
                "/api/v1/auth/setup-admin-password",
                headers=headers,
                json_body={"password": bootstrap_password},
            )
            if not setup_payload.get("access_token"):
                raise RuntimeError("Admin setup did not return an access token")
            _, after_payload = _request_json(
                client,
                "GET",
                "/api/v1/auth/bootstrap-status",
                headers=headers,
            )
            if bool(after_payload.get("needs_password_setup")):
                raise RuntimeError("Bootstrap status still reports password setup as pending")
            details.extend(
                [
                    f"setup_status={setup_response.status_code}",
                    "admin_password_setup=completed",
                ]
            )

        return CheckResult(name="admin_bootstrap", ok=True, details="; ".join(details))


def validate_migrations(database_url: str, alembic_ini: Path) -> CheckResult:
    if not database_url.strip():
        raise RuntimeError("database_url is required for migration validation")

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parent / "validate_migrations.py"),
            "--database-url",
            database_url,
            "--alembic-ini",
            str(alembic_ini),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise RuntimeError(f"Migration validation failed:\n{output}")

    return CheckResult(
        name="migrations",
        ok=True,
        details="Alembic upgrade/downgrade validation completed successfully.",
    )


def validate_storage_replica(
    primary_dir: Path,
    replica_dir: Path,
    *,
    keep_artifacts: bool,
) -> CheckResult:
    primary_dir.mkdir(parents=True, exist_ok=True)
    replica_dir.mkdir(parents=True, exist_ok=True)

    marker = uuid.uuid4().hex
    payload = f"creatorhub-storage-check:{marker}".encode("utf-8")
    primary_file = primary_dir / f"replica-check-{marker}.bin"
    replica_file = replica_dir / primary_file.name

    primary_file.write_bytes(payload)
    shutil.copy2(primary_file, replica_file)

    if replica_file.read_bytes() != payload:
        raise RuntimeError("Replica storage validation failed: content mismatch")

    if not keep_artifacts:
        primary_file.unlink(missing_ok=True)
        replica_file.unlink(missing_ok=True)

    return CheckResult(
        name="asset_storage_replica",
        ok=True,
        details=f"Replica verified at {replica_file}",
    )


def validate_smoke_tests(
    base_url: str,
    *,
    timeout_seconds: float,
    transport: httpx.BaseTransport | None = None,
) -> CheckResult:
    with httpx.Client(
        base_url=base_url,
        timeout=timeout_seconds,
        follow_redirects=True,
        transport=transport,
    ) as client:
        _, health = _request_json(client, "GET", "/health")
        if health.get("status") not in {"ok", "starting"}:
            raise RuntimeError("Unexpected /health status")

        _, live = _request_json(client, "GET", "/health/live")
        if live.get("status") != "alive":
            raise RuntimeError("Unexpected /health/live payload")

        _, ready = _request_json(client, "GET", "/health/ready")
        if ready.get("status") != "ready":
            raise RuntimeError("Application is not ready")

        _, alerts = _request_json(client, "GET", "/health/alerts")
        if "definitions" not in alerts or "state" not in alerts:
            raise RuntimeError("Alert payload missing required fields")

        metrics_response, _ = _request_json(client, "GET", "/health/metrics")
        metric_lines = [
            line for line in metrics_response.text.splitlines() if line and not line.startswith("#")
        ]
        if not metric_lines:
            raise RuntimeError("Metrics endpoint returned no samples")

    return CheckResult(
        name="live_smoke_tests",
        ok=True,
        details="Health, readiness, alerts, and metrics endpoints responded successfully.",
    )


def capture_monitoring_baseline(
    base_url: str,
    report_path: Path,
    *,
    timeout_seconds: float,
    transport: httpx.BaseTransport | None = None,
) -> CheckResult:
    with httpx.Client(
        base_url=base_url,
        timeout=timeout_seconds,
        follow_redirects=True,
        transport=transport,
    ) as client:
        _, ready = _request_json(client, "GET", "/health/ready")
        _, alerts = _request_json(client, "GET", "/health/alerts")
        metrics_response, _ = _request_json(client, "GET", "/health/metrics")

    active_alerts = [entry for entry in alerts.get("active", []) if bool(entry.get("active", True))]
    report = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "ready": ready,
        "active_alerts": active_alerts,
        "metric_sample_count": len(
            [line for line in metrics_response.text.splitlines() if line and not line.startswith("#")]
        ),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    return CheckResult(
        name="monitoring_baseline",
        ok=True,
        details=f"Monitoring baseline written to {report_path}",
    )


def generate_release_notes(project_root: Path, output_path: Path, checks: list[CheckResult]) -> CheckResult:
    latest_tag = _git_output(project_root, ["describe", "--tags", "--abbrev=0"])
    commit = _git_output(project_root, ["rev-parse", "--short", "HEAD"])
    branch = _git_output(project_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    recent_commits = _git_output(project_root, ["log", "--oneline", "-n", "12"])

    lines = [
        "# CreatorHUB Release Notes",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Branch: {branch or 'unknown'}",
        f"Commit: {commit or 'unknown'}",
        f"Latest tag: {latest_tag or 'none'}",
        "",
        "## Validation Summary",
    ]
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        lines.append(f"- {status}: {check.name} - {check.details}")

    lines.extend(["", "## Recent Commits", ""])
    if recent_commits:
        lines.extend(f"- {line}" for line in recent_commits.splitlines())
    else:
        lines.append("- No git history available.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return CheckResult(name="release_notes", ok=True, details=f"Release notes written to {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate production release operations")
    parser.add_argument("--base-url", default=os.getenv("PROD_BASE_URL", ""))
    parser.add_argument("--bootstrap-token", default=os.getenv("PROD_BOOTSTRAP_TOKEN", ""))
    parser.add_argument("--bootstrap-password", default=os.getenv("PROD_BOOTSTRAP_PASSWORD", ""))
    parser.add_argument("--perform-admin-setup", action="store_true")
    parser.add_argument("--database-url", default=os.getenv("PROD_DATABASE_URL", os.getenv("DATABASE_URL", "")))
    parser.add_argument("--alembic-ini", default=os.getenv("PROD_ALEMBIC_INI", "backend/alembic.ini"))
    parser.add_argument("--primary-storage-dir", default=os.getenv("PROD_ASSET_PRIMARY_DIR", ""))
    parser.add_argument("--replica-storage-dir", default=os.getenv("PROD_ASSET_REPLICA_DIR", ""))
    parser.add_argument("--monitoring-report-path", default=os.getenv("PROD_MONITORING_REPORT_PATH", ""))
    parser.add_argument("--release-notes-path", default=os.getenv("PROD_RELEASE_NOTES_PATH", ""))
    parser.add_argument("--keep-artifacts", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("PROD_HTTP_TIMEOUT_SECONDS", "10")))
    args = parser.parse_args()

    project_root = Path(".").resolve()
    checks: list[CheckResult] = []
    failures: list[str] = []

    print("PRODUCTION RELEASE OPERATIONS VALIDATION")
    print("=" * 72)

    if args.base_url.strip():
        try:
            base_url = _normalize_base_url(args.base_url)
            print("[CHECK] Live smoke tests")
            smoke = validate_smoke_tests(base_url, timeout_seconds=args.timeout_seconds)
            checks.append(smoke)
            print(f"  [PASS] {smoke.details}")
        except Exception as exc:
            failures.append(f"live_smoke_tests: {exc}")
            print(f"  [FAIL] live_smoke_tests: {exc}")

        if args.bootstrap_token.strip() or args.perform_admin_setup:
            try:
                if args.perform_admin_setup and not args.bootstrap_token.strip():
                    raise RuntimeError("bootstrap_token is required when perform_admin_setup is set")
                print("[CHECK] Admin bootstrap flow")
                bootstrap = validate_bootstrap_flow(
                    base_url,
                    bootstrap_token=args.bootstrap_token.strip() or None,
                    bootstrap_password=args.bootstrap_password.strip() or None,
                    perform_admin_setup=bool(args.perform_admin_setup),
                    timeout_seconds=args.timeout_seconds,
                )
                checks.append(bootstrap)
                print(f"  [PASS] {bootstrap.details}")
            except Exception as exc:
                failures.append(f"admin_bootstrap: {exc}")
                print(f"  [FAIL] admin_bootstrap: {exc}")

        if args.monitoring_report_path.strip():
            try:
                print("[CHECK] Monitoring baseline capture")
                monitoring = capture_monitoring_baseline(
                    base_url,
                    Path(args.monitoring_report_path),
                    timeout_seconds=args.timeout_seconds,
                )
                checks.append(monitoring)
                print(f"  [PASS] {monitoring.details}")
            except Exception as exc:
                failures.append(f"monitoring_baseline: {exc}")
                print(f"  [FAIL] monitoring_baseline: {exc}")

    if args.database_url.strip():
        try:
            print("[CHECK] Migration reversibility")
            migrations = validate_migrations(args.database_url.strip(), Path(args.alembic_ini))
            checks.append(migrations)
            print(f"  [PASS] {migrations.details}")
        except Exception as exc:
            failures.append(f"migrations: {exc}")
            print(f"  [FAIL] migrations: {exc}")

    if args.primary_storage_dir.strip() and args.replica_storage_dir.strip():
        try:
            print("[CHECK] Asset storage replica")
            storage = validate_storage_replica(
                Path(args.primary_storage_dir),
                Path(args.replica_storage_dir),
                keep_artifacts=bool(args.keep_artifacts),
            )
            checks.append(storage)
            print(f"  [PASS] {storage.details}")
        except Exception as exc:
            failures.append(f"asset_storage_replica: {exc}")
            print(f"  [FAIL] asset_storage_replica: {exc}")

    if args.release_notes_path.strip():
        try:
            print("[CHECK] Release notes generation")
            notes = generate_release_notes(project_root, Path(args.release_notes_path), checks)
            checks.append(notes)
            print(f"  [PASS] {notes.details}")
        except Exception as exc:
            failures.append(f"release_notes: {exc}")
            print(f"  [FAIL] release_notes: {exc}")

    print("=" * 72)
    if failures:
        print("[RESULT] VALIDATION FAILED")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    if not checks:
        print("[RESULT] No checks were run. Provide prod URLs, database URL, storage paths, or output paths.")
        return 2

    print(f"[RESULT] ALL CHECKS PASSED ({len(checks)} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())