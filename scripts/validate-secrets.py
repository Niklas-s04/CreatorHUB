#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_dotenv() -> None:
    env_file = Path(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, _, value = raw.partition("=")
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def _check_secret(errors: list[str], name: str, min_length: int, description: str) -> None:
    value = os.getenv(name, "").strip()
    if not value:
        errors.append(f"{name}: missing - {description}")
    elif len(value) < min_length:
        errors.append(f"{name}: too short ({len(value)}/{min_length}) - {description}")


def _check_not_placeholder(errors: list[str], name: str, placeholders: set[str]) -> None:
    value = os.getenv(name, "").strip()
    if value in placeholders:
        errors.append(f"{name}: placeholder value is not allowed")


def main() -> int:
    _load_dotenv()
    errors: list[str] = []
    warnings: list[str] = []

    _check_secret(errors, "JWT_SECRET", 32, "JWT signing secret")
    _check_secret(errors, "BOOTSTRAP_ADMIN_PASSWORD", 12, "bootstrap admin password")
    _check_secret(errors, "POSTGRES_PASSWORD", 1, "database password")
    _check_not_placeholder(errors, "JWT_SECRET", {"change_me", "default", "test", "secret"})
    _check_not_placeholder(errors, "BOOTSTRAP_ADMIN_PASSWORD", {"admin", "password"})

    if os.getenv("ENV", "dev").strip().lower() == "prod":
        _check_secret(errors, "POSTGRES_PASSWORD", 16, "database password")
        _check_secret(errors, "AUTH_COOKIE_DOMAIN", 1, "production cookie domain")
        _check_secret(errors, "BOOTSTRAP_INSTALL_TOKEN", 16, "bootstrap install token")

    if not os.getenv("DATABASE_URL") and not (
        os.getenv("POSTGRES_USER") and os.getenv("POSTGRES_DB")
    ):
        warnings.append("DATABASE_URL is missing and POSTGRES_USER/POSTGRES_DB are incomplete")

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  - {warning}")

    if errors:
        print("Secret validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Secret validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
