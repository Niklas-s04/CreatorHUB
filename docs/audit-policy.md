# Audit Log Policy

## Purpose

This policy defines how CreatorHUB records audit events. It is intended to support security review, operational troubleshooting, and GDPR-oriented accountability while keeping the data set minimal.

## What Is Logged

Only state-changing actions are logged.

### Authentication and Security

- `auth.session.login`
- `auth.session.logout`
- `auth.session.revoke`
- `auth.password.change`
- `auth.password.reset.request`
- `auth.password.reset.confirm`
- `auth.mfa.enable`
- `auth.mfa.disable`

### Account Management

- `user.account.deletion_requested`
- `user.account.deletion_canceled`
- `user.account.hard_deleted`

### User Management

- `user.role_or_status.update`
- `user.create`
- `user.lock`
- `user.unlock`

### Registration and Approvals

- `registration.request.review`
- `registration_requests.{request_id}.approval`

### Data Operations

- `product.create`
- `product.update`
- `product.delete`
- `asset.quarantine`
- `asset.approve`

## What Is Not Logged

Read-only activity is excluded to reduce noise and privacy exposure.

- product views
- asset views
- searches
- dashboard views

Admin views of sensitive data may still be logged when a permission gate requires it.

## Critical Events

These actions are marked as critical and may trigger additional monitoring:

- all `auth.*` actions
- all registration approval actions
- `user.role_or_status.update`
- `product.delete`
- `user.account.deletion_requested`
- `user.account.hard_deleted`

## Redaction

Sensitive fields are redacted automatically before storage.

Typical redacted keys include:

- password
- token
- secret
- mfa_secret
- access_token
- refresh_token
- cvv
- ssn
- card_number

Example:

```json
{
  "before": {"password": "***REDACTED***"},
  "after": {"password": "***REDACTED***"}
}
```

## Retention and Deletion

| Data Type | Retention | Removal Method |
|-----------|-----------|----------------|
| Audit logs | 90 days | Automatic purge |
| Security events | 90 days | Automatic purge |
| User records | 30-day grace period | Hard delete after expiration |
| Associated audit references | Immediate anonymization | User ID set to NULL |
| App logs | 30 days | Log rotation |

When a user requests deletion, `deletion_requested_at` is set, the grace period starts, and the purge job anonymizes audit references after hard deletion.

## Access Control

- Only administrators with `Permission.audit_read` may view audit logs.
- Users may export audit data that concerns them through the account export flow.

## Log Structure

```json
{
  "id": "uuid",
  "actor_id": "user_id or null",
  "actor_name": "username, [SYSTEM_*], or [DELETED_USER]",
  "action": "auth.session.login",
  "entity_type": "User",
  "entity_id": "target_id",
  "description": "User logged in",
  "before": {},
  "after": {},
  "meta": {
    "audit_version": "1",
    "audit_category": "security",
    "critical": true,
    "request_id": "uuid",
    "client_ip": "1.2.3.4",
    "client_user_agent": "Mozilla/...",
    "occurred_at": "2026-04-15T10:30:00.000Z"
  },
  "created_at": "2026-04-15T10:30:00.000Z"
}
```

## Compliance

This policy supports GDPR record-keeping, SOC 2 access tracing, and other security or privacy audits where activity evidence is required.
