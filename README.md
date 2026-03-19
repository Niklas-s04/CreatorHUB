# CreatorHUB

CreatorHUB is a full-stack platform for inventory operations, content planning, asset handling, and AI-assisted communication.

It combines product lifecycle workflows, media sourcing/review, content task tracking, and guarded email drafting in one self-hosted project.

## Features

- Product inventory with status transitions and transaction history
- Asset library with upload/web sources, review state, and primary asset selection
- Content workflow board (platform lanes + status columns + tasks)
- AI-assisted email drafting and refinement with risk checks and deal-intake support
- Knowledge base for reusable policy/brand context
- Image search pipeline (open sources + optional model-assisted scoring)
- Audit endpoints and asynchronous worker jobs
- Admin bootstrap + registration-request approval flow
- Web security middleware (CSRF, rate limiting, security headers, trusted hosts, request-size limit)

## Tech Stack

### Backend
- FastAPI
- SQLAlchemy + Alembic
- PostgreSQL
- Redis + RQ
- Pydantic Settings

### Frontend
- React + TypeScript
- Vite
- React Router

## Repository Structure

- `backend/` API, models, services, migrations, worker
- `frontend/` React UI
- `.env.example` environment template

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL
- Redis
- (Optional) Ollama for local LLM features

## Quick Start (Local Development)

### 1) Clone

```bash
git clone https://github.com/Nxklass/CreatorHUB
cd CreatorHUB
```

### 2) Configure environment

Copy `.env.example` to `.env` and set at least:

- `ENV=dev`
- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET`
- `CORS_ORIGINS` (e.g. `http://localhost:3000`)

For production, also ensure:

- strong `JWT_SECRET`
- `AUTH_COOKIE_SECURE=true`
- non-wildcard `CORS_ORIGINS`

### 3) Backend setup

```bash
cd backend
python -m pip install -r requirements.txt
alembic upgrade head
python -m app.main
```

Backend runs on `http://localhost:8000`.

### 4) Worker (optional but recommended)

Open a second terminal:

```bash
cd backend
python -m app.workers.run_worker
```

### 5) Frontend setup

```bash
cd frontend
npm ci
npm run dev
```

Frontend runs on `http://localhost:3000`.

## Docker

This repository includes Dockerfiles for backend and frontend:

- `backend/Dockerfile`
- `frontend/Dockerfile`

You can build/run these images directly or integrate them into your own compose stack.

### Reproducible builds

- Frontend reproducible installs use `npm ci` (including Docker builds).
- Keep lockfiles committed and in sync:
	- `frontend/package-lock.json`
	- backend uses pinned `requirements.txt` versions.
- Vite/Rollup are pinned and constrained via `package.json` + `overrides`.

### Optional native dependencies

- Backend image builds Python wheels in a builder stage (`build-essential` only in builder).
- Runtime image stays minimal and does not require compiler toolchain.

### Docker Compose (production-like local stack)

- Use `docker-compose.yml` to run frontend, backend, worker, PostgreSQL, and Redis with healthchecks.
- Start command:

```bash
docker compose up --build
```

- Readiness/Liveness:
	- Backend live: `/health/live`
	- Backend ready: `/health/ready`
	- Frontend live: `/healthz`

- Service startup ordering is protected with `depends_on` health conditions for DB/Redis/backend.

### Secrets handling

- Do not commit `.env` or runtime secrets.
- Docker build contexts exclude `.env*` via `.dockerignore`.
- Configure secrets via environment variables or secret manager in deployment.

### Startup configuration validation

- App startup validates critical configuration (URLs/schemes, cookie policy, required production values).
- Misconfigured or missing critical environment settings fail fast at startup.

## Authentication & Admin Bootstrap

- Auth is cookie-based (`creatorhub_access` + `creatorhub_refresh`, legacy `creatorhub_auth`) with CSRF protection (`creatorhub_csrf`).
- On first setup, bootstrap admin may require password initialization.
- Registration is request-based and can be approved/rejected in the admin area.

