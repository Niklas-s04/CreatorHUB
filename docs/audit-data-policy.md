# Audit Data Policy

CreatorHUB keeps audit logging narrow and predictable. This document defines which data is written to audit logs, which data is excluded, and how long records are retained.

## Scope

Audit logging is limited to state-changing and security-relevant actions:

- create
- update
- delete
- export
- authentication and recovery events
- administrative actions

Read-only activity is not logged by default.

## Logged Categories

- `security`: authentication, sessions, MFA, and sensitive actions
- `approval`: registration and review workflows
- `permission_change`: role and permission updates
- `ai_action`: AI-assisted content generation or edits
- `domain`: business workflow events

## Redaction Rules

The following fields are redacted before persistence:

- password
- token
- secret
- access_token
- refresh_token
- mfa_secret
- cvv
- ssn
- card
- card_number

Redaction is recursive and applies to nested dictionaries and lists.

## Retention

- Audit logs: 90 days
- Security events: 90 days
- Application logs: 30 days
- Deleted user records: removed after the purge window

## Operational Notes

- Do not log raw secrets, recovery codes, access tokens, or passwords.
- Do not persist request or response bodies unless a route is explicitly designed for that and redaction has been verified.
- Audit records should remain useful for support and abuse investigations without exposing sensitive payloads.
