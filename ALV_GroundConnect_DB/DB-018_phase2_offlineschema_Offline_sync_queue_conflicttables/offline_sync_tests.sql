-- ============================================================================
-- DB-018 VERIFICATION TESTS
-- OFF-04: durable, ordered, resumable, idempotent queue
-- OFF-05: version conflicts with both versions preserved
-- ============================================================================

BEGIN;

-- --------------------------------------------------------------------------
-- 1. Required schema/tables exist
-- --------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'offline_sync'
          AND table_name = 'syncable_record_versions'
    ) THEN
        RAISE EXCEPTION 'DB-018: syncable_record_versions missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'offline_sync'
          AND table_name = 'sync_queue'
    ) THEN
        RAISE EXCEPTION 'DB-018: sync_queue missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'offline_sync'
          AND table_name = 'sync_conflicts'
    ) THEN
        RAISE EXCEPTION 'DB-018: sync_conflicts missing';
    END IF;
END;
$$;


-- --------------------------------------------------------------------------
-- 2. Required columns
-- --------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'offline_sync'
          AND table_name = 'sync_queue'
          AND column_name = 'idempotency_key'
    ) THEN
        RAISE EXCEPTION 'DB-018: idempotency_key missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'offline_sync'
          AND table_name = 'sync_queue'
          AND column_name = 'sequence_no'
    ) THEN
        RAISE EXCEPTION 'DB-018: sequence_no missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'offline_sync'
          AND table_name = 'syncable_record_versions'
          AND column_name = 'version'
    ) THEN
        RAISE EXCEPTION 'DB-018: version missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'offline_sync'
          AND table_name = 'sync_conflicts'
          AND column_name = 'client_payload'
    ) THEN
        RAISE EXCEPTION 'DB-018: client_payload missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'offline_sync'
          AND table_name = 'sync_conflicts'
          AND column_name = 'server_payload'
    ) THEN
        RAISE EXCEPTION 'DB-018: server_payload missing';
    END IF;
END;
$$;


-- --------------------------------------------------------------------------
-- 3. Required uniqueness constraints
-- --------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'offline_sync'
          AND t.relname = 'sync_queue'
          AND c.conname = 'uq_sync_queue_org_idempotency'
    ) THEN
        RAISE EXCEPTION 'DB-018: idempotency uniqueness constraint missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'offline_sync'
          AND t.relname = 'sync_queue'
          AND c.conname = 'uq_sync_queue_org_device_sequence'
    ) THEN
        RAISE EXCEPTION 'DB-018: ordered sequence uniqueness constraint missing';
    END IF;
END;
$$;


-- --------------------------------------------------------------------------
-- 3A. Active conflict uniqueness
-- --------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_class i
        JOIN pg_namespace n ON n.oid = i.relnamespace
        WHERE n.nspname = 'offline_sync'
          AND i.relname = 'uq_sync_conflicts_active_record'
          AND i.relkind = 'i'
    ) THEN
        RAISE EXCEPTION 'DB-018: active conflict uniqueness index missing';
    END IF;
END;
$$;


-- --------------------------------------------------------------------------
-- 4. Required functions exist
-- --------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'offline_sync'
          AND p.proname = 'enqueue'
    ) THEN
        RAISE EXCEPTION 'DB-018: enqueue function missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'offline_sync'
          AND p.proname = 'record_conflict'
    ) THEN
        RAISE EXCEPTION 'DB-018: record_conflict function missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'offline_sync'
          AND p.proname = 'resolve_conflict'
    ) THEN
        RAISE EXCEPTION 'DB-018: resolve_conflict function missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'offline_sync'
          AND p.proname = 'claim_next'
    ) THEN
        RAISE EXCEPTION 'DB-018: worker-safe claim_next function missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'offline_sync'
          AND p.proname = 'schedule_retry'
    ) THEN
        RAISE EXCEPTION 'DB-018: schedule_retry function missing';
    END IF;
END;
$$;


-- --------------------------------------------------------------------------
-- 5. RLS enabled on all DB-018 tenant tables
-- --------------------------------------------------------------------------

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*)
      INTO v_count
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'offline_sync'
       AND c.relname IN (
           'syncable_record_versions',
           'sync_queue',
           'sync_conflicts'
       )
       AND c.relrowsecurity = TRUE;

    IF v_count <> 3 THEN
        RAISE EXCEPTION
            'DB-018: expected RLS on 3 tables, found %',
            v_count;
    END IF;
END;
$$;


-- --------------------------------------------------------------------------
-- 6. Idempotency test
-- --------------------------------------------------------------------------
-- Uses an existing tenant/device only when available. This test is skipped
-- safely when the database has no seed tenant/device.
-- --------------------------------------------------------------------------

DO $$
DECLARE
    v_org UUID;
    v_device UUID;
    v_record UUID := gen_random_uuid();
    v_key UUID := gen_random_uuid();
    v_first UUID;
    v_second UUID;
BEGIN
    SELECT id
      INTO v_org
      FROM tenant_and_configuration.tenants
     LIMIT 1;

    SELECT id
      INTO v_device
      FROM identity_authentication_sessions.devices
     WHERE organization_id = v_org
     LIMIT 1;

    IF v_org IS NULL OR v_device IS NULL THEN
        RAISE NOTICE 'DB-018 idempotency runtime test skipped: no tenant/device seed data';
        RETURN;
    END IF;

    PERFORM set_config(
        'app.organization_id',
        v_org::TEXT,
        TRUE
    );

    v_first := offline_sync.enqueue(
        v_org,
        v_device,
        1,
        'test_record',
        v_record,
        'create',
        0,
        '{"test":true}'::jsonb,
        v_key
    );

    v_second := offline_sync.enqueue(
        v_org,
        v_device,
        1,
        'test_record',
        v_record,
        'create',
        0,
        '{"test":true}'::jsonb,
        v_key
    );

    IF v_first <> v_second THEN
        RAISE EXCEPTION
            'OFF-04 failed: retry created a duplicate queue row';
    END IF;

    DELETE FROM offline_sync.sync_queue
     WHERE id = v_first;
END;
$$;


-- --------------------------------------------------------------------------
-- 7. Conflict version rule
-- --------------------------------------------------------------------------

DO $$
DECLARE
    v_invalid BOOLEAN;
BEGIN
    SELECT convalidated
      INTO v_invalid
      FROM pg_constraint c
      JOIN pg_class t ON t.oid = c.conrelid
      JOIN pg_namespace n ON n.oid = t.relnamespace
     WHERE n.nspname = 'offline_sync'
       AND t.relname = 'sync_conflicts'
       AND c.conname = 'chk_sync_conflicts_versions_differ';

    IF COALESCE(v_invalid, FALSE) <> TRUE THEN
        RAISE EXCEPTION
            'OFF-05 failed: client/server version difference constraint missing';
    END IF;
END;
$$;


-- --------------------------------------------------------------------------
-- 8. Ensure PRV-05 is not introduced by DB-018
-- --------------------------------------------------------------------------

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'offline_sync'
          AND table_name = 'data_principal_requests'
    ) THEN
        RAISE EXCEPTION
            'DB-018 must not introduce data_principal_requests';
    END IF;
END;
$$;


ROLLBACK;

-- Tests are rolled back so this file does not leave test data behind.
-- The schema implementation itself must be deployed separately first.
