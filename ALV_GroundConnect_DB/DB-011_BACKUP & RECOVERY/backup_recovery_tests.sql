-- ============================================================
-- DB-011 — VALIDATION TESTS
-- ============================================================
-- IMPORTANT:
-- Run this against a dedicated test database or inside a transaction.
-- The tenant INSERT below assumes the existing tenants table permits
-- insertion with only an id. If your existing tenant table requires
-- additional mandatory columns, create the test tenant according to
-- that table's actual definition.
--
-- These tests validate database-side behavior only. They do NOT prove
-- that external WAL archiving, backup storage, encryption, credential
-- isolation, or physical PITR are operational.
-- ============================================================

BEGIN;

DO $$
DECLARE
    v_tenant UUID;
    v_policy UUID;
    v_backup UUID;
    v_drill UUID;
    v_count INTEGER;
BEGIN
    -- --------------------------------------------------------
    -- TEST 01: Required DB-011 tables exist
    -- --------------------------------------------------------
    SELECT COUNT(*)
    INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'backup_recovery'
      AND table_name IN (
          'backup_policies',
          'backup_runs',
          'wal_archive_status',
          'recovery_drills'
      );

    IF v_count <> 4 THEN
        RAISE EXCEPTION
            'TEST 01 FAILED: expected 4 tables, found %', v_count;
    END IF;

    RAISE NOTICE 'TEST 01 PASSED';

    -- --------------------------------------------------------
    -- TEST 02: Required functions exist
    -- --------------------------------------------------------
    SELECT COUNT(*)
    INTO v_count
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'backup_recovery'
      AND p.proname IN (
          'record_backup_run',
          'record_wal_archive_status',
          'record_recovery_drill'
      );

    IF v_count <> 3 THEN
        RAISE EXCEPTION
            'TEST 02 FAILED: expected 3 recording functions, found %', v_count;
    END IF;

    RAISE NOTICE 'TEST 02 PASSED';

    -- --------------------------------------------------------
    -- TEST 03: Required views exist
    -- --------------------------------------------------------
    SELECT COUNT(*)
    INTO v_count
    FROM information_schema.views
    WHERE table_schema = 'backup_recovery'
      AND table_name IN (
          'usable_backups',
          'recovery_readiness'
      );

    IF v_count <> 2 THEN
        RAISE EXCEPTION
            'TEST 03 FAILED: expected 2 views, found %', v_count;
    END IF;

    RAISE NOTICE 'TEST 03 PASSED';

    -- --------------------------------------------------------
    -- TEST 04: Required indexes exist
    -- --------------------------------------------------------
    SELECT COUNT(*)
    INTO v_count
    FROM pg_indexes
    WHERE schemaname = 'backup_recovery'
      AND indexname IN (
          'idx_backup_runs_organization_id',
          'idx_backup_runs_policy_time',
          'idx_backup_runs_verification',
          'idx_backup_runs_completed',
          'idx_wal_archive_status_organization_time',
          'idx_wal_archive_status_health',
          'idx_recovery_drills_organization_time',
          'idx_recovery_drills_result',
          'idx_recovery_drills_type'
      );

    IF v_count <> 9 THEN
        RAISE EXCEPTION
            'TEST 04 FAILED: expected 9 indexes, found %', v_count;
    END IF;

    RAISE NOTICE 'TEST 04 PASSED';

    -- --------------------------------------------------------
    -- TEST 05: Create test tenant
    -- --------------------------------------------------------
    INSERT INTO tenant_and_configuration.tenants (id)
    VALUES (gen_random_uuid())
    RETURNING id INTO v_tenant;

    RAISE NOTICE 'TEST 05 PASSED: test tenant created';

    -- --------------------------------------------------------
    -- TEST 06: Create valid backup policy
    -- --------------------------------------------------------
    INSERT INTO backup_recovery.backup_policies (
        organization_id
    )
    VALUES (
        v_tenant
    )
    RETURNING id INTO v_policy;

    RAISE NOTICE 'TEST 06 PASSED';

    -- --------------------------------------------------------
    -- TEST 07: record_backup_run() creates a valid completed backup
    -- --------------------------------------------------------
    SELECT backup_recovery.record_backup_run(
        v_tenant,
        v_policy,
        'daily_full',
        CURRENT_TIMESTAMP - INTERVAL '10 minutes',
        CURRENT_TIMESTAMP - INTERVAL '5 minutes',
        TRUE,
        TRUE,
        'test-storage',
        'test-backup-001',
        'verified',
        CURRENT_TIMESTAMP - INTERVAL '4 minutes',
        'completed',
        NULL
    )
    INTO v_backup;

    IF NOT EXISTS (
        SELECT 1
        FROM backup_recovery.backup_runs
        WHERE id = v_backup
          AND status = 'completed'
          AND encrypted = TRUE
          AND credential_isolated = TRUE
          AND verification_status = 'verified'
    ) THEN
        RAISE EXCEPTION 'TEST 07 FAILED';
    END IF;

    RAISE NOTICE 'TEST 07 PASSED';

    -- --------------------------------------------------------
    -- TEST 08: record_wal_archive_status() works
    -- --------------------------------------------------------
    PERFORM backup_recovery.record_wal_archive_status(
        v_tenant,
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP - INTERVAL '30 seconds',
        30,
        'healthy',
        'test-wal-001',
        'postgresql',
        NULL
    );

    RAISE NOTICE 'TEST 08 PASSED';

    -- --------------------------------------------------------
    -- TEST 09: record_recovery_drill() creates valid passed drill
    -- --------------------------------------------------------
    SELECT backup_recovery.record_recovery_drill(
        v_tenant,
        v_backup,
        'pre_production',
        CURRENT_TIMESTAMP - INTERVAL '50 minutes',
        CURRENT_TIMESTAMP - INTERVAL '5 minutes',
        CURRENT_TIMESTAMP - INTERVAL '45 minutes',
        CURRENT_TIMESTAMP - INTERVAL '46 minutes',
        1.00,
        45.00,
        TRUE,
        TRUE,
        'passed',
        'test-evidence-001',
        NULL
    )
    INTO v_drill;

    IF NOT EXISTS (
        SELECT 1
        FROM backup_recovery.recovery_drills
        WHERE id = v_drill
          AND result = 'passed'
          AND measured_rpo_minutes <= 15
          AND measured_rto_minutes <= 60
    ) THEN
        RAISE EXCEPTION 'TEST 09 FAILED';
    END IF;

    RAISE NOTICE 'TEST 09 PASSED';

    -- --------------------------------------------------------
    -- TEST 10: Invalid policy RPO > 15 is rejected
    -- --------------------------------------------------------
    BEGIN
        INSERT INTO backup_recovery.backup_policies (
            organization_id,
            target_rpo_minutes
        )
        VALUES (
            gen_random_uuid(),
            16
        );

        RAISE EXCEPTION 'TEST 10 FAILED: invalid RPO accepted';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'TEST 10 PASSED';
    END;

    -- --------------------------------------------------------
    -- TEST 11: Invalid policy RTO > 60 is rejected
    -- --------------------------------------------------------
    BEGIN
        INSERT INTO backup_recovery.backup_policies (
            organization_id,
            target_rto_minutes
        )
        VALUES (
            gen_random_uuid(),
            61
        );

        RAISE EXCEPTION 'TEST 11 FAILED: invalid RTO accepted';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'TEST 11 PASSED';
    END;

    -- --------------------------------------------------------
    -- TEST 12: Completed unencrypted backup is rejected
    -- --------------------------------------------------------
    BEGIN
        PERFORM backup_recovery.record_backup_run(
            v_tenant,
            v_policy,
            'daily_full',
            CURRENT_TIMESTAMP - INTERVAL '10 minutes',
            CURRENT_TIMESTAMP - INTERVAL '5 minutes',
            FALSE,
            TRUE,
            NULL,
            'invalid-backup-001',
            'verified',
            CURRENT_TIMESTAMP,
            'completed',
            NULL
        );

        RAISE EXCEPTION
            'TEST 12 FAILED: unencrypted backup accepted';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE 'TEST 12 FAILED:%' THEN
                RAISE;
            END IF;
            RAISE NOTICE 'TEST 12 PASSED';
    END;

    -- --------------------------------------------------------
    -- TEST 13: Completed backup without credential isolation rejected
    -- --------------------------------------------------------
    BEGIN
        PERFORM backup_recovery.record_backup_run(
            v_tenant,
            v_policy,
            'daily_full',
            CURRENT_TIMESTAMP - INTERVAL '10 minutes',
            CURRENT_TIMESTAMP - INTERVAL '5 minutes',
            TRUE,
            FALSE,
            NULL,
            'invalid-backup-002',
            'verified',
            CURRENT_TIMESTAMP,
            'completed',
            NULL
        );

        RAISE EXCEPTION
            'TEST 13 FAILED: non-isolated backup accepted';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE 'TEST 13 FAILED:%' THEN
                RAISE;
            END IF;
            RAISE NOTICE 'TEST 13 PASSED';
    END;

    -- --------------------------------------------------------
    -- TEST 14: Completed unverified backup rejected
    -- --------------------------------------------------------
    BEGIN
        PERFORM backup_recovery.record_backup_run(
            v_tenant,
            v_policy,
            'daily_full',
            CURRENT_TIMESTAMP - INTERVAL '10 minutes',
            CURRENT_TIMESTAMP - INTERVAL '5 minutes',
            TRUE,
            TRUE,
            NULL,
            'invalid-backup-003',
            'pending',
            NULL,
            'completed',
            NULL
        );

        RAISE EXCEPTION
            'TEST 14 FAILED: unverified backup accepted';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE 'TEST 14 FAILED:%' THEN
                RAISE;
            END IF;
            RAISE NOTICE 'TEST 14 PASSED';
    END;

    -- --------------------------------------------------------
    -- TEST 15: Passed drill with RPO > 15 rejected
    -- --------------------------------------------------------
    BEGIN
        PERFORM backup_recovery.record_recovery_drill(
            v_tenant,
            v_backup,
            'quarterly',
            CURRENT_TIMESTAMP - INTERVAL '90 minutes',
            CURRENT_TIMESTAMP - INTERVAL '5 minutes',
            NULL,
            NULL,
            16.00,
            30.00,
            TRUE,
            TRUE,
            'passed',
            'invalid-rpo-evidence',
            NULL
        );

        RAISE EXCEPTION
            'TEST 15 FAILED: RPO > 15 accepted';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE 'TEST 15 FAILED:%' THEN
                RAISE;
            END IF;
            RAISE NOTICE 'TEST 15 PASSED';
    END;

    -- --------------------------------------------------------
    -- TEST 16: Passed drill with RTO > 60 rejected
    -- --------------------------------------------------------
    BEGIN
        PERFORM backup_recovery.record_recovery_drill(
            v_tenant,
            v_backup,
            'quarterly',
            CURRENT_TIMESTAMP - INTERVAL '120 minutes',
            CURRENT_TIMESTAMP - INTERVAL '5 minutes',
            NULL,
            NULL,
            5.00,
            61.00,
            TRUE,
            TRUE,
            'passed',
            'invalid-rto-evidence',
            NULL
        );

        RAISE EXCEPTION
            'TEST 16 FAILED: RTO > 60 accepted';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE 'TEST 16 FAILED:%' THEN
                RAISE;
            END IF;
            RAISE NOTICE 'TEST 16 PASSED';
    END;

    -- --------------------------------------------------------
    -- TEST 17: Passed drill using unverified/non-completed backup rejected
    -- --------------------------------------------------------
    INSERT INTO backup_recovery.backup_runs (
        organization_id,
        backup_policy_id,
        backup_type,
        started_at,
        status,
        encrypted,
        credential_isolated,
        verification_status
    )
    VALUES (
        v_tenant,
        v_policy,
        'manual',
        CURRENT_TIMESTAMP,
        'started',
        FALSE,
        FALSE,
        'pending'
    )
    RETURNING id INTO v_backup;

    BEGIN
        PERFORM backup_recovery.record_recovery_drill(
            v_tenant,
            v_backup,
            'ad_hoc',
            CURRENT_TIMESTAMP - INTERVAL '50 minutes',
            CURRENT_TIMESTAMP - INTERVAL '5 minutes',
            NULL,
            NULL,
            5.00,
            30.00,
            TRUE,
            TRUE,
            'passed',
            'invalid-backup-evidence',
            NULL
        );

        RAISE EXCEPTION
            'TEST 17 FAILED: invalid backup accepted for passed drill';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE 'TEST 17 FAILED:%' THEN
                RAISE;
            END IF;
            RAISE NOTICE 'TEST 17 PASSED';
    END;

    -- --------------------------------------------------------
    -- TEST 18: Passed drill without evidence rejected
    -- --------------------------------------------------------
    BEGIN
        PERFORM backup_recovery.record_recovery_drill(
            v_tenant,
            NULL,
            'ad_hoc',
            CURRENT_TIMESTAMP - INTERVAL '50 minutes',
            CURRENT_TIMESTAMP - INTERVAL '5 minutes',
            NULL,
            NULL,
            5.00,
            30.00,
            TRUE,
            TRUE,
            'passed',
            NULL,
            NULL
        );

        RAISE EXCEPTION
            'TEST 18 FAILED: passed drill without evidence accepted';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE 'TEST 18 FAILED:%' THEN
                RAISE;
            END IF;
            RAISE NOTICE 'TEST 18 PASSED';
    END;

    -- --------------------------------------------------------
    -- TEST 19: usable_backups exposes only valid completed backups
    -- --------------------------------------------------------
    SELECT COUNT(*)
    INTO v_count
    FROM backup_recovery.usable_backups
    WHERE organization_id = v_tenant
      AND backup_run_id = v_backup;

    -- v_backup currently refers to the invalid started backup.
    IF v_count <> 0 THEN
        RAISE EXCEPTION
            'TEST 19 FAILED: invalid backup exposed as usable';
    END IF;

    RAISE NOTICE 'TEST 19 PASSED';

    -- --------------------------------------------------------
    -- TEST 20: recovery_readiness view returns evidence
    -- --------------------------------------------------------
    IF NOT EXISTS (
        SELECT 1
        FROM backup_recovery.recovery_readiness
        WHERE organization_id = v_tenant
    ) THEN
        RAISE EXCEPTION
            'TEST 20 FAILED: recovery_readiness returned no row';
    END IF;

    RAISE NOTICE 'TEST 20 PASSED';

    RAISE NOTICE '============================================================';
    RAISE NOTICE 'DB-011 DATABASE-SIDE VALIDATION PASSED';
    RAISE NOTICE '============================================================';
END $$;

ROLLBACK;

-- ============================================================
-- OPERATIONAL VALIDATION STILL REQUIRED
-- ============================================================
-- 1. Configure continuous WAL archiving.
-- 2. Execute daily encrypted backups.
-- 3. Verify backup credentials are isolated from production.
-- 4. Perform an actual PITR/recovery drill.
-- 5. Measure RPO <= 15 minutes.
-- 6. Measure RTO <= 60 minutes.
-- 7. Record evidence.
-- 8. Repeat recovery drills quarterly.
-- ============================================================
