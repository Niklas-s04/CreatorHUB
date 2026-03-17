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
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`.

## Docker

This repository includes Dockerfiles for backend and frontend:

- `backend/Dockerfile`
- `frontend/Dockerfile`

You can build/run these images directly or integrate them into your own compose stack.

## Authentication & Admin Bootstrap

- Auth is cookie-based (`creatorhub_auth`) with CSRF protection (`creatorhub_csrf`).
- On first setup, bootstrap admin may require password initialization.
- Registration is request-based and can be approved/rejected in the admin area.

Relevant auth/admin endpoints are under `/api/auth/*`.

## Security Notes

The backend adds middleware for:

- Security headers (`CSP`, `X-Frame-Options`, etc.)
- Request body size limit
- Rate limiting (global + auth-sensitive)
- CSRF checks for unsafe API methods
- Trusted host validation

Security behavior is environment-aware and stricter in production.

## Useful Commands

### Frontend

```bash
cd frontend
npm run dev
npm run build
npm run preview
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

- `/api/auth`
- `/api/products`
- `/api/assets`
- `/api/content`
- `/api/email`
- `/api/images`
- `/api/knowledge`
- `/api/deals`
- `/api/audit`

Health route:

- `/health`

## Troubleshooting

- **`JWT_SECRET must be set...`**
	- Set `ENV=dev` for local dev or configure a secure `JWT_SECRET`.
- **TypeScript server command in terminal fails**
	- `TypeScript: Restart TS Server` is a VS Code command, not a shell command.
- **Auth/CSRF errors on write requests**
	- Ensure frontend and backend origins/cookies are configured correctly.

## License

See `LICENSE`.