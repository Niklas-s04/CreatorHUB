# Domain Status Rules

Dieses Dokument beschreibt die technisch erzwungenen Statusregeln im Backend.

## Einheitliches Workflow-/Freigabemodell (moduleübergreifend)

Für `products`, `content_items`, `deal_drafts`, `knowledge_docs` und `assets` gilt zusätzlich ein
einheitlicher Workflow-Status:

- `draft`
- `in_review`
- `approved`
- `rejected`
- `published`
- `archived`

Erlaubte Übergänge:

- `draft` → `in_review`, `archived`
- `in_review` → `approved`, `rejected`, `draft`
- `approved` → `published`, `archived`, `in_review`
- `rejected` → `draft`, `in_review`, `archived`
- `published` → `in_review`, `archived`
- `archived` → `in_review`

Zusätzliche Regeln:

- Für `approved`, `rejected` und `published` ist `review_reason` verpflichtend.
- Reviewer-Informationen werden pro Wechsel revisionssicher gespeichert (`reviewed_by_id`, `reviewed_by_name`, `reviewed_at`).
- Änderungen an relevanten Fachfeldern erzwingen bei bereits `approved`/`published` Objekten automatisch `in_review` (Re-Review).
- Jeder Workflowwechsel wird zusätzlich als Audit-Log und Domain-Event protokolliert.

## Produkte (`ProductStatus`)

Erlaubte Übergänge:

- `active` → `sold`, `gifted`, `returned`, `broken`, `archived`
- `sold` → `returned`, `archived`
- `gifted` → `archived`
- `returned` → `active`, `broken`, `archived`
- `broken` → `returned`, `archived`
- `archived` → _(keine)_

Zusätzliche Regeln:

- `sold` erfordert `amount`.
- Statuswechsel über `/api/products/{id}/status` erzeugen je nach Zielstatus automatisch eine `ProductTransaction`.

## Assets (`AssetReviewState`)

Erlaubte Übergänge:

- `quarantine` → `pending_review`, `rejected`
- `pending_review` → `needs_review`, `pending`, `approved`, `rejected`, `quarantine`
- `needs_review` → `pending`, `approved`, `rejected`
- `pending` → `needs_review`, `approved`, `rejected`
- `approved` → `needs_review`, `rejected`
- `rejected` → `pending_review`, `needs_review`

Zusätzliche Regeln:

- `is_primary=true` ist nur für Produkt-Bilder erlaubt (`owner_type=product`, `kind=image`).
- `approved` erfordert `local_path` oder `url`.
- Wechsel zu `rejected` setzt `is_primary=false`.

## Content (`ContentStatus`)

Erlaubte Übergänge:

- `idea` → `draft`
- `draft` → `recorded`, `scheduled`
- `recorded` → `edited`
- `edited` → `scheduled`, `published`
- `scheduled` → `published`, `draft`
- `published` → _(keine)_

Zusätzliche Regeln:

- `scheduled` erfordert `planned_date` oder `publish_date`.
- `published` erfordert `publish_date` oder `external_url`.
- Bei Wechsel zu `published` wird `publish_date` automatisch gesetzt, falls nicht vorhanden.

## Freigaben (`RegistrationRequestStatus`)

Erlaubte Übergänge:

- `pending` → `approved`, `rejected`
- `rejected` → `pending` (erneute Einreichung)
- `approved` → _(keine)_

Zusätzliche Regeln:

- Bei `approved` wird ein neuer Benutzer angelegt.
- Bei Re-Submission wird ein bestehender `rejected` Request auf `pending` zurückgesetzt.

## Domain Events

Statuswechsel und zustandsbezogene Nebenwirkungen werden zusätzlich als Domain-Event über Audit-Logs erfasst (`action = domain_event.<name>`), z. B.:

- `domain_event.product.status.changed`
- `domain_event.product.transaction.created`
- `domain_event.asset.review_state.changed`
- `domain_event.content.status.changed`
- `domain_event.registration.request.approved|rejected|reopened`

## End-to-End Workflows (7.2)

### Produkt → Asset → Content → Kommunikation

- Produkte werden mit Assets (`owner_type=product`) und Content (`content_items.product_id`) fachlich verknüpft.
- Operations-Inbox identifiziert Medienbrüche als `workflow_gap`, z. B.:
	- Produkt ohne freigegebenes Asset
	- Asset vorhanden, aber kein Content
	- Content vorhanden, aber kein verknüpfter Deal/Kommunikationsschritt

### Deal-Workflow mit Checklisten + Freigaben

- `deal_drafts` unterstützen `product_id` und eine persistente `checklist`.
- Bei Übergängen in `review`/`negotiating`/`won` werden Pflichtpunkte technisch geprüft.
- Fehlende Pflichtpunkte blockieren den Fortschritt (BusinessRuleViolation).

### E-Mail-Erstellung mit Risiko-Prüfung + Freigabe

- Jeder Entwurf speichert `risk_flags`, `risk_score`, `risk_checked_at`.
- Freigabe/Rejection erfolgt explizit per Approval-Flow (`approved`, `approval_reason`, `approved_by_*`, `approved_at`).
- Für High-Risk-Entwürfe ist ein Freigabegrund verpflichtend.

### Verkaufsabschluss mit Archivierung + Historisierung

- Bei Produkt-Status `sold` wird ein Abschluss-Workflow ausgelöst:
	- verknüpfte Deals auf `won` gesetzt und archiviert,
	- verknüpfter Content archiviert,
	- verknüpfte Produkt-Assets archiviert,
	- zusammenfassende Historisierung via Audit-Log (`sales.workflow.finalized`) + Domain Event (`domain_event.sales.closed`).

## Aufgaben- und Zuständigkeitsmodell (7.3)

Für `content_tasks` gilt zusätzlich:

- Zuweisung an konkrete Benutzer (`assignee_user_id`) oder Rollen (`assignee_role`)
- Prioritäten (`low|medium|high|critical`)
- Fälligkeitsdaten (`due_date`) mit Overdue-Kennzeichnung (`is_overdue`)
- Benachrichtigungs-/Eskalationszeitpunkte (`notified_at`, `escalated_at`)

Zusätzliche Regeln:

- Benutzer- und Rollenzuweisung sind gegenseitig exklusiv.
- Kurz vor Fälligkeit werden Due-Soon-Events emittiert.
- Überfällige Aufgaben werden eskaliert und als `content_overdue` in Operations hervorgehoben.

Persönliche Arbeitslisten und Ansichten:

- Persönliche Task-Listen pro Benutzer (`/content/tasks/me`) mit Filtern.
- Filterbar nach Verantwortlichem, Rolle, Priorität, Status, Overdue.
- Gespeicherte Ansichten (`content_task_views`) für wiederkehrende Arbeitsfilter.
