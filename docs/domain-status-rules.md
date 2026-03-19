# Domain Status Rules

Dieses Dokument beschreibt die technisch erzwungenen Statusregeln im Backend.

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
