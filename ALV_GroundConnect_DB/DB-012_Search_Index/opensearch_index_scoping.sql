-- ============================================================
-- DB-012: OPENSEARCH INDEX SCOPING & SEARCH SOURCE REGISTRY
-- ============================================================
-- SRC-01: users, teams, messages, tasks, issues, reports,
--         documents, locations
-- SRC-02: authorization is applied inside the search query
-- SRC-03: tenant-scoped/partitioned search index
-- SRC-04: Indian-language transliteration variants
-- TEN-04: cross-tenant search leakage is a CI release gate
--
-- IMPORTANT:
-- PostgreSQL does not create the physical OpenSearch index.
-- This migration provides the tenant-scoped database contract
-- consumed by the indexing/search service.
-- ============================================================

BEGIN;

DO $$
BEGIN
    IF to_regclass('tenant_and_configuration.tenants') IS NULL THEN
        RAISE EXCEPTION 'DB-012 dependency missing: tenants';
    END IF;

    IF to_regprocedure('app.current_organization_id()') IS NULL THEN
        RAISE EXCEPTION 'DB-012 dependency missing: app.current_organization_id()';
    END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS search_index;

-- One logical OpenSearch index identity per tenant.
CREATE TABLE IF NOT EXISTS search_index.tenant_indexes
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    index_name TEXT NOT NULL,
    index_status TEXT NOT NULL DEFAULT 'active',
    transliteration_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_search_tenant_indexes PRIMARY KEY (id),
    CONSTRAINT uq_search_tenant_indexes_organization UNIQUE (organization_id),
    CONSTRAINT uq_search_tenant_indexes_index_name UNIQUE (index_name),
    CONSTRAINT fk_search_tenant_indexes_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT chk_search_tenant_indexes_index_name
        CHECK (length(btrim(index_name)) > 0),
    CONSTRAINT chk_search_tenant_indexes_status
        CHECK (index_status IN ('active','rebuilding','disabled'))
);

CREATE INDEX IF NOT EXISTS idx_search_tenant_indexes_status
    ON search_index.tenant_indexes (index_status);

-- This is a registry/contract, not a replacement for source tables.
CREATE TABLE IF NOT EXISTS search_index.search_records
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    tenant_index_id UUID NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID NOT NULL,
    search_text TEXT NOT NULL DEFAULT '',
    transliteration_variants TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    authorization_scope JSONB NOT NULL DEFAULT '{}'::JSONB,
    is_searchable BOOLEAN NOT NULL DEFAULT TRUE,
    source_updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    indexed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_search_records PRIMARY KEY (id),
    CONSTRAINT uq_search_records_tenant_resource
        UNIQUE (organization_id, resource_type, resource_id),
    CONSTRAINT fk_search_records_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT fk_search_records_tenant_index
        FOREIGN KEY (tenant_index_id)
        REFERENCES search_index.tenant_indexes(id),
    CONSTRAINT chk_search_records_resource_type
        CHECK (
            resource_type IN (
                'user','team','message','task',
                'issue','report','document','location'
            )
        ),
    CONSTRAINT chk_search_records_search_text
        CHECK (length(search_text) <= 100000),
    CONSTRAINT chk_search_records_transliteration
        CHECK (cardinality(transliteration_variants) <= 100),
    CONSTRAINT chk_search_records_authorization_scope
        CHECK (jsonb_typeof(authorization_scope) = 'object')
);

-- Database-level proof that a record and its tenant index belong
-- to the same organization.
ALTER TABLE search_index.tenant_indexes
    DROP CONSTRAINT IF EXISTS uq_search_tenant_indexes_id_org;

ALTER TABLE search_index.tenant_indexes
    ADD CONSTRAINT uq_search_tenant_indexes_id_org
    UNIQUE (id, organization_id);

ALTER TABLE search_index.search_records
    DROP CONSTRAINT IF EXISTS fk_search_records_tenant_index_scoped;

ALTER TABLE search_index.search_records
    ADD CONSTRAINT fk_search_records_tenant_index_scoped
    FOREIGN KEY (tenant_index_id, organization_id)
    REFERENCES search_index.tenant_indexes (id, organization_id);

CREATE INDEX IF NOT EXISTS idx_search_records_org_type
    ON search_index.search_records (organization_id, resource_type);

