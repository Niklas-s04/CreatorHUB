# Release and Rollback Process

## Goal

Provide a repeatable release path with clear quality gates and a documented rollback procedure.

## Release Process

1. Finish the feature branch.
2. Run local checks:
   - Backend: `ruff check`, `ruff format --check`, `mypy`, `pytest --cov=app`
   - Frontend: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run test:coverage`, `npm run build`
3. Create the pull request and wait for CI.
4. Tag the release with a semantic version such as `v1.4.0`.
5. Deploy to the target environment.
6. Verify health endpoints and smoke-test the main product flows.

## Rollback Process

1. Determine the trigger: critical auth failure, data-loss risk, severe 5xx spike, or security issue.
2. Roll back to the last stable tag if the code release must be reverted.
3. Use database downgrade only when the migration is known to be reversible and the rollback is coordinated.
4. Verify health checks and smoke tests after rollback.
5. Record the incident and follow-up actions.

## Quality Gates

- Backend lint, format, typecheck, and tests must pass.
- Frontend lint, format, typecheck, tests, and build must pass.
- Backend coverage must be at least 70%.
- Frontend coverage must be at least 70% for lines, functions, and statements, with at least 60% branches.
- Security checks must be clean.
- Alembic migration upgrade to head must succeed.

## Logging Retention

- Application logs: 30 days.
- Security event logs: 90 days.
- Daily rotation and expiry cleanup are required when file logging is enabled.