Relevant auth/admin endpoints are under `/api/auth/*`.

### Cookie & Session Security

- `AUTH_COOKIE_SECURE` is enabled by default and must stay enabled in production.
- `AUTH_COOKIE_SAMESITE` is explicitly validated (`lax|strict|none`), with enforced `Secure=true` for `none`.
- Auth cookies are `HttpOnly` where technically possible (access/refresh/legacy auth cookie).
- Cookie scope is minimized:
	- Access/auth cookies path: `/api`
	- Refresh cookie path: `/api/auth`
	- CSRF cookie path: `/` (required so the SPA can read and echo it)
	- Cookie domain is host-only by default (`AUTH_COOKIE_DOMAIN` unset)
- Cookie lifetimes are aligned with session state (idle + absolute expiration).

### CSRF Model

- CSRF is required for all unsafe methods (`POST`, `PUT`, `PATCH`, `DELETE`) under `/api` whenever an auth cookie is present.
- CSRF token is session-bound (cryptographically tied to JWT session id claim `sid`) and validated server-side.
- CSRF exception list is minimized to login only: `/api/auth/token`.
- Public endpoints without auth cookie do not require CSRF by design.

### Outbound Request Security (SSRF Protection)

Outbound URL fetch inventory (code paths):

- `app/services/storage.py` → `cache_download()` (image/file download)
- `app/services/image_fetcher.py` → Wikimedia/Openverse/OpenGraph/manufacturer page fetches
- `app/services/ai_gateway.py` → Ollama API call (trusted configured host)

All outbound HTTP is centralized in `app/services/outbound_http.py` and enforces:

- URL scheme validation (`https` by default, configurable exceptions)
- Blocklist for localhost, loopback, link-local, private RFC1918 and other non-routable ranges
- DNS pre-resolution and stability check (double resolve) before request
- Redirect handling with explicit limit and per-hop re-validation
- Port allowlist (`OUTBOUND_ALLOWED_PORTS`)
- Strict response-size cap (`OUTBOUND_MAX_RESPONSE_BYTES`)
- Global connect/read timeouts
- Controlled retry behavior for idempotent requests
- Optional host allowlist for sensitive targets
- Audit logging for outbound/download operations (status, errors, duration)

Operational hardening recommendations:

- Move external download workloads fully into isolated worker/service boundary over time.
- Enforce restrictive egress firewall/network policies at runtime environment level.

### Upload & Asset Security

- Allowed file types are purpose-bound (`image`, `pdf`) and enforced server-side.
- MIME type from client is not trusted; magic-byte/signature validation is required.
- File extension must match allowed lists per type.
- Size limits are type-specific (`UPLOAD_MAX_IMAGE_BYTES`, `UPLOAD_MAX_PDF_BYTES`).
- Image uploads enforce max dimensions and max total pixels (`UPLOAD_MAX_IMAGE_WIDTH/HEIGHT`, `UPLOAD_MAX_IMAGE_PIXELS`).
- PDF uploads use dedicated validation (`%PDF-` signature + `%%EOF` marker).
- Archives/compressed formats are blocked by signature (zip/rar/gzip/7z).
- Unsafe/unneeded formats are denied by default.
- Filenames are sanitized server-side and storage keys are generated independently from original names.
- Uploads are not auto-approved; review states include `quarantine`, `pending_review`, `needs_review`, `approved`, `rejected`.
- Review queue endpoint: `GET /api/assets/review-queue` (admin/editor).
- Thumbnail generation is restricted to validated/allowed image formats.
- Metadata extraction only runs for validated files.
- Optional malware scanning hook exists (`ENABLE_OPTIONAL_MALWARE_SCAN`) for AV integration.
- Asset delivery hardening includes strict content-type, explicit content-disposition, cache-control, size cap (`ASSET_MAX_DELIVERY_BYTES`), and permission checks for non-approved assets.

