from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _compose_config() -> dict:
    config = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert isinstance(config, dict)
    return config


def test_compose_runs_migrations_before_backend_and_worker() -> None:
    services = _compose_config()["services"]

    assert services["migrate"]["command"] == ["python", "-m", "alembic", "upgrade", "head"]
    assert services["migrate"]["depends_on"]["db"]["condition"] == "service_healthy"
    for service_name in ("backend", "worker"):
        assert (
            services[service_name]["depends_on"]["migrate"]["condition"]
            == "service_completed_successfully"
        )


def test_compose_persists_and_shares_application_storage() -> None:
    config = _compose_config()
    expected_volumes = {"uploads_data", "cache_data", "exports_data"}

    assert expected_volumes <= set(config["volumes"])
    for service_name in ("backend", "worker"):
        mounts = {
            mount.split(":", maxsplit=1)[0] for mount in config["services"][service_name]["volumes"]
        }
        assert expected_volumes <= mounts


def test_runtime_bootstrap_does_not_create_database_schema() -> None:
    seed_source = (ROOT / "backend" / "app" / "seed.py").read_text(encoding="utf-8")

    assert "create_all" not in seed_source
