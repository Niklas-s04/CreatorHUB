# CreatorHUB

CreatorHUB is a full-stack platform for inventory operations, content planning, asset review, and controlled AI-assisted communication.

The project combines product lifecycle workflows, media review, content task tracking, audit logging, and guarded automation in a self-hosted stack.

## What It Provides

- Product inventory with workflow and transaction history
- Asset storage with upload, review, and primary-selection support
- Content planning with structured workflow states
- AI-assisted email drafting with risk checks
- Knowledge base support for policy and brand context
- Open-source image search with optional local AI assistance
- Audit endpoints and background worker jobs
- Admin bootstrap and registration review flows
- Web security middleware for CSRF, rate limiting, security headers, trusted hosts, and request-size limits

## Technology Stack

### Backend

- FastAPI
- SQLAlchemy and Alembic
- PostgreSQL
- Redis and RQ
- Pydantic Settings

### Frontend

- React
- TypeScript
- Vite
- React Router

## Repository Layout

- `backend/` API, models, services, migrations, and workers
- `frontend/` React UI
- `docs/api-design.md` API conventions and response formats
- `docs/design-system.md` UI tokens and component standards
- `docs/domain-status-rules.md` workflow rules and allowed transitions
- `docs/technical-documentation.md` architecture, configuration, operations, and recovery notes
- `docs/audit-data-policy.md` audit logging scope and redaction rules
- `docs/privacy-policy-technical.md` privacy, retention, and deletion handling
- `.env.example` environment template
- `.env.test.example` local Docker smoke-test environment template
- `scripts/validate-secrets.sh` pre-deploy secret validation

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- PostgreSQL
- Redis
- Bash for release/CI helper scripts
- Optional: Ollama for local AI features

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Nxklass/CreatorHUB
cd CreatorHUB
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and set the required values for your environment.

At minimum, local development needs:

- `ENV=dev`
- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET`
- `POSTGRES_PASSWORD`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `CORS_ORIGINS`

Production also requires strong secret values and explicit cookie/domain settings.
Do not commit `.env`, `.env.test`, generated secrets, database dumps, uploads, or coverage artifacts.

### 3. Start the backend

```bash
cd backend
../.venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt
../.venv/Scripts/python.exe -m alembic upgrade head
../.venv/Scripts/python.exe -m app.main
```

The backend runs on `http://localhost:31800` by default.

### 4. Start the worker

In a second terminal:

```bash
cd backend
../.venv/Scripts/python.exe -m app.workers.run_worker
```

### 5. Start the frontend

```bash
cd frontend
npm ci
npm run dev
```

The frontend runs on `http://localhost:31080` by default.

## Docker Smoke Test

For a local release smoke test, create a disposable `.env.test` from the checked-in template:

```bash
cp .env.test.example .env.test
cp .env.test .env
bash scripts/validate-secrets.sh
docker-compose up --build
```

Then verify:

- Backend readiness: `http://localhost:31800/health/ready`
- Frontend health: `http://localhost:31080/healthz`
- Browser DevTools cookies include Secure, HttpOnly where applicable, and SameSite=Strict.
- Browser DevTools console has no unexpected CSP violations.

The `.env.test.example` values are non-production examples only.

## Security and Operations

- Authentication uses secure cookies and CSRF protection.
- Audit logging is state-change only and redacts sensitive fields.
- External requests are validated centrally to reduce SSRF risk.
- Uploads are validated by file type, signature, size, and image dimensions.
- Account deletion immediately deactivates the account, revokes active sessions, and schedules hard deletion after the configured grace period.
- Deleted-user purge anonymizes audit logs and records compliance audit events.
- Production deployments should use explicit secrets, explicit origins, and restrictive host settings.
- Run `bash scripts/validate-secrets.sh` before deployment. It fails on missing or weak required secrets.

## Common Commands

### Frontend

```bash
cd frontend
npm run dev
npm run build
npm run test
npm run test:coverage
npm run lint
npm run typecheck
npm run format:check
npm run e2e
```

### Backend

```bash
cd backend
../.venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt
../.venv/Scripts/python.exe -m ruff check app tests
../.venv/Scripts/python.exe -m ruff format --check app tests
../.venv/Scripts/python.exe -m mypy --config-file mypy.ini
../.venv/Scripts/python.exe -m pytest tests --cov --cov-fail-under=70
../.venv/Scripts/python.exe -m pip_audit -r requirements.txt
```

### Release Verification

```bash
bash scripts/validate-secrets.sh
cd backend
../.venv/Scripts/python.exe -m ruff check app tests
../.venv/Scripts/python.exe -m ruff format --check app tests
../.venv/Scripts/python.exe -m pytest tests --cov --cov-fail-under=70
```

The Phase 1 security foundation release was verified with the backend suite passing at 70%+ coverage.

## API Overview

Main route groups:

- `/api/v1/auth`
- `DELETE /api/v1/user/account`
- `/api/v1/products`
- `/api/v1/assets`
- `/api/v1/content`
- `/api/v1/email`
- `/api/v1/images`
- `/api/v1/knowledge`
- `/api/v1/deals`
- `/api/v1/audit`

Health routes:

- `/health`
- `/health/live`
- `/health/ready`

API conventions:

- [API Design Guidelines](docs/api-design.md)
- [Domain Status Rules](docs/domain-status-rules.md)

## Troubleshooting

- If startup fails, check `DATABASE_URL`, `REDIS_URL`, and `JWT_SECRET` first.
- If authentication fails, verify cookie domain, secure cookie settings, and CSRF handling.
- If uploads fail, verify the file signature, allowed extension, and size limits.
- If API calls fail from the frontend, verify the API base URL and CORS settings.
- If the frontend is opened through a LAN IP such as `http://192.168.x.x:31080`, run a
  LAN/dev profile: set `ENV=dev` or `ENV=test`, `AUTH_COOKIE_SECURE=false`, leave
  `AUTH_COOKIE_DOMAIN` empty, add the exact browser origin to `CORS_ORIGINS`, and add
  the LAN host/IP to `TRUSTED_HOSTS`. The frontend container must not force
  `upgrade-insecure-requests` in this HTTP profile, otherwise browser asset requests are
  upgraded to HTTPS on the HTTP-only Nginx port and the app can render as a blank page.
- If you need another frontend port, set `FRONTEND_PORT`, for example
  `FRONTEND_PORT=32080 docker compose up --build`. Use the same port in `CORS_ORIGINS`.
- If Nginx logs `connect() failed ... upstream: "http://[...]:31800"`, rebuild the
  frontend image so the Docker DNS resolver config with IPv6 disabled is active.
- For production, use an HTTPS domain, `AUTH_COOKIE_SECURE=true`, an explicit
  `AUTH_COOKIE_DOMAIN`, and production-only `CORS_ORIGINS`/`TRUSTED_HOSTS` values.
  Terminate TLS, redirect HTTP to HTTPS, and set HSTS at the external reverse proxy or
  load balancer in front of the frontend container.

## License

See `LICENSE`.
