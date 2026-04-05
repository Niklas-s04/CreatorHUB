#!/usr/bin/env python3
"""
Pre-deploy secret validation script.

Ensures all required secrets meet minimum security requirements before deployment.
Exit code 0: All checks passed
Exit code 1: Validation errors found
"""

import os
import sys
from pathlib import Path


class SecretValidator:
    """Validates deployment secrets against security requirements."""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []
        self._load_env()

    def _load_env(self):
        """Load .env file if it exists."""
        env_file = Path(".env")
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        os.environ[key.strip()] = value

    def check_secret(self, var_name: str, min_length: int, description: str) -> bool:
        """Check if a secret meets minimum requirements."""
        value = os.environ.get(var_name, "").strip()

        if not value:
            self.errors.append(f"{var_name}: Not set - {description}")
            return False

        if len(value) < min_length:
            self.errors.append(
                f"{var_name}: Too short ({len(value)}/{min_length} chars) - {description}"
            )
            return False

        self.passed.append(f"{var_name}: OK ({len(value)} chars)")
        return True

    def check_not_placeholder(
        self, var_name: str, forbidden_value: str, description: str
    ) -> bool:
        """Check that a secret is not a placeholder value."""
        value = os.environ.get(var_name, "")

        if value == forbidden_value:
            self.errors.append(
                f"{var_name}: Still has placeholder value '{forbidden_value}' - {description}"
            )
            return False

        return True

    def validate(self) -> bool:
        """Run all validations."""
        print("=" * 50)
        print("Pre-Deploy Secret Validation")
        print("=" * 50)
        print()

        print("Checking required secrets...")
        self.check_secret("JWT_SECRET", 32, "JWT signing key")
        self.check_secret("POSTGRES_PASSWORD", 16, "Database password")
        self.check_secret("BOOTSTRAP_ADMIN_PASSWORD", 12, "Admin password")

        print()
        print("Checking for placeholder values...")
        self.check_not_placeholder("JWT_SECRET", "change_me", "JWT_SECRET placeholder")
        self.check_not_placeholder(
            "BOOTSTRAP_ADMIN_PASSWORD", "admin", "Admin password placeholder"
        )

        if os.environ.get("ENV", "dev").strip().lower() == "prod":
            self.check_secret(
                "AUTH_COOKIE_DOMAIN",
                1,
                "AUTH_COOKIE_DOMAIN must be set in production",
            )

        print()
        print("Checking database configuration...")
        if not os.environ.get("DATABASE_URL"):
            if os.environ.get("POSTGRES_USER") and os.environ.get("POSTGRES_DB"):
                self.passed.append("POSTGRES_*: Variables set for auto-construction")
            else:
                self.warnings.append(
                    "DATABASE_URL not set and POSTGRES_* not fully configured"
                )
        else:
            self.passed.append("DATABASE_URL: Configured")

        print()
        print("=" * 50)
        print("Results:")
        print("=" * 50)

        if self.passed:
            print("\n✓ Passed checks:")
            for msg in self.passed:
                print(f"  {msg}")

        if self.warnings:
            print("\n⚠ Warnings:")
            for msg in self.warnings:
                print(f"  {msg}")

        if self.errors:
            print("\n✗ Errors:")
            for msg in self.errors:
                print(f"  {msg}")
            print()
            print(f"Total errors: {len(self.errors)}")
            return False

        print()
        print("✓ All validations passed!")
        return True


if __name__ == "__main__":
    validator = SecretValidator()
    success = validator.validate()
    sys.exit(0 if success else 1)
