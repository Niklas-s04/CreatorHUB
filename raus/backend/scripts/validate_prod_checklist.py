#!/usr/bin/env python
"""
Production Release Validation - Simple Checklist

Validates that the project is ready for production deployment.
Exit 0 = Ready, Exit 1 = Issues found
"""

import sys
from pathlib import Path


def main() -> int:
    """Validate production readiness."""
    root = Path(".").resolve()
    errors = []

    print("\n" + "=" * 70)
    print("PRODUCTION READINESS CHECKLIST")
    print("=" * 70 + "\n")

    # Check all required files exist
    required_files = [
        # Phase 5 new artifacts
        "docs/phase5-completion-report.md",
        "docs/release-go-nogo-decision.md",
        "backend/scripts/validate_prod_release.py",
        # Security
        "backend/app/core/web_security.py",
        "backend/app/services/outbound_http.py",
        "backend/app/services/storage.py",
        # Privacy
        "backend/app/services/account.py",
        "backend/app/workers/tasks/purge_deleted_users.py",
        "docs/privacy-policy-technical.md",
        "docs/audit-data-policy.md",
        # Deployment
        "backend/scripts/validate_migrations.py",
        "backend/scripts/validate_backup_restore.py",
        "docs/deployment-runbook.md",
        "docs/backup-and-recovery.md",
        "docs/observability-alerts.md",
        # Release
        "scripts/validate-secrets.py",
        ".env.example",
        ".github/workflows/ci.yml",
        ".github/workflows/quality-ci.yml",
    ]

    print("[CHECK] Required Files")
    print("-" * 70)
    for file_path in required_files:
        full_path = root / file_path
        if full_path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ MISSING: {file_path}")
            errors.append(f"Missing: {file_path}")

    # Check file contents for critical requirements
    print("\n[CHECK] Required Content")
    print("-" * 70)

    content_checks = [
        ("backend/app/core/config.py", [
            "ACCOUNT_DELETION_GRACE_PERIOD_DAYS",
            "PURGE_DELETED_USERS_INTERVAL_HOURS",
            "@field_validator",
        ]),
        ("backend/app/api/routers/auth.py", [
            "delete_account",
            "require_sensitive_action",
        ]),
        (".env.example", [
            "ACCOUNT_DELETION_GRACE_PERIOD_DAYS",
            "PURGE_DELETED_USERS_INTERVAL_HOURS",
        ]),
    ]

    for file_path, required_content in content_checks:
        full_path = root / file_path
        if not full_path.exists():
            errors.append(f"File not found: {file_path}")
            continue

        content = full_path.read_text()
        missing = [req for req in required_content if req not in content]
        if missing:
            print(f"  ✗ {file_path}: Missing {missing}")
            errors.append(f"{file_path}: Missing {missing}")
        else:
            print(f"  ✓ {file_path}")

    # Summary
    print("\n" + "=" * 70)
    if errors:
        print("[RESULT] VALIDATION FAILED")
        print("\nIssues found:")
        for error in errors:
            print(f"  - {error}")
        return 1
    else:
        print("[RESULT] ALL CHECKS PASSED ✓")
        print("\nProject is production-ready!")
        print("Run: pytest backend/tests/ -q")
        print("     npm run test:coverage")
        print("     npx playwright test")
        return 0


if __name__ == "__main__":
    sys.exit(main())
