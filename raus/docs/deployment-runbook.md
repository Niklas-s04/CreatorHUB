# Deployment Runbook

This document describes the intended release flow for CreatorHUB.

## Pre-Deployment Checks

- CI is green.
- Tests are up to date.
- Security validation scripts have passed.
- Database migrations have been reviewed.
- Backups are available.
- Monitoring is ready.

## Deployment Flow

1. Build backend and frontend artifacts.
2. Deploy a green environment alongside the current production environment.
3. Run migrations on the green database.
4. Execute smoke tests against the green environment.
5. Switch traffic from blue to green.
6. Monitor error rate, latency, and authentication health for at least 15 minutes.

## Rollback Criteria

Rollback if any of the following occur:

- failed smoke tests
- spikes in authentication failures
- migration failure
- elevated 5xx error rate
- signs of data corruption

## Rollback Flow

1. Stop the new deployment.
2. Switch traffic back to the last stable environment.
3. Run the matching Alembic downgrade only if the schema change is reversible and coordinated.
4. Re-run smoke tests and health checks.

## Notes

- Releases should remain reversible.
- Production secrets must be supplied by the deployment environment, not baked into images.
# Deployment Runbook

This runbook describes the intended release process for CreatorHUB.

## Pre-deployment checks

- CI is green
- tests are up to date
- security validation scripts passed
- migrations were reviewed
- backups are available
- monitoring is ready
- production release validator is prepared: `python backend/scripts/validate_prod_release.py`

## Deployment flow

1. Build backend and frontend artifacts.
2. Deploy a green environment alongside the current production environment.
3. Run database migrations against the green database.
4. Execute smoke tests against green.
5. Switch traffic from blue to green.
6. Watch error rate, latency, and auth health for at least 15 minutes.

Recommended automated validation sequence:

1. `python backend/scripts/validate_prod_release.py --base-url "$PROD_BASE_URL" --bootstrap-token "$PROD_BOOTSTRAP_TOKEN" --database-url "$PROD_DATABASE_URL" --primary-storage-dir "$PROD_ASSET_PRIMARY_DIR" --replica-storage-dir "$PROD_ASSET_REPLICA_DIR" --monitoring-report-path "$PROD_MONITORING_REPORT_PATH" --release-notes-path "$PROD_RELEASE_NOTES_PATH"`
2. Review the generated monitoring report and release notes.
3. Proceed only if all checks pass.

## Rollback criteria

Rollback if any of the following occur:

- failed smoke tests
- authentication failure spikes
- migration failure
- elevated 5xx error rate
- unexpected data corruption

## Rollback flow

1. Stop the new deployment.
2. Switch traffic back to the previous stable environment.
3. Run the matching Alembic downgrade if the schema changed.
4. Verify login, search, upload, and admin flows.

## Notes

- Releases should stay reversible.
- Production secrets must be injected by the deployment environment, not baked into images.