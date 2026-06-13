from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import httpx


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_prod_release.py"
SPEC = importlib.util.spec_from_file_location("validate_prod_release", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
PROD_RELEASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PROD_RELEASE
SPEC.loader.exec_module(PROD_RELEASE)


def test_normalize_base_url() -> None:
    assert PROD_RELEASE._normalize_base_url("https://example.com/") == "https://example.com"


def test_storage_replica_roundtrip(tmp_path) -> None:
    primary = tmp_path / "primary"
    replica = tmp_path / "replica"

    result = PROD_RELEASE.validate_storage_replica(primary, replica, keep_artifacts=False)

    assert result.ok is True
    assert result.name == "asset_storage_replica"
    assert not any(primary.iterdir())
    assert not any(replica.iterdir())


def test_http_smoke_and_bootstrap_flow() -> None:
    state = {"setup_called": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok", "startup_complete": True})
        if request.url.path == "/health/live":
            return httpx.Response(200, json={"status": "alive"})
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"status": "ready"})
        if request.url.path == "/health/alerts":
            return httpx.Response(200, json={"definitions": {"db_unavailable": {}}, "state": {}})
        if request.url.path == "/health/metrics":
            return httpx.Response(200, text="# TYPE api_requests_total counter\napi_requests_total 1\n")
        if request.url.path == "/api/v1/auth/bootstrap-status":
            if state["setup_called"]:
                return httpx.Response(200, json={"needs_password_setup": False})
            return httpx.Response(200, json={"needs_password_setup": True})
        if request.url.path == "/api/v1/auth/setup-admin-password":
            state["setup_called"] = True
            return httpx.Response(200, json={"access_token": "token"})
        return httpx.Response(404, json={"detail": "not found"})

    transport = httpx.MockTransport(handler)
    with httpx.Client(base_url="https://prod.example", transport=transport):
        smoke = PROD_RELEASE.validate_smoke_tests(
            "https://prod.example",
            timeout_seconds=1.0,
            transport=transport,
        )
        assert smoke.ok is True

        bootstrap = PROD_RELEASE.validate_bootstrap_flow(
            "https://prod.example",
            bootstrap_token="bootstrap-token",
            bootstrap_password="StrongPass123!",
            perform_admin_setup=True,
            timeout_seconds=1.0,
            transport=transport,
        )
        assert bootstrap.ok is True


def test_generate_release_notes(tmp_path, monkeypatch) -> None:
    def fake_git_output(project_root: Path, args: list[str]) -> str:
        mapping = {
            ("describe", "--tags", "--abbrev=0"): "v1.0.0",
            ("rev-parse", "--short", "HEAD"): "abc1234",
            ("rev-parse", "--abbrev-ref", "HEAD"): "main",
            ("log", "--oneline", "-n", "12"): "abc1234 Fix release checks",
        }
        return mapping.get(tuple(args), "")

    monkeypatch.setattr(PROD_RELEASE, "_git_output", fake_git_output)
    output = tmp_path / "release-notes.md"
    result = PROD_RELEASE.generate_release_notes(
        tmp_path,
        output,
        [PROD_RELEASE.CheckResult(name="smoke", ok=True, details="passed")],
    )

    assert result.ok is True
    content = output.read_text(encoding="utf-8")
    assert "CreatorHUB Release Notes" in content
    assert "smoke" in content
    assert "abc1234 Fix release checks" in content
