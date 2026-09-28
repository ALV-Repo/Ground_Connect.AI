-- ============================================================
-- DB-017 VERIFICATION TESTS
-- ============================================================
-- Run after the DB-017 . Tests are read-only and rollback-safe.

BEGIN;

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT count(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'consent_privacy_erasure'
      AND table_name IN (
          'privacy_notices',
          'consent_receipts',
          'erasure_requests',
          'erasure_cascade_log',
          'retention_schedules',
          'retention_enforcement_log',
          'retention_enforcement_queue',
          'privacy_alert_rules',
          'privacy_alerts',
          'legal_holds'
      );

    IF v_count <> 10 THEN
        RAISE EXCEPTION 'DB-017: expected 10 DB-017 tables, found %', v_count;
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('consent_privacy_erasure.data_principal_requests') IS NOT NULL THEN
        RAISE EXCEPTION 'DB-017: PRV-05 data_principal_requests must not be present';
    END IF;
END $$;

DO $$
BEGIN
    PERFORM 1
    FROM information_schema.columns
    WHERE table_schema = 'consent_privacy_erasure'
      AND table_name = 'consent_receipts'
      AND column_name = 'privacy_notice_version';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'DB-017: privacy_notice_version missing';
    END IF;

    PERFORM 1
    FROM information_schema.columns
    WHERE table_schema = 'consent_privacy_erasure'
      AND table_name = 'consent_receipts'
      AND column_name = 'lawful_basis_type';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'DB-017: lawful_basis_type missing';
    END IF;
END $$;

DO $$
BEGIN
    IF (
        SELECT count(*)
        FROM information_schema.columns
        WHERE table_schema = 'consent_privacy_erasure'
          AND table_name = 'erasure_cascade_log'
          AND column_name IN (
              'evidence_type',
              'external_reference',
              'evidence_hash',
              'verified_at'
          )
    ) <> 4 THEN
        RAISE EXCEPTION 'DB-017: external purge evidence columns missing';
    END IF;

    IF (
        SELECT count(*)
        FROM information_schema.columns
        WHERE table_schema = 'consent_privacy_erasure'
          AND table_name = 'retention_schedules'
          AND column_name IN (
              'owner_role_name',
              'alert_enabled',
              'alert_before_days'
          )
    ) <> 3 THEN
        RAISE EXCEPTION 'DB-017: named ownership/alert schedule columns missing';
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('consent_privacy_erasure.retention_enforcement_queue') IS NULL THEN
        RAISE EXCEPTION 'DB-017: retention enforcement queue missing';
    END IF;

    IF to_regclass('consent_privacy_erasure.privacy_alert_rules') IS NULL
       OR to_regclass('consent_privacy_erasure.privacy_alerts') IS NULL THEN
        RAISE EXCEPTION 'DB-017: alerting framework tables missing';
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('consent_privacy_erasure.privacy_obligations_dashboard') IS NULL THEN
        RAISE EXCEPTION 'DB-017: obligations dashboard view missing';
    END IF;

    IF to_regprocedure(
        'consent_privacy_erasure.issue_erasure_certificate(uuid,uuid)'
    ) IS NULL THEN
        RAISE EXCEPTION 'DB-017: certificate function missing';
    END IF;

    IF to_regprocedure(
        'consent_privacy_erasure.enqueue_due_retention_work(uuid)'
    ) IS NULL THEN
        RAISE EXCEPTION 'DB-017: retention automation entry point missing';
    END IF;

    IF to_regprocedure(
        'consent_privacy_erasure.refresh_privacy_alerts(uuid)'
    ) IS NULL THEN
        RAISE EXCEPTION 'DB-017: alert refresh entry point missing';
    END IF;
END $$;

DO $$
DECLARE
    v_bad INTEGER;
BEGIN
    SELECT count(*) INTO v_bad
    FROM pg_policies
    WHERE schemaname = 'consent_privacy_erasure'
      AND tablename IN (
          'privacy_notices',
          'consent_receipts',
          'erasure_requests',
          'retention_schedules',
          'legal_holds',
          'erasure_cascade_log',
          'retention_enforcement_log',
          'retention_enforcement_queue',
          'privacy_alert_rules',
          'privacy_alerts'
      )
      AND policyname LIKE 'db017_%';

    IF v_bad <> 10 THEN
        RAISE EXCEPTION 'DB-017: expected 10 tenant RLS policies, found %', v_bad;
    END IF;
END $$;

SELECT
    schemaname,
    tablename,
    rowsecurity,
    forcerowsecurity
FROM pg_tables
WHERE schemaname = 'consent_privacy_erasure'
  AND tablename IN (
      'erasure_cascade_log',
      'retention_enforcement_log'
  )
ORDER BY tablename;

SELECT *
FROM consent_privacy_erasure.privacy_obligations_dashboard
ORDER BY organization_id, data_class;

ROLLBACK;
