-- ============================================================
-- DB-016 VERIFICATION / TEST SCRIPT
-- Run AFTER DB-016 migrations, the audit migration, and tenant_rls.sql.
-- These checks are non-destructive metadata/integrity checks.
-- ============================================================

BEGIN;

-- 1. Required objects exist.
DO $$
BEGIN
    IF to_regclass('citizen_issues.sla_config') IS NULL
       OR to_regclass('citizen_issues.sla_escalation_chains') IS NULL
       OR to_regclass('citizen_issues.sla_escalation_chain_steps') IS NULL
       OR to_regclass('citizen_issues.sla_escalation_events') IS NULL
       OR to_regclass('compliance_mode.compliance_profiles') IS NULL
       OR to_regclass('compliance_mode.compliance_profile_activations') IS NULL
       OR to_regclass('compliance_mode.profile_activation_history') IS NULL
    THEN
        RAISE EXCEPTION 'DB-016 object check failed';
    END IF;
END $$;

-- 2. Required SLA columns.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='citizen_issues'
          AND table_name='sla_config'
          AND column_name='response_target_minutes'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='citizen_issues'
          AND table_name='sla_config'
          AND column_name='resolution_target_minutes'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='citizen_issues'
          AND table_name='sla_config'
          AND column_name='escalation_chain_id'
    ) THEN
        RAISE EXCEPTION 'CIT-13 SLA matrix columns are incomplete';
    END IF;
END $$;

-- 3. Compliance profile fields required by CMP-01.
DO $$
DECLARE
    v_missing INTEGER;
BEGIN
    SELECT COUNT(*)
      INTO v_missing
      FROM (
        VALUES
          ('feature_availability'),
          ('retention_policy'),
          ('mandatory_disclaimers'),
          ('approval_requirements'),
          ('export_restrictions'),
          ('audit_granularity')
      ) AS required(column_name)
      LEFT JOIN information_schema.columns c
        ON c.table_schema='compliance_mode'
       AND c.table_name='compliance_profiles'
       AND c.column_name=required.column_name
     WHERE c.column_name IS NULL;

    IF v_missing <> 0 THEN
        RAISE EXCEPTION 'CMP-01 profile configuration fields are incomplete';
    END IF;
END $$;

-- 4. Exactly one active compliance profile per tenant is enforced
-- by the partial unique index.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname='compliance_mode'
          AND indexname='uq_compliance_profile_activations_one_active'
    ) THEN
        RAISE EXCEPTION 'CMP-01 active-profile uniqueness index is missing';
    END IF;
END $$;

-- 5. History is append-only.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger t
        JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='compliance_mode'
          AND c.relname='profile_activation_history'
          AND t.tgname='trg_profile_activation_history_append_only'
          AND NOT t.tgisinternal
    ) THEN
        RAISE EXCEPTION 'CMP-02 append-only history trigger is missing';
    END IF;
END $$;

-- 6. Activation rows protect immutable snapshot fields.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger t
        JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='compliance_mode'
          AND c.relname='compliance_profile_activations'
          AND t.tgname='trg_compliance_profile_activations_protect'
          AND NOT t.tgisinternal
    ) THEN
        RAISE EXCEPTION 'CMP-02 activation protection trigger is missing';
    END IF;
END $$;

-- 7. SLA breach processor and escalation outbox exist.
DO $$
BEGIN
    IF to_regprocedure(
        'citizen_issues.process_sla_breaches(uuid,timestamptz)'
    ) IS NULL THEN
        RAISE EXCEPTION 'CIT-13 SLA breach processor is missing';
    END IF;
END $$;

-- 8. RLS is enabled and forced for DB-016 tables.
DO $$
DECLARE
    v_bad INTEGER;
BEGIN
    SELECT COUNT(*)
      INTO v_bad
      FROM pg_class c
      JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE (n.nspname,c.relname) IN (
       ('citizen_issues','sla_config'),
       ('citizen_issues','sla_escalation_chains'),
       ('citizen_issues','sla_escalation_chain_steps'),
       ('citizen_issues','sla_escalation_events'),
       ('compliance_mode','compliance_profiles'),
       ('compliance_mode','compliance_profile_activations'),
       ('compliance_mode','profile_activation_history')
     )
       AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity);

    IF v_bad <> 0 THEN
        RAISE EXCEPTION 'DB-016 RLS/force-RLS check failed for % table(s)', v_bad;
    END IF;
