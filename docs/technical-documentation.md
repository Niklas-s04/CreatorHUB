# Technical Documentation

## 1. Architecture Overview

CreatorHUB is a full-stack application with clear boundaries between browser, backend, database, cache, worker, and external integrations.

- The backend is a FastAPI application with versioned routes under `/api/v1/...`.
- The frontend is a React and Vite single-page application.
- PostgreSQL is the primary source of truth for persistent data.
- Redis supports rate limiting, background coordination, and worker queues.
- Background jobs run outside the web process.
- External integrations are isolated, especially Ollama for local AI features and open-source media search providers.

Main entry points:

- [Backend app entry](../backend/app/main.py)
- [Backend configuration](../backend/app/core/config.py)
- [Docker Compose stack](../docker-compose.yml)
- [Frontend scripts](../frontend/package.json)

### Trust Boundaries

- The browser must not contain secrets or privileged business logic.
- The backend owns authentication, authorization, session validity, and sensitive administrative actions.
- State-changing requests are protected with CSRF and audit logging.
- Outbound network requests are validated centrally to reduce SSRF risk.

## 2. Module Boundaries

The repository is split into functional and technical layers.

### Backend

- `backend/app/api/` - HTTP routes, dependencies, and error handling
- `backend/app/core/` - configuration, security, logging, observability, and web protection
- `backend/app/db/` - engine and session primitives
- `backend/app/models/` - persistence models
- `backend/app/schemas/` - request and response schemas
- `backend/app/services/` - domain logic and integrations
- `backend/app/workers/` - background jobs and queue processing
- `backend/app/seed.py` - bootstrap and initial setup

### Frontend

- `frontend/src/api.ts` - browser API bindings
- `frontend/src/features/` - feature-specific UI modules
- `frontend/src/pages/` - routed page containers
- `frontend/src/shared/` - reusable UI and helper code
- `frontend/src/components/` - cross-cutting components

### Working Rule

- UI sends data and interactions.
- Services enforce and transform business rules.
- Models represent persistence.
- Schemas define API contracts.
- Core modules handle technical cross-cutting concerns.

### Project Hub

Projects are the parent planning layer for a creative initiative or video production. A project
stores its category, owner, status, priority, schedule, progress, creative brief, requirements,
internal notes, and preview/approval state. Content items and products are linked through
many-to-many relations, so a record can be reused across projects without duplicating domain data.

The project API supports:

- custom category CRUD under `/api/v1/projects/categories`
- project list, detail, filtering, create, update, and delete
- linking and unlinking existing content or products
- creating new content or products directly inside a project
- reciprocal `project_id` filters on product and content list endpoints
- audit logging and role-based `project.read`, `project.manage`, and `project.delete` permissions

## 3. Environment Variables

The most important environment variables are grouped by purpose in `.env.example` and in `backend/app/core/config.py`.

### Application and Infrastructure

- `PROJECT_NAME`
- `ENV`
- `DATABASE_URL`
- `REDIS_URL`
- `UPLOADS_DIR`
- `CACHE_DIR`
- `EXPORTS_DIR`

### Authentication and Sessions

- `JWT_SECRET`
- `JWT_ACCESS_EXPIRE_MINUTES`
- `JWT_REFRESH_EXPIRE_MINUTES`
- `BOOTSTRAP_ADMIN_USERNAME`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `BOOTSTRAP_INSTALL_TOKEN`
- `AUTH_COOKIE_DOMAIN`
- `AUTH_COOKIE_SECURE`
- `AUTH_COOKIE_SAMESITE`
- `CSRF_COOKIE_NAME`
- `SECURITY_SENSITIVE_ACTION_REQUIRE_STEP_UP_MFA`
- `ACCOUNT_DELETION_GRACE_PERIOD_DAYS`

### Networking and Outbound Requests

