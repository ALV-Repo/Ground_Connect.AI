-- ============================================================
-- DB-020 | Per-Tenant Dedicated Database Provisioning Tests
-- Requirements: TEN-06, SEC-04
-- ============================================================

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM information_schema.schemata
    WHERE schema_name = 'tenant_database_provisioning';

    IF v_count <> 1 THEN
        RAISE EXCEPTION 'DB-020 test failed: schema missing';
    END IF;

    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'tenant_database_provisioning'
      AND table_name IN (
          'database_targets',
          'tenant_database_assignments',
          'tenant_key_bindings'
      );

    IF v_count <> 3 THEN
        RAISE EXCEPTION 'DB-020 test failed: required tables missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'tenant_database_provisioning'
          AND indexname = 'uq_tenant_database_assignments_active'
    ) THEN
        RAISE EXCEPTION 'DB-020 test failed: active routing uniqueness missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'tenant_database_provisioning'
          AND indexname = 'uq_tenant_key_bindings_active'
    ) THEN
        RAISE EXCEPTION 'DB-020 test failed: active key binding uniqueness missing';
    END IF;

    SELECT COUNT(*) INTO v_count
    FROM information_schema.columns
    WHERE table_schema = 'tenant_database_provisioning'
      AND table_name = 'database_targets'
      AND column_name IN (
          'deployment_mode',
          'host_reference',
          'database_name',
          'credential_secret_reference',
          'provisioning_status'
      );

    IF v_count <> 5 THEN
        RAISE EXCEPTION 'DB-020 test failed: routing metadata incomplete';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'tenant_database_provisioning'
          AND table_name = 'database_targets'
          AND column_name IN (
              'password',
              'database_password',
              'private_key',
              'secret_value'
          )
    ) THEN
        RAISE EXCEPTION 'DB-020 test failed: plaintext credential column detected';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'tenant_database_provisioning'
          AND c.relname = 'tenant_database_assignments'
          AND c.relrowsecurity
          AND c.relforcerowsecurity
    ) THEN
        RAISE EXCEPTION 'DB-020 test failed: assignment RLS missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'tenant_database_provisioning'
          AND c.relname = 'tenant_key_bindings'
          AND c.relrowsecurity
          AND c.relforcerowsecurity
    ) THEN
        RAISE EXCEPTION 'DB-020 test failed: key binding RLS missing';
    END IF;

    SELECT COUNT(*) INTO v_count
    FROM information_schema.views
    WHERE table_schema = 'tenant_database_provisioning'
      AND table_name IN (
          'active_tenant_database_routes',
          'dedicated_database_readiness'
      );

    IF v_count <> 2 THEN
        RAISE EXCEPTION 'DB-020 test failed: routing/readiness views missing';
    END IF;


    -- Dedicated target exclusivity
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'tenant_database_provisioning'
          AND indexname = 'uq_dedicated_database_target_exclusive'
    ) THEN
        RAISE EXCEPTION
            'DB-020 test failed: dedicated target exclusivity missing';
    END IF;

    -- Provisioning audit trail
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'tenant_database_provisioning'
      AND table_name = 'provisioning_audit_events';

    IF v_count <> 1 THEN
        RAISE EXCEPTION
            'DB-020 test failed: provisioning audit table missing';
    END IF;

    -- Provisioning audit must be tenant-scoped.
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'tenant_database_provisioning'
          AND table_name = 'provisioning_audit_events'
          AND column_name = 'organization_id'
          AND is_nullable = 'NO'
    ) THEN
        RAISE EXCEPTION
            'DB-020 test failed: provisioning audit organization_id must be NOT NULL';
    END IF;

    -- Cutover tracking
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'tenant_database_provisioning'
      AND table_name = 'database_cutovers';

    IF v_count <> 1 THEN
        RAISE EXCEPTION
            'DB-020 test failed: cutover tracking table missing';
    END IF;

    -- Key rotation evidence
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'tenant_database_provisioning'
      AND table_name = 'key_rotation_evidence';

    IF v_count <> 1 THEN
        RAISE EXCEPTION
            'DB-020 test failed: key rotation evidence table missing';
    END IF;

    -- All new tenant-owned tables must have FORCE RLS.
    FOR v_count IN
        SELECT COUNT(*)
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'tenant_database_provisioning'
          AND c.relname IN (
              'provisioning_audit_events',
              'database_cutovers',
              'key_rotation_evidence'
          )
          AND c.relrowsecurity
          AND c.relforcerowsecurity
    LOOP
        IF v_count <> 3 THEN
            RAISE EXCEPTION
                'DB-020 test failed: RLS/FORCE RLS missing on review-fix tables';
        END IF;
    END LOOP;

    -- Provisioning audit must be immutable.
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_provisioning_audit_immutable'
    ) THEN
        RAISE EXCEPTION
            'DB-020 test failed: immutable provisioning audit trigger missing';
    END IF;

    -- Required cutover lifecycle columns.
    SELECT COUNT(*) INTO v_count
    FROM information_schema.columns
    WHERE table_schema = 'tenant_database_provisioning'
      AND table_name = 'database_cutovers'
      AND column_name IN (
          'cutover_type',
          'status',
          'started_at',
          'completed_at',
          'validation_status',
          'rollback_at',
          'migration_operation_id'
      );

    IF v_count <> 7 THEN
        RAISE EXCEPTION
            'DB-020 test failed: cutover lifecycle metadata incomplete';
    END IF;

    -- Required key rotation evidence fields.
    SELECT COUNT(*) INTO v_count
    FROM information_schema.columns
    WHERE table_schema = 'tenant_database_provisioning'
      AND table_name = 'key_rotation_evidence'
      AND column_name IN (
          'previous_key_version_reference',
          'new_key_version_reference',
          'rotation_history_id',
          'verification_status',
          'verified_at',
          'verification_evidence_ref'
      );

    IF v_count <> 6 THEN
        RAISE EXCEPTION
            'DB-020 test failed: key rotation evidence metadata incomplete';
    END IF;

    RAISE NOTICE
        'DB-020 structural tests passed. Physical provisioning must be verified by infrastructure/CI integration tests.';
END $$;
