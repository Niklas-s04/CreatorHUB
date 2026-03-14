# CreatorHUB

Local-first platform for product inventory, content workflows, AI-assisted email drafting, and image sourcing.

CreatorHUB is a full-stack web application built to support small creator, reseller, and operations-heavy workflows in one place. The project combines product management, asset handling, content task tracking, knowledge-based AI assistance, and asynchronous background jobs in a single self-hosted setup.

## Why I built this

Many small workflows are spread across spreadsheets, chat tools, draft emails, and shared folders. CreatorHUB is an attempt to bring those operational steps together into one system:

- manage products and their status
- organize assets and media
- track content tasks
- draft emails with local AI support
- keep reusable policy and brand knowledge in the app
- run background processing with a worker queue

The focus of this project is not just CRUD, but practical workflow design across backend, frontend, storage, and async processing.

## Core features

- Product management with detail views and status tracking
- Asset management for uploaded media and related records
- Content workflow with task-oriented views
- AI-assisted email drafting with guardrails
- Knowledge base for reusable brand/policy context
- Image sourcing from open sources
- Audit-related endpoints and operational background jobs
- Self-hosted architecture using Docker, Postgres, Redis, and Ollama

## Stack

### Backend
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis + RQ worker
- Pydantic

### Frontend
- React
- TypeScript
- Vite
- React Router

### Infrastructure
- Docker
- Docker Compose
- Ollama for local LLM usage

## Architecture overview

- `frontend/` contains the React application
- `backend/` contains the FastAPI API, business logic, models, and worker code
- `postgres` stores application data
- `redis` powers background jobs and queue processing
- `ollama` provides local model inference for AI-related features
- persistent volumes are used for uploads, cache, exports, and database storage

## Main modules

- **Products**: product records, value/status information, detail pages
- **Assets**: file and asset-related operations
- **Content**: workflow tasks for operational and publishing processes
- **Email**: AI-assisted draft generation with policy constraints
- **Knowledge**: stored brand voice and policy documents
- **Images**: image search/fetch pipeline using open sources
- **Deals / Audit**: additional workflow and traceability endpoints

## Run locally

### Prerequisites

- Docker
- Docker Compose
- enough local resources to run Postgres, Redis, frontend, backend, and Ollama

### 1. Clone the repository

```bash
git clone https://github.com/Nxklass/CreatorHUB
