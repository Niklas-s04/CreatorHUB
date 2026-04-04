# Technische Dokumentation

## 1. Architekturuebersicht

CreatorHUB ist eine Full-Stack-Anwendung mit klar getrennter Verantwortung zwischen Browser, Backend, Datenbank, Cache/Queue und externen Diensten.

- Das Backend ist eine FastAPI-Anwendung mit versionierten API-Routen unter `/api/v1/...` und temporaer weiter verfuegbaren Legacy-Routen unter `/api/...`.
- Das Frontend ist eine React/Vite-SPA, die fachliche Seiten ueber `frontend/src/pages` und Feature-Module unter `frontend/src/features` zusammensetzt.
- PostgreSQL ist die fachliche Source of Truth fuer persistente Daten.
- Redis wird fuer Rate-Limiting, Background-Jobs und runtime-nahe Koordination verwendet.
- Hintergrundjobs laufen getrennt vom Webprozess im Worker-Prozess.
- Externe Dienste sind bewusst gekapselt, vor allem Ollama fuer KI-Funktionen und externe Download-/Bildquellen fuer Medien- und Suchfunktionen.

Wichtige Einstiegspunkte:

- [Backend-App-Start](../backend/app/main.py)
- [Backend-Konfiguration](../backend/app/core/config.py)
- [Docker Compose Stack](../docker-compose.yml)
- [Frontend-Skripte](../frontend/package.json)

### Trust Boundaries

- Browser und SPA duerfen keine geheimen Werte oder privilegierte Logik enthalten.
- Das Backend entscheidet serverseitig ueber Authentifizierung, Autorisierung, Session-Gueltigkeit und sensible Admin-Aktionen.
- Schreibende Operationen mit Sicherheitsbezug sind an CSRF, Session-Pruefung und Audit-Logging gebunden.
- Externe Netzwerkanfragen werden zentral kontrolliert und gegen SSRF- und Redirect-Risiken abgesichert.

## 2. Modulgrenzen

Die Repo-Struktur ist bewusst in fachliche und technische Schichten getrennt.

### Backend

- `backend/app/api/`  
  HTTP-Schicht mit Routern, Dependencies und Fehlerbehandlung. Hier liegen keine Fachregeln, die auch ohne HTTP gebraucht werden.
- `backend/app/core/`  
  Infrastruktur und Querschnitt: Konfiguration, Security, Logging, Observability, Web-Schutz.
- `backend/app/db/`  
  Engine-, Session- und Datenbank-Basis.
- `backend/app/models/`  
  SQLAlchemy-Modelle und Persistenzstrukturen.
- `backend/app/schemas/`  
  Pydantic-Modelle fuer Request- und Response-Vertraege.
- `backend/app/services/`  
  Fachlogik und Integrationslogik, z. B. Domain-Regeln, CSV-Import, Storage, Audit, Auto-Archive.
- `backend/app/workers/`  
  Separater Ausfuehrungsbereich fuer Queue- und Background-Jobs.
- `backend/app/seed.py`  
  Bootstrap-/Initialisierungslogik fuer Erstsetup.

### Frontend

- `frontend/src/api.ts`  
  Zentrale API-Bindings fuer den Browser.
- `frontend/src/features/`  
  Fachliche UI-Features mit eigener Logik und eigener Komposition.
- `frontend/src/pages/`  
  Seitencontainer und Routing-Ziele.
- `frontend/src/shared/`  
  Wiederverwendbare UI-, API- und Helper-Bausteine.
- `frontend/src/components/`  
  Querschnittskomponenten.
- `frontend/src/entities/`  
  Domainnahe Frontend-Modelle.
- `frontend/src/hooks/`  
  Wiederverwendbare React-Hooks.

### Praktische Regel

- UI schickt Daten und Interaktionen.
- Services pruefen und transformieren Fachregeln.
- Modelle bilden Persistenz ab.
- Schemas definieren API-Vertraege.
- Core kapselt technische Querschnittsthemen.