## Security Notes

The backend adds middleware for:

- Security headers (`CSP`, `X-Frame-Options`, etc.)
- Request body size limit
- Rate limiting (global + auth-sensitive)
- CSRF checks for unsafe API methods
- Trusted host validation

Header hardening includes:

- `Content-Security-Policy` with `frame-ancestors 'none'`, `object-src 'none'`, and restricted source directives
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Permissions-Policy` with disabled sensitive browser APIs
- `Strict-Transport-Security` automatically set in production for TLS deployments

Security behavior is environment-aware and stricter in production.

## Useful Commands

### Frontend

```bash
cd frontend
npm run dev
npm run build
npm run preview
npm run test
npm run test:coverage
npm run lint
npm run typecheck
npm run format:check
npm run e2e:list
npm run e2e
```

### Backend Quality Checks

```bash
cd backend
python -m pip install -r requirements.txt -r requirements-dev.txt
ruff check app tests
ruff format --check app tests
mypy --config-file mypy.ini
pytest --cov=app --cov-report=term-missing
pip-audit -r requirements.txt
```

## Qualität & CI

- GitHub Actions Workflow: `.github/workflows/quality-ci.yml`
- Enthält:
	- Backend: install, lint, format-check, typecheck, tests + coverage, dependency security audit
	- Frontend: install, lint, format-check, typecheck, tests + coverage, build, dependency security audit
	- Migrations-Check: `alembic upgrade head` + `alembic current`

### Quality Gates (Mindestanforderungen)

- Backend Coverage: mindestens **55%** (`backend/.coveragerc`)
- Frontend Coverage: mindestens **30% lines/functions/statements**, **20% branches** (`frontend/vite.config.ts`)
- Lint/Format/Typecheck müssen in beiden Stacks erfolgreich sein

## Release & Rollback

Der standardisierte Release- und Rollback-Ablauf ist dokumentiert in:

- `docs/release-and-rollback.md`

### End-to-End Tests (Playwright)

- E2E base URL defaults to `http://127.0.0.1:3000` (`E2E_BASE_URL` override).
- API is expected at `http://127.0.0.1:8000/api` (configured in frontend via `VITE_API_BASE`).
- Credentials/env overrides for test login:
	- `E2E_ADMIN_USER` (default: `admin`)
	- `E2E_ADMIN_PASSWORD`
	- `E2E_BOOTSTRAP_TOKEN` (optional, used only if admin first-time setup is required)

Install browser binaries once:

```bash
cd frontend
npx playwright install
```

### Backend

```bash
cd backend
alembic upgrade head
python -m app.main
python -m app.workers.run_worker
```

## API Overview

Main route groups:

- `/api/v1/auth`
- `/api/v1/products`
- `/api/v1/assets`
- `/api/v1/content`
- `/api/v1/email`
- `/api/v1/images`
- `/api/v1/knowledge`
- `/api/v1/deals`
- `/api/v1/audit`
- Legacy aliases `/api/*` are still available and marked as deprecated in OpenAPI.

Health route:

- `/health`
- `/health/live`
- `/health/ready`

Status & domain rules:

- `docs/domain-status-rules.md`

API design rules:

- `docs/api-design.md`

Standard list/query contract:

- Query: `limit`, `offset`, `sort_by`, `sort_order`
- Response envelope: `{ meta: { limit, offset, total, sort_by, sort_order }, items: [...] }`

Standard error response contract:

- `{ code, message, status, details }`

## Troubleshooting

- **`JWT_SECRET must be set...`**
	- Set `ENV=dev` for local dev or configure a secure `JWT_SECRET`.
- **TypeScript server command in terminal fails**
	- `TypeScript: Restart TS Server` is a VS Code command, not a shell command.
- **Auth/CSRF errors on write requests**
	- Ensure frontend and backend origins/cookies are configured correctly.

## License

See `LICENSE`.