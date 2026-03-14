# Creator Suite (TrueNAS Local)

Lokales Web-System für Inventar, Content-Workflows, KI‑E-Mail‑Assistenz und Bild‑Finder – gemäß Konzept.

## Quickstart (Docker Compose)

1) Voraussetzungen: Docker + Docker Compose (auf TrueNAS SCALE z.B. über Apps/Compose), optional gemountete Datasets.
2) Kopiere `.env.example` nach `.env` und passe Werte an.
3) Start:

```bash
docker compose up -d --build
```

4) Öffne:
- Frontend: http://localhost:3000
- Backend (Swagger): http://localhost:8000/docs

## TrueNAS Hinweise (Datasets)

Empfohlen (SCALE): Lege Datasets an und mappe sie in Compose:

- `./data/db` → `/mnt/pool/appdata/creator-suite/db`
- `./data/uploads` → `/mnt/pool/appdata/creator-suite/uploads`
- `./data/cache` → `/mnt/pool/appdata/creator-suite/cache`
- `./data/exports` → `/mnt/pool/appdata/creator-suite/exports`

## KI (Ollama)

- `OLLAMA_URL=http://ollama:11434`
- Text‑Modell (E‑Mail): `OLLAMA_TEXT_MODEL=llama3.1:8b` (Beispiel)
- Vision‑Modell (Bilder): `OLLAMA_VISION_MODEL=llava:latest` (optional, für echte Bildklassifikation)

## Sicherheit / Guardrails

- Keine automatische E‑Mail‑Sicherung/Sendung (MVP): Draft + Flags + manuelle Freigabe.
- Prompt‑Versionierung + Validierung + Redaction optional.
- Web‑Assets speichern immer Quelle + Lizenz + Attribution.

## Ordner

- `backend/` FastAPI + Postgres + Alembic + Redis RQ Worker
- `frontend/` React (Vite)
- `infra/` Traefik + Backup‑Skripte