## 3. Umgebungsvariablen

Die Default-Werte liegen in [backend/app/core/config.py](../backend/app/core/config.py). Die wichtigsten Variablen sind hier nach Zweck gruppiert.

### Basis und Datenhaltung

- `PROJECT_NAME`  
  Anzeigename der Anwendung.
- `ENV`  
  Laufzeitmodus, z. B. `prod` oder `dev`.
- `DATABASE_URL`  
  PostgreSQL-Verbindungszeichenkette.
- `REDIS_URL`  
  Redis-Verbindungszeichenkette.
- `UPLOADS_DIR`  
  Speicherort fuer Uploads.
- `CACHE_DIR`  
  Speicherort fuer Cache-Daten.
- `EXPORTS_DIR`  
  Speicherort fuer Exporte.

### Authentifizierung und Sessions

- `JWT_SECRET`  
  Signierschluessel fuer JWTs.
- `JWT_ACCESS_EXPIRE_MINUTES`  
  Laufzeit des Access-Tokens.
- `JWT_REFRESH_EXPIRE_MINUTES`  
  Laufzeit des Refresh-Tokens.
- `AUTH_COOKIE_NAME`  
  Legacy-Auth-Cookie.
- `AUTH_ACCESS_COOKIE_NAME`  
  Access-Cookie.
- `AUTH_REFRESH_COOKIE_NAME`  
  Refresh-Cookie.
- `AUTH_COOKIE_SECURE`  
  Cookie nur ueber sichere Verbindungen.
- `AUTH_COOKIE_SAMESITE`  
  SameSite-Policy fuer Cookies.
- `AUTH_COOKIE_DOMAIN`  
  Optionale Cookie-Domain.
- `AUTH_ACCESS_COOKIE_MAX_AGE_SECONDS`  
  Max-Age des Access-Cookies.
- `AUTH_REFRESH_COOKIE_MAX_AGE_SECONDS`  
  Max-Age des Refresh-Cookies.
- `AUTH_COOKIE_MAX_AGE_SECONDS`  
  Max-Age des Legacy-Cookies.
- `CSRF_COOKIE_NAME`  
  Name des CSRF-Cookies.
- `SESSION_IDLE_TIMEOUT_MINUTES`  
  Inaktivitaets-Timeout.
- `SESSION_ABSOLUTE_TIMEOUT_MINUTES`  
  Absolute Session-Laufzeit.
- `AUTH_MAX_FAILED_ATTEMPTS`  
  Maximal erlaubte Fehlversuche vor Sperre.
- `AUTH_LOCK_MINUTES`  
  Sperrdauer nach zu vielen Fehlversuchen.
- `AUTH_SUSPICIOUS_FAILED_THRESHOLD`  
  Schwellwert fuer auffaellige Fehlversuche.
- `AUTH_SUSPICIOUS_WINDOW_MINUTES`  
  Zeitfenster fuer Suspicious-Login-Erkennung.
- `MFA_TOTP_ISSUER`  
  Issuer-Name fuer TOTP.
- `MFA_RECOVERY_CODES_COUNT`  
  Anzahl Wiederherstellungscodes.
- `SECURITY_SENSITIVE_ACTION_CONFIRMATION_REQUIRED`  
  Ob sensible Aktionen zusaetzliche Bestaetigung brauchen.
- `SECURITY_SENSITIVE_ACTION_CONFIRMATION_HEADER`  
  Header fuer die Bestaetigung.
- `SECURITY_SENSITIVE_ACTION_CONFIRMATION_VALUE`  
  Erwarteter Bestaetigungswert.
- `SECURITY_SENSITIVE_ACTION_REQUIRE_STEP_UP_MFA`  
  Ob Step-up-MFA fuer sensible Aktionen verlangt wird.
- `PASSWORD_RESET_TOKEN_TTL_MINUTES`  
  Gueltigkeit von Passwort-Reset-Tokens.

