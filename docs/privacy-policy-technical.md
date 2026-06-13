# Privacy Policy - Technical Implementation

**Effective Date:** April 15, 2026  
**Last Updated:** April 15, 2026

## 1. Data Collection Overview

CreatorHUB collects only the data needed to operate the product:

| Data Category | Purpose | Retention | User Control |
|---------------|---------|-----------|--------------|
| Account Data | Authentication and authorization | Until deletion request expires, then hard delete after the grace period | Export, delete |
| Session Data | Keep the user logged in | Session lifetime, with a maximum absolute duration of 7 days | Automatic logout |
| Audit Logs | Security and compliance | 90 days | View own audit trail |
| Upload Assets | User-generated content | Until the user deletes them | User delete action |
| Email Drafts | AI-assisted suggestions | Until the user saves or deletes them | User control, not logged in detail |
| Search Queries | Image search requests | 7 days locally, then purged | See the Openverse privacy policy |

## 2. Account Data

### Stored Data

- Username, required for login
- Email address, reserved for future password recovery
- Hashed password, never plaintext
- Account role
- Optional MFA secret
- Account deletion timestamp

### Not Stored as Product Data

- IP addresses, except in audit logs where they are retained for the audit retention window
- Continuous login history outside audit events
- User agent strings outside security audit logs
- Location data
- Payment data, unless the product adds a payment flow later

### User Rights

- Access: `GET /api/v1/users/me`
- Export: `GET /api/v1/users/me/export`
- Delete: `POST /api/v1/users/me/account-deletion/request`

## 3. Session and Authentication Data

### Session Flow

- Login creates an `AuthSession` record with secure tokens.
- Cookies are used for authentication: `creatorhub_auth` and `creatorhub_refresh`.
- Idle timeout is 30 minutes.
- Absolute session timeout is 7 days.
- After timeout, the user must log in again.

### Session Termination

- Logout revokes the session immediately.
- Tokens are invalidated.
- The CSRF token is rotated.
- Cookies are cleared from the client.

### Security Configuration

- Cookies use the `Secure` flag.
- Cookies use `SameSite=strict`.
- Cookies use `HttpOnly` where technically possible.
- Cookie domain is explicitly required in production.

## 4. Audit Logs and Privacy

### What Gets Logged

Only state-changing operations are logged.

### What Does Not Get Logged

- Product reads
- Search queries
- Dashboard views

### Sensitive Field Redaction

Audit logs automatically redact sensitive values such as passwords, tokens, secrets, MFA secrets, card numbers, and national identifiers.

### Retention and Deletion

- General audit logs: 90 days
- Security events: 90 days
- User deletion: audit references are anonymized after hard deletion

## 5. AI Features and Privacy

### Email Draft Generation

- Context is sent to local Ollama only.
- Drafts are generated locally and are not logged in full.
- Audit logs record the event, not the content.
- No training is performed on user prompts.

### Image Search

- Queries are sent to Openverse.
- Results are cached locally for 7 days and then removed.
- Openverse's own privacy policy applies to the external request.

### Privacy Guarantees

- No AI training on user data.
- No third-party tracking for AI features.
- Local processing is preferred when available.

## 6. Upload and Asset Management

### File Uploads

- Files are stored server-side with UUID-based keys.
- The original filename is preserved separately for display.
- Magic-byte validation is required for supported file types.
- New uploads start in quarantine.

### Asset Lifecycle

1. Upload into quarantine.
2. Admin review.
3. Approval or rejection.
4. Visible only after approval.
5. User deletion removes the asset immediately.

### Privacy Note

Assets are not automatically removed with account deletion when they are still referenced by products or other shared content. User data is deleted, but content references may remain where integrity requires it.

## 7. Telemetry and Observability

### Disabled by Default

- Application performance monitoring
- Session replay
- Heatmaps
- Behavioral analytics

### If Enabled Later

Telemetry must remain minimal, anonymized where possible, and opt-in or otherwise clearly disclosed.

### Never Collected

- Cursor movement
- Keystroke patterns
- Form input values
- Plain PII in logs

## 8. Cookies and Consent

### Essential Cookies

- `creatorhub_auth`
- `creatorhub_refresh`
- `creatorhub_csrf`

### Optional Cookies

- Analytics, if added later
- Preferences such as theme or language

### Consent Banner

- The consent banner appears on first visit if no choice is stored.
- The consent level is stored in `localStorage`.
- Optional analytics are disabled unless the user opts in.

## 9. Third-Party Integrations

### Openverse

- Shared data: search query
- Purpose: image search
- Control: user curates results before saving

### Ollama

- Shared data: email draft context, locally only
- Purpose: local text generation
- Control: fully user-controlled

### Not Used

- No Google Analytics
- No Sentry or similar analytics SDKs
- No CDN that stores user data
- No external email provider at this stage

## 10. Data Deletion

### Deletion Request Flow

```text
POST /api/v1/users/me/account-deletion/request
→ Sets user.deletion_requested_at
→ Creates audit log event: user.account.deletion_requested
→ Returns the grace period information
```

### Grace Period

- Users can cancel the request during the grace period.
- After 30 days, the purge job performs hard deletion.

### Hard Delete

1. Delete auth sessions.
2. Delete MFA secrets if present.
3. Anonymize audit references.
4. Delete the user record.
5. Create a final system-generated audit entry.

### Data Not Deleted

- Assets that are still referenced elsewhere
- Products that represent the user's work
- Comments and shared content where integrity must be preserved
- The anonymized audit trail

## 11. Data Breach Notification

- Affected users are notified within 72 hours when personal data is compromised.
- Notifications describe the type of data involved and the containment measures taken.
- Contact: privacy@creatorhub.local

## 12. Data Subject Rights

- Access
- Rectification
- Erasure
- Restriction
- Portability
- Objection

Requests can be handled through the API, by email, or through support processes where applicable.

## 13. Policy Updates

- Policy changes may be issued as needed.
- Material changes should be communicated in-app and reflected in the product documentation.
- Review cycle: annual, or sooner if the data model changes materially.

## 14. Compliance Frameworks

This implementation is aligned with GDPR and can support additional frameworks such as SOC 2 or PCI-DSS if the corresponding product features are added.

## 15. Implementation References

- Audit logging: [Audit Log Policy](./audit-policy.md)
- Configuration: [Technical Documentation](./technical-documentation.md)
- Account deletion: backend services and worker jobs
- Redaction: backend audit service
- Cookie handling: backend web security middleware