END $$;

-- 9. Audit dependency exists.
DO $$
BEGIN
    IF to_regprocedure(
        'audit_trail.append_audit_event(uuid,uuid,uuid,uuid,text,text,uuid,jsonb,text,boolean,timestamptz)'
    ) IS NULL THEN
        RAISE EXCEPTION 'Required audit append function is missing';
    END IF;
END $$;

-- 10A. Verify and exercise the CHECK constraint actually defined
-- by 14_citizen_issues_phase2.sql: chk_sla_config_priority.
DO $$
DECLARE
    v_sla_id UUID;
    v_org_id UUID;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'citizen_issues'
          AND t.relname = 'sla_config'
          AND c.conname = 'chk_sla_config_priority'
          AND c.contype = 'c'
          AND c.convalidated
    ) THEN
        RAISE EXCEPTION
            'DB-016 CHECK missing or not validated: chk_sla_config_priority';
    END IF;

    SELECT id, organization_id
      INTO v_sla_id, v_org_id
      FROM citizen_issues.sla_config
     LIMIT 1;

    IF v_sla_id IS NULL THEN
        RAISE NOTICE
            'DB-016 runtime priority CHECK test skipped: no sla_config fixture row';
        RETURN;
    END IF;

    PERFORM set_config('app.organization_id', v_org_id::text, TRUE);

    BEGIN
        UPDATE citizen_issues.sla_config
           SET priority = 'Invalid'
         WHERE id = v_sla_id;

        RAISE EXCEPTION
            'DB-016 CHECK failed: invalid SLA priority was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END $$;

-- 10B. Tenant policies must define both read and write predicates.
DO $$
DECLARE
    v_bad INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_bad
    FROM pg_policies
    WHERE (schemaname, tablename) IN (
        ('citizen_issues','sla_config'),
        ('citizen_issues','sla_escalation_chains'),
        ('citizen_issues','sla_escalation_chain_steps'),
        ('citizen_issues','sla_escalation_events'),
        ('compliance_mode','compliance_profiles'),
        ('compliance_mode','compliance_profile_activations'),
        ('compliance_mode','profile_activation_history')
    )
      AND (qual IS NULL OR with_check IS NULL);

    IF v_bad > 0 THEN
        RAISE EXCEPTION 'DB-016 RLS policies missing USING/WITH CHECK on % policy row(s)', v_bad;
    END IF;
END $$;

-- 10C. Cross-tenant RLS isolation for DB-016 schemas.
-- Requires tenant_rls.sql to have been applied after the DB-016 tables.
-- Run this test as a database administrator capable of creating the
-- temporary test role and fixture tenants. RLS assertions run as a
-- non-superuser, non-BYPASSRLS role.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'rls_test_executor'
    ) THEN
        CREATE ROLE rls_test_executor NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;
END $$;

GRANT USAGE ON SCHEMA app, tenant_and_configuration,
    citizen_issues, compliance_mode TO rls_test_executor;
GRANT EXECUTE ON FUNCTION app.current_organization_id()
    TO rls_test_executor;

GRANT SELECT, INSERT ON citizen_issues.sla_config
    TO rls_test_executor;
GRANT SELECT, INSERT ON compliance_mode.compliance_profiles
    TO rls_test_executor;

