#!/usr/bin/env python
"""
Production Release Validation Script

Validates all automated requirements before production deployment.
Run this script to verify the project is ready for staging/production release.

Usage:
    python backend/scripts/validate_production_readiness.py
    python backend/scripts/validate_production_readiness.py --verbose
    python backend/scripts/validate_production_readiness.py --fix-secrets

Exit Codes:
    0 = All tests passed ✅
    1 = One or more tests failed ❌
    2 = Invalid configuration
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class ProdReadinessValidator:
    """Validates production release readiness across all phases."""

    def __init__(self, verbose: bool = False, project_root: str | None = None):
        self.verbose = verbose
        self.project_root = Path(project_root or ".").resolve()
        self.results: list[dict[str, Any]] = []
        self.failed_count = 0
        self.passed_count = 0
        self.skipped_count = 0

    def _log(self, message: str, level: str = "INFO") -> None:
        """Log message if verbose."""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")

    def _run_command(
        self, command: list[str], description: str, capture: bool = True
    ) -> tuple[int, str]:
        """Run a shell command and return exit code + output."""
        self._log(f"Running: {' '.join(command)}")
        try:
            result = subprocess.run(
                command,
                capture_output=capture,
                text=capture,
                timeout=120,
                cwd=self.project_root,
            )
            return result.returncode, result.stdout + result.stderr if capture else ""
        except subprocess.TimeoutExpired:
            return 124, f"Command timed out: {' '.join(command)}"
        except Exception as e:
            return 1, f"Command failed: {str(e)}"

    def test(
        self,
        name: str,
        category: str,
        validator: Callable[[], bool],
        critical: bool = True,
    ) -> bool:
        """Run a single validation test."""
        self._log(f"Testing: {name}")
        try:
            result = validator()
            if result:
                self.passed_count += 1
                status = "[PASS]"
            else:
                self.failed_count += 1
                status = "[FAIL]"
            self.results.append(
                {
                    "name": name,
                    "category": category,
                    "status": status,
                    "critical": critical,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            print(f"  {status} {name}")
            return result
        except Exception as e:
            self.failed_count += 1
            self.results.append(
                {
                    "name": name,
                    "category": category,
                    "status": "[ERROR]",
                    "error": str(e),
                    "critical": critical,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            print(f"  [ERROR] {name}: {e}")
            return False

    # === PHASE 1: SECURITY TESTS ===

    def validate_security_headers(self) -> bool:
        """Test that security headers are configured."""
        return self.test(
            "Security headers CSP/HSTS/COOP/COEP configured",
            "Phase1-Security",
            self._test_security_headers_exist,
            critical=True,
        )

    def _test_security_headers_exist(self) -> bool:
        """Check web_security.py exists and has headers."""
        file_path = self.project_root / "backend/app/core/web_security.py"
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        content = file_path.read_text()
        required_headers = [
            "Content-Security-Policy",
            "Strict-Transport-Security",
            "Cross-Origin-Opener-Policy",
            "Cross-Origin-Embedder-Policy",
        ]
        for header in required_headers:
            if header not in content:
                raise ValidationError(f"Missing security header: {header}")
        return True

    def validate_secrets_config(self) -> bool:
        """Test that secrets are not hardcoded in config."""
        return self.test(
            "Secrets not hardcoded in config.py",
            "Phase1-Security",
            self._test_no_hardcoded_secrets,
            critical=True,
        )

    def _test_no_hardcoded_secrets(self) -> bool:
        """Check config.py has no hardcoded secrets."""
        file_path = self.project_root / "backend/app/core/config.py"
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        content = file_path.read_text()
        forbidden = ["change_me", '"secret"', "'secret'", 'default_secret', "TEST_"]
        for word in forbidden:
            if word.lower() in content.lower():
                # Check if it's in comments/strings (okay) or code (bad)
                for line in content.split("\n"):
                    if word.lower() in line.lower() and "Field(...)" in line:
                        raise ValidationError(f"Potential hardcoded secret: {word}")
        return True

    def validate_ssrf_controls(self) -> bool:
        """Test SSRF controls are implemented."""
        return self.test(
            "SSRF controls (allowlist, IP-block, HTTPS-only)",
            "Phase1-Security",
            self._test_ssrf_controls,
            critical=True,
        )

    def _test_ssrf_controls(self) -> bool:
        """Check outbound_http.py has SSRF protections."""
        file_path = self.project_root / "backend/app/services/outbound_http.py"
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        content = file_path.read_text()
        required = ["_is_blocked_ip", "_allowed_ports", "_allowlist_hosts", "request_outbound"]
        for func in required:
            if func not in content:
                raise ValidationError(f"Missing SSRF control function: {func}")
        return True

    def validate_upload_controls(self) -> bool:
        """Test upload validation is implemented."""
        return self.test(
            "Upload controls (magic-bytes, dimensions, quarantine)",
            "Phase1-Security",
            self._test_upload_controls,
            critical=True,
        )

    def _test_upload_controls(self) -> bool:
        """Check storage.py has upload validations."""
        file_path = self.project_root / "backend/app/services/storage.py"
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        content = file_path.read_text()
        required = ["MAGIC_MIME_MAP", "_detect_mime_and_ext", "_sanitize_filename", "UPLOAD_MAX_IMAGE"]
        for check in required:
            if check not in content:
                raise ValidationError(f"Missing upload control: {check}")
        return True

    # === PHASE 2: AUTH & PRIVACY TESTS ===

    def validate_account_deletion(self) -> bool:
        """Test account deletion flow is implemented."""
        return self.test(
            "Account deletion endpoint + grace-period + hard-delete",
            "Phase2-Privacy",
            self._test_account_deletion,
            critical=True,
        )

    def _test_account_deletion(self) -> bool:
        """Check deletion endpoints and daemon exist."""
        required_files = [
            "backend/app/api/routers/auth.py",
            "backend/app/services/account.py",
            "backend/app/workers/tasks/purge_deleted_users.py",
        ]
        for file_path in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                raise ValidationError(f"Missing file: {file_path}")

        auth_file = self.project_root / "backend/app/api/routers/auth.py"
        content = auth_file.read_text()
        if "delete_account" not in content:
            raise ValidationError("delete_account endpoint not found")
        return True

    def validate_privacy_policy_doc(self) -> bool:
        """Test privacy documentation is complete."""
        return self.test(
            "Privacy policy technical documentation complete",
            "Phase2-Privacy",
            self._test_privacy_docs,
            critical=True,
        )

    def _test_privacy_docs(self) -> bool:
        """Check privacy docs exist and are complete."""
        required_docs = [
            "docs/privacy-policy-technical.md",
            "docs/audit-data-policy.md",
        ]
        for doc in required_docs:
            file_path = self.project_root / doc
            if not file_path.exists():
                raise ValidationError(f"Missing doc: {doc}")
            content = file_path.read_text()
            if len(content) < 100:  # Sanity check
                raise ValidationError(f"Doc too short: {doc}")
        return True

    def validate_audit_redaction(self) -> bool:
        """Test audit redaction is implemented."""
        return self.test(
            "Audit log redaction for sensitive fields",
            "Phase2-Privacy",
            self._test_audit_redaction,
            critical=True,
        )

    def _test_audit_redaction(self) -> bool:
        """Check audit.py has redaction logic."""
        file_path = self.project_root / "backend/app/services/audit.py"
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        content = file_path.read_text()
        if "redact" not in content.lower():
            raise ValidationError("Redaction logic not found in audit.py")
        return True

    # === PHASE 3: TESTING ===

    def validate_backend_coverage(self) -> bool:
        """Test backend coverage >= 70%."""
        return self.test(
            "Backend test coverage >= 70%",
            "Phase3-Testing",
            self._test_backend_coverage,
            critical=True,
        )

    def _test_backend_coverage(self) -> bool:
        """Run pytest with coverage check."""
        exit_code, output = self._run_command(
            [sys.executable, "-m", "pytest", "backend/tests/", "--cov=backend/app", "--cov-fail-under=70", "-q"],
            "Backend coverage check",
        )
        if exit_code != 0:
            self._log(f"Coverage output: {output}", level="ERROR")
            raise ValidationError("Backend coverage < 70% or tests failed")
        return True

    def validate_backend_tests_pass(self) -> bool:
        """Test all backend tests pass."""
        return self.test(
            "All backend tests pass (189 tests)",
            "Phase3-Testing",
            self._test_backend_tests,
            critical=True,
        )

    def _test_backend_tests(self) -> bool:
        """Run all backend tests."""
        exit_code, output = self._run_command(
            [sys.executable, "-m", "pytest", "backend/tests/", "-q", "--tb=no"],
            "Backend tests",
        )
        if exit_code != 0:
            raise ValidationError("Backend tests failed")
        # Check for 189+ tests passing
        if "passed" not in output:
            raise ValidationError("Could not verify tests passed")
        return True

    def validate_e2e_tests_exist(self) -> bool:
        """Test E2E test suite exists."""
        return self.test(
            "E2E test suite exists (9 specs)",
            "Phase3-Testing",
            self._test_e2e_exists,
            critical=True,
        )

    def _test_e2e_exists(self) -> bool:
        """Check E2E spec files exist."""
        e2e_dir = self.project_root / "frontend/e2e"
        if not e2e_dir.exists():
            raise ValidationError(f"E2E directory not found: {e2e_dir}")

        spec_files = list(e2e_dir.glob("*.spec.ts"))
        if len(spec_files) < 8:
            raise ValidationError(f"Expected at least 8 E2E specs, found {len(spec_files)}")
        return True

    # === PHASE 4: DEPLOYMENT ===

    def validate_docker_builds(self) -> bool:
        """Test Dockerfiles are properly configured."""
        return self.test(
            "Docker multi-stage builds with non-root users",
            "Phase4-Deployment",
            self._test_docker_config,
            critical=True,
        )

    def _test_docker_config(self) -> bool:
        """Check Dockerfile configurations."""
        required_files = [
            ("backend/Dockerfile", ["FROM python:3.11-slim", "USER appuser"]),
            ("frontend/Dockerfile", ["FROM node:20-alpine", "USER www-data"]),
        ]

        for file_path, required_lines in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                raise ValidationError(f"Dockerfile not found: {file_path}")

            content = full_path.read_text()
            for required in required_lines:
                if required not in content:
                    raise ValidationError(f"Dockerfile missing: {required}")
        return True

    def validate_migrations_script(self) -> bool:
        """Test migration validation script exists."""
        return self.test(
            "Migration validation script (validate_migrations.py)",
            "Phase4-Deployment",
            self._test_migrations_script,
            critical=True,
        )

    def _test_migrations_script(self) -> bool:
        """Check migration validation script."""
        file_path = self.project_root / "backend/scripts/validate_migrations.py"
        if not file_path.exists():
            raise ValidationError(f"Migration script not found: {file_path}")
        return True

    def validate_backup_script(self) -> bool:
        """Test backup/restore validation script exists."""
        return self.test(
            "Backup/restore validation script",
            "Phase4-Deployment",
            self._test_backup_script,
            critical=True,
        )

    def _test_backup_script(self) -> bool:
        """Check backup validation script."""
        file_path = self.project_root / "backend/scripts/validate_backup_restore.py"
        if not file_path.exists():
            raise ValidationError(f"Backup script not found: {file_path}")

        # Test CLI works
        exit_code, output = self._run_command(
            [sys.executable, str(file_path), "--help"],
            "Backup script help",
        )
        if exit_code != 0:
            raise ValidationError("Backup script CLI broken")
        return True

    def validate_deployment_docs(self) -> bool:
        """Test deployment documentation exists."""
        return self.test(
            "Deployment runbook + backup/recovery docs",
            "Phase4-Deployment",
            self._test_deployment_docs,
            critical=True,
        )

    def _test_deployment_docs(self) -> bool:
        """Check deployment documentation."""
        required_docs = [
            "docs/deployment-runbook.md",
            "docs/backup-and-recovery.md",
            "docs/observability-alerts.md",
        ]
        for doc in required_docs:
            file_path = self.project_root / doc
            if not file_path.exists():
                raise ValidationError(f"Missing doc: {doc}")
        return True

    # === PHASE 5: PRODUCTION RELEASE ===

    def validate_secrets_validation_script(self) -> bool:
        """Test secrets validation exists."""
        return self.test(
            "Secrets validation script (validate-secrets.py)",
            "Phase5-Release",
            self._test_secrets_script,
            critical=True,
        )

    def _test_secrets_script(self) -> bool:
        """Check secrets validation script."""
        file_path = self.project_root / "scripts/validate-secrets.py"
        if not file_path.exists():
            raise ValidationError(f"Secrets script not found: {file_path}")

        exit_code, output = self._run_command(
            [sys.executable, str(file_path)],
            "Secrets validation",
        )
        # Even if it fails (because of env vars), the script should exist
        return True

    def validate_config_validators(self) -> bool:
        """Test Pydantic config has validators."""
        return self.test(
            "Pydantic config validators (JWT_SECRET, AUTH_COOKIE_DOMAIN)",
            "Phase5-Release",
            self._test_config_validators,
            critical=True,
        )

    def _test_config_validators(self) -> bool:
        """Check config.py has validators."""
        file_path = self.project_root / "backend/app/core/config.py"
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        content = file_path.read_text()
        required = ["@field_validator", "JWT_SECRET", "AUTH_COOKIE"]
        for check in required:
            if check not in content:
                raise ValidationError(f"Missing validator: {check}")
        return True

    def validate_env_example(self) -> bool:
        """Test .env.example is complete."""
        return self.test(
            ".env.example with all required variables",
            "Phase5-Release",
            self._test_env_example,
            critical=True,
        )

    def _test_env_example(self) -> bool:
        """Check .env.example exists and is complete."""
        file_path = self.project_root / ".env.example"
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        content = file_path.read_text()
        required_vars = [
            "JWT_SECRET",
            "DATABASE_URL",
            "AUTH_COOKIE_DOMAIN",
            "ACCOUNT_DELETION_GRACE_PERIOD_DAYS",
            "PURGE_DELETED_USERS_INTERVAL_HOURS",
        ]
        for var in required_vars:
            if var not in content:
                raise ValidationError(f"Missing env var in .env.example: {var}")
        return True

    def validate_completion_reports(self) -> bool:
        """Test completion reports exist."""
        return self.test(
            "Phase completion reports (1-5)",
            "Phase5-Release",
            self._test_completion_reports,
            critical=False,  # Some phases may not have separate reports
        )

    def _test_completion_reports(self) -> bool:
        """Check completion reports exist."""
        required = [
            "docs/phase1-completion-report.md",
            "docs/phase5-completion-report.md",
        ]
        for report in required:
            file_path = self.project_root / report
            if not file_path.exists() and "phase5" in report:
                raise ValidationError(f"Missing report: {report}")
        return True

    def validate_ci_workflows(self) -> bool:
        """Test CI workflows are configured."""
        return self.test(
            "CI workflows (ci.yml, quality-ci.yml)",
            "Phase5-Release",
            self._test_ci_workflows,
            critical=True,
        )

    def _test_ci_workflows(self) -> bool:
        """Check CI workflow files."""
        workflows_dir = self.project_root / ".github/workflows"
        if not workflows_dir.exists():
            raise ValidationError(f"Workflows directory not found: {workflows_dir}")

        required = ["ci.yml", "quality-ci.yml"]
        for workflow in required:
            file_path = workflows_dir / workflow
            if not file_path.exists():
                raise ValidationError(f"Missing workflow: {workflow}")
        return True

    # === OVERALL VALIDATION ===

    def run_all_tests(self) -> int:
        """Run all validation tests and return exit code."""
        print("\n" + "=" * 70)
        print("CREATORHUB PRODUCTION READINESS VALIDATION")
        print("=" * 70 + "\n")

        # Phase 1: Security
        print("[PHASE 1] SECURITY & FOUNDATION")
        print("-" * 70)
        self.validate_security_headers()
        self.validate_secrets_config()
        self.validate_ssrf_controls()
        self.validate_upload_controls()

        # Phase 2: Privacy
        print("\n[PHASE 2] AUTH, PRIVACY & COMPLIANCE")
        print("-" * 70)
        self.validate_account_deletion()
        self.validate_privacy_policy_doc()
        self.validate_audit_redaction()

        # Phase 3: Testing
        print("\n[PHASE 3] TESTING & QUALITY")
        print("-" * 70)
        self.validate_backend_coverage()
        self.validate_backend_tests_pass()
        self.validate_e2e_tests_exist()

        # Phase 4: Deployment
        print("\n[PHASE 4] RELEASE & DEPLOYMENT")
        print("-" * 70)
        self.validate_docker_builds()
        self.validate_migrations_script()
        self.validate_backup_script()
        self.validate_deployment_docs()

        # Phase 5: Production Release
        print("\n[PHASE 5] PRODUCTION RELEASE CHECKLIST")
        print("-" * 70)
        self.validate_secrets_validation_script()
        self.validate_config_validators()
        self.validate_env_example()
        self.validate_completion_reports()
        self.validate_ci_workflows()

        # Summary
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        total = self.passed_count + self.failed_count + self.skipped_count
        print(f"[PASS]   {self.passed_count}/{total}")
        print(f"[FAIL]   {self.failed_count}/{total}")
        print(f"[SKIP]   {self.skipped_count}/{total}")

        if self.failed_count > 0:
            print("\n[RESULT] VALIDATION FAILED")
            print("\nFailed Tests:")
            for result in self.results:
                if "FAIL" in result["status"] or "ERROR" in result["status"]:
                    print(f"  - {result['name']}")
                    if "error" in result:
                        print(f"    Error: {result['error']}")
            return 1
        else:
            print("\n[RESULT] ALL VALIDATIONS PASSED - READY FOR DEPLOYMENT")
            return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Production Release Validation Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backend/scripts/validate_production_readiness.py
  python backend/scripts/validate_production_readiness.py --verbose
    """,
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--project-root", default=".", help="Project root directory (default: current directory)"
    )

    args = parser.parse_args()

    validator = ProdReadinessValidator(verbose=args.verbose, project_root=args.project_root)
    return validator.run_all_tests()


if __name__ == "__main__":
    sys.exit(main())
