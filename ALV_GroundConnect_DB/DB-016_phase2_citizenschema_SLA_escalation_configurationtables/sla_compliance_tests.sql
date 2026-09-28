-- ============================================================
-- DB-016 VERIFICATION / TEST SCRIPT
-- Run AFTER db016_sla_compliance.sql and the existing audit migration.
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