- `OLLAMA_URL`
- `OLLAMA_TEXT_MODEL`
- `OLLAMA_VISION_MODEL`
- `IMAGE_HUNT_DEFAULT_SOURCES`
- `OPENVERSE_API_BASE`
- `OUTBOUND_CONNECT_TIMEOUT_SECONDS`
- `OUTBOUND_READ_TIMEOUT_SECONDS`
- `OUTBOUND_MAX_RESPONSE_BYTES`
- `OUTBOUND_MAX_REDIRECTS`
- `OUTBOUND_ALLOWED_PORTS`
- `OUTBOUND_REQUIRE_HTTPS`
- `OUTBOUND_BLOCK_PRIVATE_RANGES`
- `OUTBOUND_ALLOWLIST_HOSTS`

### Uploads and Assets

- `UPLOAD_ALLOWED_IMAGE_EXTENSIONS`
- `UPLOAD_ALLOWED_PDF_EXTENSIONS`
- `UPLOAD_MAX_IMAGE_BYTES`
- `UPLOAD_MAX_PDF_BYTES`
- `UPLOAD_MAX_IMAGE_WIDTH`
- `UPLOAD_MAX_IMAGE_HEIGHT`
- `UPLOAD_MAX_IMAGE_PIXELS`
- `ASSET_MAX_DELIVERY_BYTES`
- `ENABLE_OPTIONAL_MALWARE_SCAN`

### Security and Rate Limiting

- `CORS_ORIGINS`
- `TRUSTED_HOSTS`
- `MAX_REQUEST_BODY_BYTES`
- `RATE_LIMIT_ENABLED`
- `RATE_LIMIT_WINDOW_SECONDS`
- `RATE_LIMIT_GLOBAL`
- `RATE_LIMIT_AUTH`
- `SECURITY_HSTS_SECONDS`

### Logging and Observability

- `LOG_LEVEL`
- `UVICORN_LOG_LEVEL`
- `UVICORN_ACCESS_LOG_LEVEL`
- `LOG_FORMAT`
- `LOG_TO_STDOUT`
- `LOG_TO_FILE`
- `LOG_DIR`
- `LOG_FILE_NAME`
- `LOG_RETENTION_DAYS`
- `SECURITY_LOG_LEVEL`
- `SECURITY_LOG_TO_SEPARATE_FILE`
- `SECURITY_LOG_FILE_NAME`
- `SECURITY_LOG_RETENTION_DAYS`
- `OBSERVABILITY_METRICS_ENABLED`
- `OBSERVABILITY_METRICS_PATH`
- `OBSERVABILITY_MONITOR_ENABLED`
- `OBSERVABILITY_MONITOR_INTERVAL_SECONDS`
- `ALERT_DB_FAILURE_CONSECUTIVE`
- `ALERT_REDIS_FAILURE_CONSECUTIVE`
- `ALERT_WORKER_FAILURE_CONSECUTIVE`
- `ALERT_QUEUE_LENGTH_WARN`
- `ALERT_QUEUE_LENGTH_CRITICAL`
- `ALERT_FAILED_JOBS_CRITICAL`
- `OTEL_ENABLED`
- `OTEL_SERVICE_NAME`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_EXPORTER_OTLP_INSECURE`
- `OTEL_SAMPLE_RATIO`

## 4. Build and Runbook

### Local Development

Backend:

```bash
cd backend
python -m pip install -r requirements.txt
alembic upgrade head
python -m app.main
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

### Quality Checks

Backend:

```bash
cd backend
ruff check app tests
ruff format --check app tests
mypy --config-file mypy.ini
pytest --cov=app --cov-report=term-missing
pip-audit -r requirements.txt
```

Frontend:

```bash
cd frontend
npm run lint
npm run format:check
npm run typecheck
npm run test
npm run build
```

### Docker-Based Start

```bash
docker compose up --build
```

The Docker stack runs PostgreSQL, Redis, backend, worker, and frontend together.
Before backend and worker start, the one-shot `migrate` service upgrades the database to the
current Alembic head. Named volumes persist uploads and exports and share the application cache
between backend and worker.

### Shutdown Behavior

- The backend closes background jobs and Redis connections cleanly during shutdown.
- The worker is a separate process and must be considered during maintenance or rollouts.

