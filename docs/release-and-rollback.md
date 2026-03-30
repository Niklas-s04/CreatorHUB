# Release- und Rollback-Prozess

## Ziel
Ein reproduzierbarer Release-Ablauf mit klaren Qualitäts-Gates und dokumentiertem Rollback-Verfahren.

## Release-Prozess
1. **Branch vorbereiten**
   - Feature-Branch fertigstellen.
   - Lokale Checks ausführen:
     - Backend: `ruff check`, `ruff format --check`, `mypy`, `pytest --cov=app`
     - Frontend: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run test:coverage`, `npm run build`
2. **Pull Request erstellen**
   - CI muss grün sein (Quality CI Workflow).
   - Migrations-Check (`alembic upgrade head`) muss erfolgreich sein.
3. **Version taggen**
   - SemVer-Tag setzen, z. B. `v1.4.0`.
4. **Deployment**
   - Deployment auf Zielumgebung auslösen.
   - Health-Endpunkte prüfen: `/health/live`, `/health/ready`, Frontend `/healthz`.
5. **Post-Release Check**
   - Login/Logout, Produktfluss, Asset-Flow, E-Mail-Drafting, Admin-Flow smoke-testen.

## Rollback-Prozess
1. **Auslöser**
   - Fehlerhafte Kernfunktion (Auth, Datenverlust-Risiko, kritische 5xx-Rate, Sicherheitsproblem).
2. **Code-Rollback**
   - Auf letzten stabilen Tag zurückrollen (z. B. `v1.3.2`).
3. **Datenbank-Rollback**
   - Nur bei explizit reversiblen Migrationen durchführen.
   - Standard: hotfix forward statt blindes Downgrade.
   - Falls nötig: `alembic downgrade <previous_revision>` in abgestimmtem Wartungsfenster.
4. **Verifikation**
   - Smoke-Tests und Healthchecks erneut ausführen.
5. **Nachbereitung**
   - Incident-Notiz mit Root Cause und Maßnahmen erfassen.

## Qualitäts-Gates (Mindestanforderungen)
- Backend Lint/Format/Typecheck erfolgreich.
- Frontend Lint/Format/Typecheck erfolgreich.
- Backend Coverage mindestens **55%**.
- Frontend Coverage mindestens **30% lines/functions/statements**, **20% branches**.
- Security Checks:
  - `pip-audit` ohne ungeklärte Findings.
  - `npm audit --audit-level=critical` ohne kritische Findings.
- Alembic Migrations-Check (`upgrade head`) erfolgreich.

## Logging-Retention und Löschfristen
- Applikationslogs: **30 Tage** (`LOG_RETENTION_DAYS`, Standardwert).
- Security-Event-Logs: **90 Tage** (`SECURITY_LOG_RETENTION_DAYS`, Standardwert).
- Umsetzung: tägliche Rotation, automatische Löschung älterer Log-Dateien nach Ablauf der Frist.
- Für produktive Umgebungen mit Compliance-Anforderungen sind abweichende Fristen als explizite Konfigurationsentscheidung zu dokumentieren.
