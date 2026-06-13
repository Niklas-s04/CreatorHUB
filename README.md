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

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- PostgreSQL
- Redis
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
- `CORS_ORIGINS`

Production also requires strong secret values and explicit cookie/domain settings.

### 3. Start the backend

```bash
cd backend
../.venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt
../.venv/Scripts/python.exe -m alembic upgrade head
../.venv/Scripts/python.exe -m app.main
```

The backend runs on `http://localhost:8000` by default.

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

The frontend runs on `http://localhost:3000` by default.

## Security and Operations

- Authentication uses secure cookies and CSRF protection.
- Audit logging is state-change only and redacts sensitive fields.
- External requests are validated centrally to reduce SSRF risk.
- Uploads are validated by file type, signature, size, and image dimensions.
- Production deployments should use explicit secrets, explicit origins, and restrictive host settings.

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
../.venv/Scripts/python.exe -m pytest --cov=app --cov-report=term-missing
../.venv/Scripts/python.exe -m pip_audit -r requirements.txt
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

## License

See `LICENSE`.
