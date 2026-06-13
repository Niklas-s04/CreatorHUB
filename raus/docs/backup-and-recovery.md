# Backup and Recovery

## Database Backups

- Run a daily PostgreSQL backup.
- Use `pg_dump -Fc` for portable restore files.
- Store backups in encrypted object storage.
- Keep at least 30 days of retention.

## Asset Backups

- Keep uploaded files outside the database.
- Back up uploads and exports separately from the database.
- Verify that backup storage matches the active recovery window.

## Recovery Objectives

- RTO: 30 minutes
- RPO: 1 day

## Recovery Procedure

1. Restore the latest backup into a clean environment.
2. Verify the database content and schema.
3. Start the application against the restored database.
4. Run login, search, and asset access smoke tests.

## Validation Commands

- `python backend/scripts/validate_backup_restore.py --database-url "$DATABASE_URL"`
- `python backend/scripts/validate_prod_release.py --base-url "$PROD_BASE_URL" --monitoring-report-path "$PROD_MONITORING_REPORT_PATH"`

## Operational Notes

- Backups must be encrypted at rest.
- Restore tests should use the same migration path as production.
