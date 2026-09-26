-- ================================================================
-- FILE: tenant_rls.sql
-- PURPOSE:
--   PostgreSQL Row Level Security for tenant isolation
--
-- REQUIREMENTS:
--   TEN-01  Tenant identity from authenticated session context
--   TEN-02  Tenant isolation at database level
--   TEN-03  Defence-in-depth against cross-tenant access
--   TEN-04  Fail closed when tenant context is missing
--
-- IMPORTANT:
--   The application authentication layer must establish:
--
--       SET LOCAL app.organization_id = '<authenticated-tenant-uuid>';
--
--   The value MUST come from the authenticated session.
--   Request parameters must NEVER be used directly as the tenant
--   security context.
--
--   This script does not implement authentication itself.
-- ================================================================

-- ================================================================
-- MIGRATION / DBA OPERATIONS NOTE
-- ================================================================
-- This migration enables and FORCEs Row Level Security.
--
-- FORCE ROW LEVEL SECURITY means the table owner is also subject
-- to the table's RLS policies.
--
-- Therefore, any subsequent migration, maintenance, or DBA SQL
-- that reads/writes tenant-owned rows must establish the trusted
-- tenant context before the statement, for example:
--
--     SET LOCAL app.organization_id = '<authenticated-tenant-uuid>';
--
-- SET LOCAL is preferred so the context is limited to the current
-- transaction.
--
-- Migration/DBA roles that intentionally need to operate across
-- tenants must either:
--   1. execute tenant-scoped work with SET LOCAL
--      app.organization_id, or
--   2. use a controlled role with BYPASSRLS privilege.
--
-- BYPASSRLS must be restricted to explicitly authorized operational
-- roles. Application roles must not receive BYPASSRLS merely to
-- avoid tenant isolation.
--
-- A missing app.organization_id context fails closed through the
-- RLS policies and must not be replaced with a request parameter.
-- ================================================================

CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.current_organization_id()
RETURNS UUID
LANGUAGE sql
STABLE
AS $$
    SELECT NULLIF(
        current_setting('app.organization_id', TRUE),
        ''
    )::UUID;
$$;

CREATE OR REPLACE FUNCTION app.require_organization_context()
RETURNS UUID
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_organization_id UUID;
BEGIN
    v_organization_id := app.current_organization_id();

    IF v_organization_id IS NULL THEN
        RAISE EXCEPTION
            'TEN-01: authenticated organization context is required';
    END IF;

    RETURN v_organization_id;
END;
$$;

DO $$
DECLARE
    r RECORD;
    v_policy_name TEXT;
BEGIN
    FOR r IN
        SELECT
            n.nspname AS schema_name,
            c.relname AS table_name
        FROM pg_class c
        JOIN pg_namespace n
            ON n.oid = c.relnamespace
        JOIN pg_attribute a
            ON a.attrelid = c.oid
        WHERE c.relkind = 'r'
          AND a.attname = 'organization_id'
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND a.attnotnull = TRUE
          AND n.nspname NOT IN (
                'pg_catalog',
                'information_schema'
          )
          AND n.nspname <> 'app'
          AND NOT (
                n.nspname = 'tenant_and_configuration'
                AND c.relname = 'tenants'
          )
          AND NOT (
                n.nspname = 'prohibited_attribute_firewall'
                AND c.relname = 'prohibited_terms'
          )
        GROUP BY
            n.nspname,
            c.relname
        ORDER BY
            n.nspname,
            c.relname
    LOOP

        EXECUTE format(
            'ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',
            r.schema_name,
            r.table_name
        );

        EXECUTE format(
            'ALTER TABLE %I.%I FORCE ROW LEVEL SECURITY',
            r.schema_name,
            r.table_name
        );

        v_policy_name :=
            'tenant_isolation_' || r.table_name;

        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON %I.%I',
            v_policy_name,
            r.schema_name,
            r.table_name
        );

        EXECUTE format(
            $policy$
            CREATE POLICY %I
            ON %I.%I
            AS PERMISSIVE
            FOR ALL
            USING (
                organization_id = app.current_organization_id()
            )
            WITH CHECK (
                organization_id = app.current_organization_id()
            )
            $policy$,
            v_policy_name,
            r.schema_name,
            r.table_name
        );

    END LOOP;
END;
$$;

