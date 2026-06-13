# Domain Status Rules

This document defines the workflow and status rules enforced by the backend.

## Shared Workflow Model

The following entities use a common workflow model:

- `products`
- `content_items`
- `deal_drafts`
- `knowledge_docs`
- `assets`

Shared workflow states:

- `draft`
- `in_review`
- `approved`
- `rejected`
- `published`
- `archived`

Allowed transitions:

- `draft` → `in_review`, `archived`
- `in_review` → `approved`, `rejected`, `draft`
- `approved` → `published`, `archived`, `in_review`
- `rejected` → `draft`, `in_review`, `archived`
- `published` → `in_review`, `archived`
- `archived` → `in_review`

Additional rules:

- `review_reason` is required for `approved`, `rejected`, and `published`.
- Reviewer metadata is stored for each transition.
- Changes to relevant fields move approved or published objects back to `in_review` for re-review.
- Every workflow change is also recorded as an audit event and a domain event.

## Products (`ProductStatus`)

Allowed transitions:

- `active` → `sold`, `gifted`, `returned`, `broken`, `archived`
- `sold` → `returned`, `archived`
- `gifted` → `archived`
- `returned` → `active`, `broken`, `archived`
- `broken` → `returned`, `archived`
- `archived` → none

Additional rules:

- `sold` requires `amount`.
- Status changes via `/api/products/{id}/status` create a `ProductTransaction` when appropriate.

## Assets (`AssetReviewState`)

Allowed transitions:

- `quarantine` → `pending_review`, `rejected`
- `pending_review` → `needs_review`, `pending`, `approved`, `rejected`, `quarantine`
- `needs_review` → `pending`, `approved`, `rejected`
- `pending` → `needs_review`, `approved`, `rejected`
- `approved` → `needs_review`, `rejected`
- `rejected` → `pending_review`, `needs_review`

Additional rules:

- `is_primary=true` is only valid for product images.
- `approved` requires either `local_path` or `url`.
- A transition to `rejected` clears `is_primary`.

## Content (`ContentStatus`)

Allowed transitions:

- `idea` → `draft`
- `draft` → `recorded`, `scheduled`
- `recorded` → `edited`
- `edited` → `scheduled`, `published`
- `scheduled` → `published`, `draft`
- `published` → none

Additional rules:

- `scheduled` requires `planned_date` or `publish_date`.
- `published` requires `publish_date` or `external_url`.
- A transition to `published` sets `publish_date` automatically when needed.

## Registration Requests

Allowed transitions:

- `pending` → `approved`, `rejected`
- `rejected` → `pending`
- `approved` → none

Additional rules:

- Approval creates a new user account.
- Re-submission resets a rejected request to pending.

## Domain Events

Status changes and related side effects are also captured as domain events in audit logs, for example:

- `domain_event.product.status.changed`
- `domain_event.product.transaction.created`
- `domain_event.asset.review_state.changed`
- `domain_event.content.status.changed`
- `domain_event.registration.request.approved`
- `domain_event.registration.request.rejected`
- `domain_event.registration.request.reopened`

## End-to-End Workflow Notes

### Product → Asset → Content → Communication

- Products are linked to assets and content through explicit foreign keys.
- The operations inbox highlights workflow gaps such as missing assets or missing content.

### Deal Workflow

- Deal drafts support product linkage and persistent checklists.
- Required checklist items are validated when a deal moves into review, negotiation, or won states.

### Email Draft Workflow

- Each draft stores risk flags, a risk score, and the time of the last risk check.
- Approval and rejection are explicit and auditable.

### Sales Finalization

- When a product is sold, linked deals, content, and assets are archived as part of the finalization workflow.

## Task and Assignment Model

For `content_tasks`:

- Assignments may target a user or a role, but not both.
- Priority values are `low`, `medium`, `high`, and `critical`.
- Due dates support overdue detection and escalation.
- Saved task views are supported for recurring work patterns.