CREATE INDEX IF NOT EXISTS idx_search_records_org_updated
    ON search_index.search_records (organization_id, source_updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_records_index_status
    ON search_index.search_records (tenant_index_id, is_searchable);

CREATE INDEX IF NOT EXISTS idx_search_records_transliteration
    ON search_index.search_records USING GIN (transliteration_variants);

CREATE INDEX IF NOT EXISTS idx_search_records_authorization_scope
    ON search_index.search_records USING GIN (authorization_scope);

-- PostgreSQL-side tenant isolation.
ALTER TABLE search_index.tenant_indexes ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_index.tenant_indexes FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS search_tenant_indexes_tenant_isolation
    ON search_index.tenant_indexes;

CREATE POLICY search_tenant_indexes_tenant_isolation
ON search_index.tenant_indexes
AS PERMISSIVE
FOR ALL
USING (organization_id = app.current_organization_id())
WITH CHECK (organization_id = app.current_organization_id());

ALTER TABLE search_index.search_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_index.search_records FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS search_records_tenant_isolation
    ON search_index.search_records;

CREATE POLICY search_records_tenant_isolation
ON search_index.search_records
AS PERMISSIVE
FOR ALL
USING (organization_id = app.current_organization_id())
WITH CHECK (organization_id = app.current_organization_id());

-- Feed consumed by the indexing service.
CREATE OR REPLACE VIEW search_index.search_index_feed AS
SELECT
    sr.id,
    sr.organization_id,
    ti.index_name,
    sr.resource_type,
    sr.resource_id,
    sr.search_text,
    sr.transliteration_variants,
    sr.authorization_scope,
    sr.is_searchable,
    sr.source_updated_at,
    sr.indexed_at
FROM search_index.search_records sr
JOIN search_index.tenant_indexes ti
  ON ti.id = sr.tenant_index_id
 AND ti.organization_id = sr.organization_id
WHERE sr.is_searchable = TRUE
  AND ti.index_status = 'active';

-- Registers/updates a tenant-scoped searchable resource.
-- Does not call OpenSearch.
CREATE OR REPLACE FUNCTION search_index.register_search_record
(
    p_organization_id UUID,
    p_resource_type TEXT,
    p_resource_id UUID,
    p_search_text TEXT,
    p_transliteration_variants TEXT[] DEFAULT ARRAY[]::TEXT[],
    p_authorization_scope JSONB DEFAULT '{}'::JSONB
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
DECLARE
    v_context UUID;
    v_tenant_index_id UUID;
    v_id UUID;
BEGIN
    v_context := app.require_organization_context();

    IF v_context <> p_organization_id THEN
        RAISE EXCEPTION
            'DB-012: organization context does not match search record tenant';
    END IF;

    IF p_resource_type NOT IN (
        'user','team','message','task',
        'issue','report','document','location'
    ) THEN
        RAISE EXCEPTION
            'DB-012: unsupported resource type: %', p_resource_type;
    END IF;

    IF p_authorization_scope IS NULL
       OR jsonb_typeof(p_authorization_scope) <> 'object' THEN
        RAISE EXCEPTION
            'DB-012: authorization_scope must be a JSON object';
    END IF;

    SELECT id INTO v_tenant_index_id
    FROM search_index.tenant_indexes
    WHERE organization_id = p_organization_id
      AND index_status <> 'disabled';

    IF v_tenant_index_id IS NULL THEN
        RAISE EXCEPTION
            'DB-012: no active tenant search index is registered';
    END IF;

    INSERT INTO search_index.search_records
    (
        organization_id,
        tenant_index_id,
        resource_type,
        resource_id,
        search_text,
        transliteration_variants,
        authorization_scope,
        source_updated_at,
        updated_at
    )
    VALUES
    (
        p_organization_id,
        v_tenant_index_id,
        p_resource_type,
        p_resource_id,
        COALESCE(p_search_text, ''),
        COALESCE(p_transliteration_variants, ARRAY[]::TEXT[]),
        p_authorization_scope,
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT (organization_id, resource_type, resource_id)
    DO UPDATE SET
        tenant_index_id = EXCLUDED.tenant_index_id,
        search_text = EXCLUDED.search_text,
        transliteration_variants = EXCLUDED.transliteration_variants,
        authorization_scope = EXCLUDED.authorization_scope,
        source_updated_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;

COMMIT;

;