### Netzwerkrichtlinien und Outbound-Requests

- `OLLAMA_URL`  
  Ziel fuer KI-Anfragen.
- `OLLAMA_TEXT_MODEL`  
  Textmodell fuer KI-Funktionen.
- `OLLAMA_VISION_MODEL`  
  Visionmodell fuer Bildfunktionen.
- `IMAGE_HUNT_DEFAULT_SOURCES`  
  Standardquellen fuer Bildsuche.
- `OPENVERSE_API_BASE`  
  Basis-URL fuer Openverse.
- `OUTBOUND_CONNECT_TIMEOUT_SECONDS`  
  Verbindungs-Timeout fuer externe Requests.
- `OUTBOUND_READ_TIMEOUT_SECONDS`  
  Lese-Timeout fuer externe Requests.
- `OUTBOUND_MAX_RESPONSE_BYTES`  
  Maximale Response-Groesse.
- `OUTBOUND_MAX_REDIRECTS`  
  Maximal erlaubte Redirects.
- `OUTBOUND_RETRIES`  
  Retry-Anzahl fuer geeignete Requests.
- `OUTBOUND_ALLOWED_PORTS`  
  Erlaubte Zielports.
- `OUTBOUND_REQUIRE_HTTPS`  
  Ob HTTPS erzwungen wird.
- `OUTBOUND_ALLOWLIST_HOSTS`  
  Host-Allowlist fuer allgemeine externe Ziele.
- `OUTBOUND_SENSITIVE_ALLOWLIST_HOSTS`  
  Zusaetzliche Allowlist fuer sensible Ziele.
- `OUTBOUND_BLOCK_PRIVATE_RANGES`  
  Blockiert interne/private Zielnetze.

### Uploads und Assets

- `UPLOAD_ALLOWED_IMAGE_EXTENSIONS`  
  Erlaubte Bild-Endungen.
- `UPLOAD_ALLOWED_PDF_EXTENSIONS`  
  Erlaubte PDF-Endungen.
- `UPLOAD_MAX_IMAGE_BYTES`  
  Bild-Upload-Limit.
- `UPLOAD_MAX_PDF_BYTES`  
  PDF-Upload-Limit.
- `UPLOAD_MAX_IMAGE_WIDTH`  
  Maximale Bildbreite.
- `UPLOAD_MAX_IMAGE_HEIGHT`  
  Maximale Bildhoehe.
- `UPLOAD_MAX_IMAGE_PIXELS`  
  Maximale Pixelzahl fuer Bilder.
- `ASSET_MAX_DELIVERY_BYTES`  
  Maximale Auslieferungsmenge fuer Assets.
- `ENABLE_OPTIONAL_MALWARE_SCAN`  
  Optionale AV-Integration.

### Security, CORS und Rate-Limits

- `CORS_ORIGINS`  
  Erlaubte Frontend-Origin-Liste.
- `TRUSTED_HOSTS`  
  Gueltige Host-Header.
- `MAX_REQUEST_BODY_BYTES`  
  Maximal erlaubte Request-Groesse.
- `RATE_LIMIT_ENABLED`  
  Aktiviert Rate-Limiting.
- `RATE_LIMIT_WINDOW_SECONDS`  
  Zeitfenster des Rate-Limits.
- `RATE_LIMIT_GLOBAL`  
  Globales Limit.
- `RATE_LIMIT_AUTH`  
  Strengeres Limit fuer Auth-Endpunkte.
- `RATE_LIMIT_REDIS_PREFIX`  
  Redis-Prefix fuer Limiter-Schluessel.
- `TRUST_PROXY_HEADERS`  
  Ob Proxy-Header vertrauenswuerdig sind.
- `SECURITY_HSTS_SECONDS`  
  HSTS-Dauer.

### Bootstrap und Initialisierung