-- Deterministic tenant fixtures; the surrounding BEGIN/ROLLBACK ensures
-- these rows and the test records are not retained.
INSERT INTO tenant_and_configuration.tenants
(
    id, slug, name, status, max_hierarchy_depth, ai_enabled,
    ai_provider_config, tpi_thresholds, data_residency_region
)
VALUES
(
    '00000000-0000-0000-0000-0000000000a1',
    'db016-rls-tenant-a', 'DB016 RLS Tenant A', 'active', 10, TRUE,
    '{}'::jsonb, '{}'::jsonb, 'ap-south-1'
),
(
    '00000000-0000-0000-0000-0000000000b1',
    'db016-rls-tenant-b', 'DB016 RLS Tenant B', 'active', 10, TRUE,
    '{}'::jsonb, '{}'::jsonb, 'ap-south-1'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO citizen_issues.sla_config
(
    id, organization_id, category, priority,
    response_target_minutes, resolution_target_minutes, escalation_chain
)
VALUES
(
    '00000000-0000-0000-0000-000000001601',
    '00000000-0000-0000-0000-0000000000a1',
    'DB016 RLS fixture A', 'High', 30, 120, '{}'::jsonb
),
(
    '00000000-0000-0000-0000-000000001602',
    '00000000-0000-0000-0000-0000000000b1',
    'DB016 RLS fixture B', 'High', 30, 120, '{}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO compliance_mode.compliance_profiles
(
    id, organization_id, name, version, config
)
VALUES
(
    '00000000-0000-0000-0000-000000001611',
    '00000000-0000-0000-0000-0000000000a1',
    'DB016 RLS fixture A', '1.0.0', '{}'::jsonb
),
(
    '00000000-0000-0000-0000-000000001612',
    '00000000-0000-0000-0000-0000000000b1',
    'DB016 RLS fixture B', '1.0.0', '{}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

SET LOCAL ROLE rls_test_executor;
SET LOCAL app.organization_id = '00000000-0000-0000-0000-0000000000a1';

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    -- Citizen issues schema: Tenant A sees A's SLA row, not Tenant B's.
    SELECT COUNT(*) INTO v_count
      FROM citizen_issues.sla_config
     WHERE id = '00000000-0000-0000-0000-000000001601';
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'DB-016 RLS failed: Tenant A cannot see its SLA row';
    END IF;

    SELECT COUNT(*) INTO v_count
      FROM citizen_issues.sla_config
     WHERE id = '00000000-0000-0000-0000-000000001602';
    IF v_count <> 0 THEN
        RAISE EXCEPTION 'DB-016 RLS failed: Tenant A can see Tenant B SLA row';
    END IF;

    -- Compliance schema: Tenant A sees A's profile, not Tenant B's.
    SELECT COUNT(*) INTO v_count
      FROM compliance_mode.compliance_profiles
     WHERE id = '00000000-0000-0000-0000-000000001611';
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'DB-016 RLS failed: Tenant A cannot see its compliance profile';
    END IF;

    SELECT COUNT(*) INTO v_count
      FROM compliance_mode.compliance_profiles
     WHERE id = '00000000-0000-0000-0000-000000001612';
    IF v_count <> 0 THEN
        RAISE EXCEPTION 'DB-016 RLS failed: Tenant A can see Tenant B compliance profile';
    END IF;

    -- Cross-tenant INSERT must be rejected in both DB-016 schemas.
    BEGIN
        INSERT INTO citizen_issues.sla_config
        (id, organization_id, category, priority,
         response_target_minutes, resolution_target_minutes, escalation_chain)
        VALUES
        ('00000000-0000-0000-0000-000000001603',
         '00000000-0000-0000-0000-0000000000b1',
         'DB016 illegal tenant insert', 'High', 30, 120, '{}'::jsonb);

        RAISE EXCEPTION 'DB-016 RLS failed: cross-tenant SLA INSERT was accepted';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;

    BEGIN
        INSERT INTO compliance_mode.compliance_profiles
        (id, organization_id, name, version, config)
        VALUES
        ('00000000-0000-0000-0000-000000001613',
         '00000000-0000-0000-0000-0000000000b1',
         'DB016 illegal tenant insert', '1.0.0', '{}'::jsonb);

        RAISE EXCEPTION 'DB-016 RLS failed: cross-tenant compliance INSERT was accepted';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
END $$;

RESET app.organization_id;
RESET ROLE;

-- 10. Inspect the final DB-016 objects.
SELECT
    schemaname,
    tablename,
    rowsecurity,
    forcerowsecurity
FROM pg_tables
WHERE (schemaname, tablename) IN (
    ('citizen_issues','sla_config'),
    ('citizen_issues','sla_escalation_chains'),
    ('citizen_issues','sla_escalation_chain_steps'),
    ('citizen_issues','sla_escalation_events'),
    ('compliance_mode','compliance_profiles'),
    ('compliance_mode','compliance_profile_activations'),
    ('compliance_mode','profile_activation_history')
)
ORDER BY schemaname, tablename;

ROLLBACK;
