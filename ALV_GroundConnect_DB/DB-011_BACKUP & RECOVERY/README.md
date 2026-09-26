# DB-011 — Backup & Recovery

## Requirement

DB-011 covers:

- Continuous WAL archiving with point-in-time recovery.
- Daily backups.
- Encrypted backups isolated from production credentials.
- RPO <= 15 minutes.
- RTO <= 1 hour.
- Recovery drill before production go-live.
- Quarterly re-drills.
- Untested backup = no backup.

## Package

```text
DB-011/
├── backup_recovery.sql
├── backup_recovery_tests.sql
└── README.md
```

## Database objects

### Tables

1. `backup_recovery.backup_policies`
2. `backup_recovery.backup_runs`
3. `backup_recovery.wal_archive_status`
4. `backup_recovery.recovery_drills`

### Functions

1. `backup_recovery.record_backup_run()`
2. `backup_recovery.record_wal_archive_status()`
3. `backup_recovery.record_recovery_drill()`

The functions provide controlled database-side recording and validation.
They do not execute physical backup, WAL archival, storage, or PITR.

### Triggers

1. `trg_backup_runs_validate`
2. `trg_recovery_drills_validate`

The triggers protect the integrity rules even when a caller writes directly
to the tables instead of using the recording functions.

### Views

1. `backup_recovery.usable_backups`

Only completed, encrypted, credential-isolated and verified backups are
exposed as usable backups.

2. `backup_recovery.recovery_readiness`

Provides evidence-based database readiness from the latest recorded WAL
observation, latest usable backup, and latest passed recovery drill.

This view is not a replacement for operational monitoring or a real restore.

## Key enforcement rules

### Backup

A backup cannot be marked `completed` unless:

- `completed_at` exists;
- `encrypted = TRUE`;
- `credential_isolated = TRUE`;
- `verification_status = 'verified'`;
- `verified_at` exists.

### Recovery drill

A drill cannot be marked `passed` unless:

- recovery completed;
- measured RPO exists and is <= 15 minutes;
- measured RTO exists and is <= 60 minutes;
- the backup was verified before the drill;
- evidence exists;
- when a backup run is referenced, it is completed and verified.

## What SQL does not perform

This package intentionally does not attempt to perform:

- WAL generation;
- WAL archive transfer;
- physical/base backups;
- object-storage writes;
- backup encryption;
- KMS/HSM operations;
- production credential isolation;
- physical restore;
- PITR execution;
- quarterly scheduling.

Those are PostgreSQL/backup-infrastructure/IAM/operations responsibilities.

The DB-011 schema records their evidence and enforces database-side integrity.

## Validation

Run:

1. `backup_recovery.sql`
2. `backup_recovery_tests.sql`

The validation script runs inside a transaction and rolls the test data back.

### Important environment dependency

The test script creates a test tenant using:

```sql
INSERT INTO tenant_and_configuration.tenants (id)
VALUES (gen_random_uuid());
```

If the project's existing `tenants` table has additional mandatory columns, the test tenant must be created using the actual tenant table definition.

The final package has therefore **not been claimed as executed against the user's live database**.

## Production acceptance

Passing the SQL tests is not the same as completing DB-011.

Production acceptance additionally requires an actual recovery drill demonstrating:

- continuous WAL archiving;
- daily encrypted backup;
- credential isolation;
- successful PITR/restore;
- RPO <= 15 minutes;
- RTO <= 60 minutes;
- documented evidence.

The recovery process must then be re-drilled quarterly.