- `BOOTSTRAP_ADMIN_USERNAME`  
  Username fuer den Bootstrap-Admin.
- `BOOTSTRAP_ADMIN_PASSWORD`  
  Passwort fuer den Bootstrap-Admin.
- `BOOTSTRAP_INSTALL_TOKEN`  
  Installations-Token fuer Erstsetup.

### Automatisierung und Lifecycle

- `AUTO_ARCHIVE_ENABLED`  
  Aktiviert das automatische Archivieren.
- `AUTO_ARCHIVE_INTERVAL_MINUTES`  
  Zyklus des Auto-Archive-Tasks.
- `AUTO_ARCHIVE_SOLD_AFTER_DAYS`  
  Frist fuer verkaufte Produkte vor Archivierung.

### Logging und Observability

- `LOG_LEVEL`  
  Grund-Log-Level.
- `UVICORN_LOG_LEVEL`  
  Log-Level fuer Uvicorn.
- `UVICORN_ACCESS_LOG_LEVEL`  
  Access-Log-Level fuer Uvicorn.
- `LOG_FORMAT`  
  `json` oder `plain`.
- `LOG_TO_STDOUT`  
  Logs auf Standardausgabe.
- `LOG_TO_FILE`  
  Datei-Logging aktivieren.
- `LOG_DIR`  
  Zielverzeichnis fuer Logdateien.
- `LOG_FILE_NAME`  
  Name der Hauptlogdatei.
- `LOG_RETENTION_DAYS`  
  Aufbewahrung der Hauptlogs.
- `SECURITY_LOG_LEVEL`  
  Log-Level fuer Security-Logs.
- `SECURITY_LOG_TO_SEPARATE_FILE`  
  Security-Logs in separater Datei.
- `SECURITY_LOG_FILE_NAME`  
  Name der Security-Logdatei.
- `SECURITY_LOG_RETENTION_DAYS`  
  Aufbewahrung der Security-Logs.
- `SECURITY_LOG_PROPAGATE_TO_ROOT`  
  Ob Security-Logs zum Root-Logger durchgereicht werden.
- `OBSERVABILITY_METRICS_ENABLED`  
  Schaltet Metriken frei.
- `OBSERVABILITY_METRICS_PATH`  
  Metrik-Endpunkt.
- `OBSERVABILITY_MONITOR_ENABLED`  
  Aktiviert Health-Monitoring.
- `OBSERVABILITY_MONITOR_INTERVAL_SECONDS`  
  Intervall des Monitors.
- `ALERT_DB_FAILURE_CONSECUTIVE`  
  Alarmgrenze fuer Datenbankfehler.
- `ALERT_REDIS_FAILURE_CONSECUTIVE`  
  Alarmgrenze fuer Redisfehler.
- `ALERT_WORKER_FAILURE_CONSECUTIVE`  
  Alarmgrenze fuer Workerfehler.
- `ALERT_QUEUE_LENGTH_WARN`  
  Warnschwelle fuer Queue-Laenge.
- `ALERT_QUEUE_LENGTH_CRITICAL`  
  Kritische Schwelle fuer Queue-Laenge.
- `ALERT_FAILED_JOBS_CRITICAL`  
  Kritische Schwelle fuer fehlgeschlagene Jobs.
- `OTEL_ENABLED`  
  Aktiviert OpenTelemetry.
- `OTEL_SERVICE_NAME`  
  Service-Name fuer Traces.
- `OTEL_EXPORTER_OTLP_ENDPOINT`  
  OTLP-Ziel fuer Traces.
- `OTEL_EXPORTER_OTLP_INSECURE`  
  Insecure-Transport fuer OTLP.
- `OTEL_SAMPLE_RATIO`  
  Sampling-Rate fuer Traces.

## 4. Build- und Runbook

### Lokale Entwicklung

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

### Qualitaetspruefungen

Backend:

