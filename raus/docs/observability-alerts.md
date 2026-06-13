# Observability Alerts

This document defines the baseline alert rules for CreatorHUB.

## Alert Principles

- Alert on user-impacting degradation, not every metric fluctuation.
- Prefer actionable thresholds with clear ownership.
- Keep metrics free of secrets and unnecessary personal data.

## Baseline Rules

### 1. HTTP Error Rate

- Condition: 5xx error rate above 5% over a rolling 5-minute window.
- Severity: Page.
- Action: Check logs, recent deploys, upstream dependencies, and rate limiting behavior.

### 2. Database Pool Exhaustion

- Condition: database connection pool exhausted or consistently near max capacity.
- Severity: Page.
- Action: Inspect slow queries, pending migrations, and worker concurrency.

### 3. Worker Failures

- Condition: more than 10 failed jobs in the current alert window.
- Severity: Warning.
- Action: Inspect job payloads, retries, and poisoned queues.

### 4. Latency Regression

- Condition: p99 response time above 1 second for core API routes.
- Severity: Warning.
- Action: Check database latency, queue depth, and recent releases.

## Metric Families

- `api_requests_total`
- `api_errors_total`
- `api_request_latency_seconds`
- `db_queries_total`
- `db_query_errors_total`
- `db_query_latency_seconds`
- `redis_commands_total`
- `redis_command_errors_total`
- `redis_command_latency_seconds`

## Operational Notes

- Alerts are defined for the production environment only.
- Use redacted logs and traces during incident triage.