## 5. Troubleshooting

### Backend Does Not Start

Check:

- `DATABASE_URL` and `REDIS_URL` are valid and reachable
- `JWT_SECRET` is set and strong enough
- `AUTH_COOKIE_SECURE` is enabled in production
- `BOOTSTRAP_INSTALL_TOKEN` and `BOOTSTRAP_ADMIN_PASSWORD` are set where required
- `CORS_ORIGINS` does not use a wildcard in production

### Login or Session Behavior Looks Wrong

Check:

- Cookies are accepted for the current domain
- SameSite and Secure settings match the environment
- The CSRF cookie is being sent
- The account is not locked
- The session has not expired by idle or absolute timeout

### Frontend Loads, but API Requests Fail

Check:

- The frontend and backend use the correct API base path
- Reverse proxy rules forward `/api` to the backend
- CORS includes the frontend origin
- The backend is running on the expected host and port

### Uploads or Assets Are Rejected

Check:

- The file type and extension are allowed
- The file size stays within the configured limit
- Image dimensions and pixel count are within bounds
- The upload directory is writable
- The asset is not blocked by a review state

### Worker or Queue Issues

Check:

- Redis is reachable
- The worker is running
- `/health/metrics` and `/health/background-jobs` show valid queue data
- Failed jobs are visible in the worker log

## 6. Security Assumptions

- The backend is authoritative for all security decisions.
- The browser must not know secrets or privileged controls.
- Cookies are HTTP-only where possible and scoped to the API path.
- CSRF protection is required for unsafe methods when auth cookies are present.
- Sensitive actions require server-side checks and are audited.
- Outbound requests must be protected against private networks, unsupported ports, and excessive redirects.
- Logs must be redacted and must not contain sensitive values.
- Production deployments should use restrictive CORS, cookie, and host settings.
- External AI and download services must be treated as untrusted dependencies.

## 7. Deployment Steps

Recommended order:

1. Run local quality checks.
2. Bring the database schema to the target state with Alembic.
3. Build and deploy the backend image.
4. Roll out the worker at the same release level.
5. Build and deploy the frontend.
6. Check health endpoints.
7. Run smoke tests for login, registration review, product flows, asset flows, and admin views.

### Docker References

- Backend image: [backend/Dockerfile](../backend/Dockerfile)
- Frontend image: [frontend/Dockerfile](../frontend/Dockerfile)
- Compose stack: [docker-compose.yml](../docker-compose.yml)

### Rollout Notes

- Test new migrations before release.
- Use staged rollouts when a critical workflow is affected.
- Monitor error rates, authentication failures, and queue health after deployment.

## 8. Backup and Restore

### Assumptions

- PostgreSQL is the primary database.
- Uploads, exports, cache, and log files are stored outside the database and must be backed up separately.
- Backup orchestration is handled at infrastructure level, not inside the application code.

### Backup

```bash
pg_dump --format=custom --file=creatorhub-db.dump "$DATABASE_URL"
```

Also back up:

- the upload directory
- the export directory
- the cache only if a full restore requires it
- configuration and secrets through a secure channel

### Restore

```bash
createdb creatorhub_restore
pg_restore --clean --if-exists --dbname=creatorhub_restore creatorhub-db.dump
```

After the restore:

1. Start the application against the restored database.
2. Verify Alembic state and migrate only if needed.
3. Restore file-based assets if necessary.
4. Run health checks and a business-level smoke test.

### Restore Validation

- Verify login and session handling
- Verify a registration review flow
- Verify a product or asset workflow
- Observe worker queue and health endpoints

## 9. Related Documents

- [API Design Guidelines](./api-design.md)
- [Domain Status Rules](./domain-status-rules.md)
- [Design System](./design-system.md)

## 10. Operational Roles

### Product and Business Ownership

- Product owners define priorities, goals, and acceptance criteria.
- Domain owners define business rules for products, content, assets, communication, and registration.
- Reviewers approve, reject, or escalate requests within their permissions.