```bash
cd backend
python -m ruff check .
python -m ruff format --check .
python -m mypy .
python -m pytest
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

### Docker-basierter Start

```bash
docker compose up --build
```

Dieser Stack startet PostgreSQL, Redis, Backend, Worker und Frontend gemeinsam. Die Health-Checks sind unter anderem:

- Backend live: `/health/live`
- Backend ready: `/health/ready`
- Frontend health: `/healthz`

### Ruhezustand und Shutdown

- Der Backend-Prozess beendet Hintergrundjobs und Redis-Verbindungen sauber beim Shutdown.
- Der Worker laeuft als eigener Prozess und muss bei Release- oder Wartungsfenstern mitberuecksichtigt werden.

## 5. Fehlerbehebungsleitfaeden

### 5.1 Backend startet nicht

Pruefen:

- `DATABASE_URL` und `REDIS_URL` sind gueltig und erreichbar.
- In Production ist `JWT_SECRET` nicht auf dem Defaultwert.
- In Production ist `AUTH_COOKIE_SECURE=true` gesetzt.
- `BOOTSTRAP_INSTALL_TOKEN` und `BOOTSTRAP_ADMIN_PASSWORD` sind produktiv gesetzt.
- `CORS_ORIGINS` enthaelt keine Wildcard in Production.

### 5.2 Login oder Sessions verhalten sich unerwartet

Pruefen:

- Browser akzeptiert Cookies fuer die aktuelle Domain.
- SameSite- und Secure-Policy passen zur Zielumgebung.
- CSRF-Cookie wird mitgeschickt.
- Benutzerkonto ist nicht gesperrt.
- Die Session ist nicht idle oder absolut abgelaufen.

### 5.3 Frontend laedt, aber API-Aufrufe schlagen fehl

Pruefen:

- Frontend und Backend zeigen auf denselben API-Pfad, lokal meist `/api`.
- Reverse Proxy leitet `/api` korrekt an das Backend weiter.
- CORS erlaubt die Frontend-Origin.
- Das Backend laeuft wirklich auf der erwarteten Host-/Port-Kombination.

### 5.4 Uploads oder Assets werden abgelehnt

Pruefen:

- Dateityp und Endung sind erlaubt.
- Datei liegt unter dem Groessenlimit.
- Bilddimensionen und Pixelgrenzen sind eingehalten.
- Das Upload- bzw. Asset-Verzeichnis ist beschreibbar.
- Die Datei ist nicht in einen gesperrten Review-Status gefallen.

### 5.5 Worker oder Queue wirken festgefahren

Pruefen:

- Redis ist erreichbar.
- Der Worker-Prozess laeuft.
- Der Health-Endpunkt `/health/metrics` bzw. `/health/background-jobs` zeigt valide Queue-Daten.
- Fehlgeschlagene Jobs werden im Worker-Log sichtbar.

### 5.6 Sinnvolle Log-Quellen

- Backend-Logs im Container-Output oder in `LOG_DIR`
- Security-Logs in der separaten Security-Logdatei, falls Datei-Logging aktiviert ist
- Frontend-Build-Fehler ueber `npm run build` und Browser-Konsole

## 6. Security-Annahmen

- Das Backend ist fuer alle Sicherheitsentscheidungen autoritativ.
- Der Browser darf keine Secrets kennen und keine privilegierten Admin-Schalter enthalten.
- Cookies sind HTTP-only, soweit technisch moeglich, und an den API-Pfad gebunden.
- CSRF ist fuer unsichere Methoden mit Auth-Cookie verpflichtend.
- Sensible Aktionen benoetigen serverseitige Pruefung, optional Step-up-MFA und werden auditiert.
- Outbound-Requests sind gegen private Netze, unerlaubte Ports und zu viele Redirects abgesichert.
- Logs werden defensiv maskiert und duerfen keine sensiblen Werte enthalten.
- Produktionsumgebungen sollen auf restriktiven CORS-, Cookie- und Host-Einstellungen laufen.
- Externe KI- und Download-Dienste sind nicht vertrauensvoll und muessen wie Fremdsysteme behandelt werden.

## 7. Deployment-Schritte

### Empfohlene Reihenfolge

1. Lokale Qualitaetspruefungen laufen lassen.
2. Datenbankschema mit Alembic auf den Zielstand bringen.
3. Backend-Image bauen und deployen.
4. Worker mit demselben Release-Stand ausrollen.
5. Frontend bauen und ausrollen.
6. Health-Checks pruefen.
7. Smoke-Tests fuer Login, Registrierungsfreigabe, Produktfluss, Asset-Flow und Admin-Ansichten ausfuehren.

### Docker-Referenz

- Backend-Image basiert auf [backend/Dockerfile](../backend/Dockerfile)
- Frontend-Image basiert auf [frontend/Dockerfile](../frontend/Dockerfile)
- Produktionsnaeherer Compose-Stack liegt in [docker-compose.yml](../docker-compose.yml)

### Rollout-Hinweise

- Neue Migrationen vor dem Rollout testen.
- Wenn ein kritischer Workflow betroffen ist, lieber gestaffelt ausrollen.
- Post-Deploy-Monitoring soll Fehlerquoten, Auth-Fehler und Queue-Zustand abdecken.

## 8. Backup- und Restore-Prozesse

### Annahmen

- PostgreSQL enthaelt die fachliche Primärdatenbank.
- Uploads, Exporte, Cache und Logdateien liegen ausserhalb des Datenbankschemas und muessen separat gesichert werden.
- Es gibt kein eingebautes Backup-Subsystem im Application-Code; die Sicherung erfolgt auf Infrastrukturebene.

### Backup

Empfohlen ist eine saubere Trennung zwischen Datenbank, Dateien und Konfiguration:

```bash
pg_dump --format=custom --file=creatorhub-db.dump "$DATABASE_URL"
```

Zusatzlich sichern:

- Upload-Verzeichnis aus `UPLOADS_DIR`
- Export-Verzeichnis aus `EXPORTS_DIR`
- Cache nur, wenn ein Restore ohne erneute Generierung notwendig ist
- Konfigurationsdateien und Secrets separat und sicher verwahren

### Restore

```bash
createdb creatorhub_restore
pg_restore --clean --if-exists --dbname=creatorhub_restore creatorhub-db.dump
```

Danach:

1. Anwendung gegen die wiederhergestellte Datenbank starten.
2. Alembic-Stand pruefen und nur bei Bedarf kontrolliert migrieren.
3. Uploads, Exporte und ggf. weitere Dateipfade zurueckspielen.
4. Health-Checks und einen fachlichen Smoke-Test ausfuehren.

### Restore-Pruefung

- Login und Session-Handling testen
- Eine Registrierungsfreigabe pruefen
- Einen Produkt- oder Asset-Workflow pruefen
- Worker-Queue und Health-Endpunkte beobachten

## 9. Verweis auf weitere Dokumente

- [API-Design-Konventionen](./api-design.md)
- [Domain Status Rules](./domain-status-rules.md)
- [Release- und Rollback-Prozess](./release-and-rollback.md)
- [Design System](./design-system.md)

## 10. Rollen und Verantwortlichkeiten

Die folgenden Rollen beschreiben die praktische Zustands- und Betriebsverantwortung im Projekt.

### Produkt- und Fachverantwortung

- Produktverantwortliche definieren Prioritaeten, fachliche Zielbilder und Freigabekriterien.
- Fachverantwortliche geben inhaltliche Regeln fuer Produkte, Content, Assets, Kommunikation und Registrierung vor.
- Reviewer entscheiden ueber Freigaben, Rueckweisungen und Ausnahmefaelle innerhalb ihrer Berechtigungen.

### Technische Verantwortung

- Backend-Entwicklung verantwortet API, Domänenlogik, Migrationen, Auth, Audit und Hintergrundverarbeitung.
- Frontend-Entwicklung verantwortet Nutzerfuehrung, Zustandsanzeige, Formulare und Bedienbarkeit.
- Betrieb/Administration verantwortet Freigaben, Sperren, Passwort-Resets, Monitoring und Incident-Erstreaktion.
- Plattform-/DevOps-Verantwortliche pflegen Deployment, Infrastruktur, Backups, Restore-Tests und Laufzeitkonfiguration.

### Klarer Zuständigkeitsgrundsatz

- Fachliche Entscheidungen gehoeren nicht in UI-Only-Code.
- Sicherheitsentscheidungen gehoeren nicht in den Browser.
- Datenkorrekturen mit Folgen fuer andere Benutzer werden nur mit Audit und Rueckrollmöglichkeit vorgenommen.

## 11. Freigabeworkflows

Freigabeworkflows sind im Projekt bewusst serverseitig modelliert und auditiert.

### Registrierung

- Neue Benutzer registrieren sich ueber einen Request.
- Admins pruefen den Request, geben ihn frei oder lehnen ihn mit Begruendung ab.
- Bei Freigabe wird ein Benutzer angelegt.
- Bei Ablehnung wird der Grund dokumentiert und im Verlauf sichtbar gehalten.

### Produkt- und Content-Freigaben

- Produkte, Assets, Content und zugehoerige Arbeitsobjekte folgen dem dokumentierten Statusmodell.
- Statuswechsel benoetigen die jeweils passenden Berechtigungen.
- Relevante Aenderungen erzeugen Review- und Audit-Spuren.

### Benutzer- und Sicherheitsfreigaben

- Rollenwechsel, Sperren, Entsperren und Passwort-Resets sind sensible Aktionen.
- Diese Aktionen benoetigen serverseitige Berechtigungspruefung und werden protokolliert.
- Bei Bedarf sind Bestaetigung und Step-up-MFA Teil des Workflows.

## 12. Datenlebenszyklen

Die wichtigsten Datenklassen folgen unterschiedlichen Lebenszyklen.

### Registrierung und Identitaet

- `RegistrationRequest` beginnt als `pending`.
- Nach Review wechselt der Request zu `approved` oder `rejected`.
- `reviewed_at`, Reviewer und Ablehnungsgrund bleiben fuer Nachvollziehbarkeit erhalten.
- Benutzerkonten koennen gesperrt, entsperrt oder fuer Passwort-Reset markiert werden.

### Sessions und Tokens

- Auth-Sessions haben Idle- und Absolute-Timeouts.
- Refresh- und Access-Cookies sind zeitlich begrenzt und an Sessionzustand gebunden.
- Administrative Eingriffe koennen Sessions revoken und Tokens ungueltig machen.

### Inhalte, Assets und Produkte

- Inhalte und Assets durchlaufen Review-, Freigabe- und Archivzustand.
- Produktdaten koennen durch Verkaufs- oder Archivprozesse weiterentwickelt werden.
- Historische Aenderungen bleiben ueber Audit- und Domain-Events nachvollziehbar.

### Logs, Exporte und Cache

- Logs werden rotiert und nach Frist geloescht.
- Exporte sind fuer externe Weitergabe gedacht und muessen separat behandelt werden.
- Cache-Daten sind abgeleitet und duerfen nicht als alleinige Quelle fuer kritische Wahrheiten dienen.

## 13. Onboarding fuer neue Entwickler

### Ziel des Onboardings

- Neue Entwickler sollen die Produktdomänen, die lokale Entwicklungsumgebung und die Sicherheitsgrenzen schnell verstehen.

### Empfohlene Reihenfolge

1. Repository klonen und README lesen.
2. Backend- und Frontend-Abhaengigkeiten installieren.
3. `.env` aus dem Template ableiten und mindestens Datenbank, Redis und JWT konfigurieren.
4. Backend lokal starten und Health-Endpunkte pruefen.
5. Frontend lokal starten und die wichtigsten Flows manuell pruefen.
6. Backend-Tests und Frontend-Checks einmal ausfuehren.
7. Die Doku fuer Architektur, Statusregeln und Release-Prozess lesen.

### Wichtige Einstiegspunkte im Code

- [Backend-Startpunkt](../backend/app/main.py)
- [Backend-Konfiguration](../backend/app/core/config.py)
- [Backend-Routen](../backend/app/api/routers/)
- [Frontend-API](../frontend/src/api.ts)
- [Frontend-Seiten](../frontend/src/pages/)
- [Frontend-Features](../frontend/src/features/)

### Onboarding-Prueffragen

- Wo liegt die Source of Truth fuer einen bestimmten Datentyp?
- Welche Aktionen sind im Browser nur sichtbar, aber serverseitig abgesichert?
- Welche Statuswechsel sind erlaubt und welche erzeugen Audit- oder Domain-Events?
- Wie wird ein Problem sauber zurueckgerollt oder wiederhergestellt?

## 14. Admin-Handbuch

### Typische Aufgaben

- Registrierungsanfragen pruefen und mit Begruendung freigeben oder ablehnen.
- Benutzerstatus ueberwachen, sperren, entsperren und Passwort-Resets ausloesen.
- Aktive Sessions kontrollieren und bei Bedarf einzelne Sessions oder alle Sessions eines Benutzers entziehen.
- Audit- und Rollenveraenderungen bei auffaelligen Vorfaellen pruefen.

### Betriebsablauf fuer Admins

1. Betroffenen Datensatz in der Admin-Ansicht oeffnen.
2. Kontext und vorhandene Historie pruefen.
3. Aktion ausfuehren und Folgezustand kontrollieren.
4. Bei sicherheitsrelevanten Eingriffen Audit-Log und Sessionzustand verifizieren.
5. Bei Unsicherheit zuerst sperren, dann analysieren, dann gezielt entsperren oder zuruecksetzen.

### Notfallregeln

- Bei verdächtigen Konten zuerst Zugriff begrenzen, dann Ursache analysieren.
- Passwort-Resets und Sperren immer mit Grund und Nachvollziehbarkeit behandeln.
- Nicht direkt in Datenbanktabellen manuell eingreifen, wenn ein API- oder Serviceweg existiert.
- Bei ungewoehnlichen Ablaeufen zuerst Logs, Audit und Sessions pruefen, erst dann Daten korrigieren.

## 15. Betriebliche Standards und Zuständigkeiten

### Standard für Aenderungen

- Jede produktive Aenderung braucht eine Rueckfallebene oder Rollback-Strategie.
- Migrationen werden vor dem Rollout getestet.
- Sicherheitsrelevante Aenderungen werden auditiert.
- Kritische Flows bekommen vor Release mindestens einen gezielten Smoke-Test.

### Standard fuer Betrieb und Support

- Health-Checks sind erste Diagnosequelle.
- Logs sollen strukturiert, korreliert und ohne Geheimnisse sein.
- Queue- und Worker-Zustaende gehoeren zur regelmaessigen Betriebsbeobachtung.
- Backup und Restore sind nicht optional, sondern Teil des Betriebsstandards.

### Zustandsverantwortung

- Entwicklung verantwortet Code, Tests und Migrationen.
- Betrieb verantwortet Verfuegbarkeit, Monitoring und Wiederherstellung.
- Fachverantwortung definiert, wann ein Zustand fachlich korrekt ist.
- Admins handeln innerhalb der dokumentierten Berechtigungen und Eskalationswege.

### Minimaler Service-Standard

- Neue Features sollen dokumentiert sein, bevor sie produktiv relevant werden.
- Kritische Aenderungen muessen in Release- und Rollback-Notizen abbildbar sein.
- Die Doku wird bei neuen Workflows oder Sicherheitsregeln mitgezogen.