ALTER TABLE tenant_and_configuration.tenants
ENABLE ROW LEVEL SECURITY;

ALTER TABLE tenant_and_configuration.tenants
FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_registry_isolation
ON tenant_and_configuration.tenants;

CREATE POLICY tenant_registry_isolation
ON tenant_and_configuration.tenants
AS PERMISSIVE
FOR ALL
USING (
    id = app.current_organization_id()
)
WITH CHECK (
    id = app.current_organization_id()
);

ALTER TABLE prohibited_attribute_firewall.prohibited_terms
ENABLE ROW LEVEL SECURITY;

ALTER TABLE prohibited_attribute_firewall.prohibited_terms
FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_prohibited_terms
ON prohibited_attribute_firewall.prohibited_terms;

DROP POLICY IF EXISTS tenant_write_prohibited_terms
ON prohibited_attribute_firewall.prohibited_terms;

DROP POLICY IF EXISTS tenant_update_prohibited_terms
ON prohibited_attribute_firewall.prohibited_terms;

DROP POLICY IF EXISTS tenant_delete_prohibited_terms
ON prohibited_attribute_firewall.prohibited_terms;

CREATE POLICY tenant_isolation_prohibited_terms
ON prohibited_attribute_firewall.prohibited_terms
AS PERMISSIVE
FOR SELECT
USING (
    organization_id IS NULL
    OR organization_id = app.current_organization_id()
);

CREATE POLICY tenant_write_prohibited_terms
ON prohibited_attribute_firewall.prohibited_terms
AS PERMISSIVE
FOR INSERT
WITH CHECK (
    organization_id = app.current_organization_id()
);

CREATE POLICY tenant_update_prohibited_terms
ON prohibited_attribute_firewall.prohibited_terms
AS PERMISSIVE
FOR UPDATE
USING (
    organization_id = app.current_organization_id()
)
WITH CHECK (
    organization_id = app.current_organization_id()
);

CREATE POLICY tenant_delete_prohibited_terms
ON prohibited_attribute_firewall.prohibited_terms
AS PERMISSIVE
FOR DELETE
USING (
    organization_id = app.current_organization_id()
);

SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attnotnull AS organization_id_not_null,
    c.relrowsecurity AS rls_enabled,
    c.relforcerowsecurity AS force_rls_enabled
FROM pg_class c
JOIN pg_namespace n
    ON n.oid = c.relnamespace
JOIN pg_attribute a
    ON a.attrelid = c.oid
WHERE c.relkind = 'r'
  AND a.attname = 'organization_id'
  AND a.attnum > 0
  AND NOT a.attisdropped
  AND n.nspname NOT IN (
        'pg_catalog',
        'information_schema',
        'app'
  )
ORDER BY
    n.nspname,
    c.relname;

SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies
WHERE schemaname NOT IN (
    'pg_catalog',
    'information_schema'
)
AND (
    policyname LIKE 'tenant_isolation_%'
    OR policyname = 'tenant_registry_isolation'
    OR policyname LIKE 'tenant_write_%'
    OR policyname LIKE 'tenant_update_%'
    OR policyname LIKE 'tenant_delete_%'
)
ORDER BY
    schemaname,
    tablename,
    policyname;

SELECT
    COUNT(*) FILTER (
        WHERE c.relrowsecurity = TRUE
    ) AS tables_with_rls,
    COUNT(*) FILTER (
        WHERE c.relforcerowsecurity = TRUE
    ) AS tables_with_force_rls,
    COUNT(*) AS tenant_tables
FROM pg_class c
JOIN pg_namespace n
    ON n.oid = c.relnamespace
JOIN pg_attribute a
    ON a.attrelid = c.oid
WHERE c.relkind = 'r'
  AND a.attname = 'organization_id'
  AND a.attnum > 0
  AND NOT a.attisdropped
  AND a.attnotnull = TRUE
  AND n.nspname NOT IN (
        'pg_catalog',
        'information_schema',
        'app'
  )
  AND NOT (
        n.nspname = 'prohibited_attribute_firewall'
        AND c.relname = 'prohibited_terms'
  )
  AND NOT (
        n.nspname = 'tenant_and_configuration'
        AND c.relname = 'tenants'
  );

-- ================================================================
-- END OF tenant_rls.sql
-- ================================================================
