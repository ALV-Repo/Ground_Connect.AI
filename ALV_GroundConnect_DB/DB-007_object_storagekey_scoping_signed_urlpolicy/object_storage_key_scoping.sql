-- ============================================================
-- object_storage_key_scoping.sql
-- OBJECT-STORAGE KEY SCOPING & SIGNED-URL POLICY
-- ============================================================
--
-- Requirement:
--   Object-storage keys and signed URLs must be tenant- and
--   resource-scoped with expiry <= 15 minutes.
--
-- Design:
--   1. Existing tasks_field_reports.evidence_media remains the
--      authoritative resource record.
--   2. Every evidence-media object-storage key must be scoped as:
--        tenant/<organization_id>/evidence/<evidence_media_id>/...
--   3. original_metadata_key, when present, follows the same scope.
--   4. Signed URL issuance is recorded in a dedicated table.
--   5. Signed URL records are bound to both organization_id and
--      evidence_media_id using a composite foreign key.
--   6. Database CHECK constraints enforce a maximum lifetime of
--      15 minutes.
--   7. The actual signed URL is intentionally NOT stored.
--      The application/object-storage layer generates the URL
--      from the validated issuance record.
--
-- This is an incremental migration.
-- It does not recreate or duplicate evidence_media.
-- It does not modify the existing RLS migration.
-- ============================================================

BEGIN;

-- ============================================================
-- 1. DEPENDENCY VALIDATION
-- ============================================================

DO $$
BEGIN
    IF to_regclass('tenant_and_configuration.tenants') IS NULL THEN
        RAISE EXCEPTION
            'Required table tenant_and_configuration.tenants does not exist';
    END IF;

    IF to_regclass('tasks_field_reports.evidence_media') IS NULL THEN
        RAISE EXCEPTION
            'Required table tasks_field_reports.evidence_media does not exist';
    END IF;
END
$$;


-- ============================================================
-- 2. OBJECT STORAGE SECURITY SCHEMA
-- ============================================================

CREATE SCHEMA IF NOT EXISTS object_storage_security;


-- ============================================================
-- 3. COMPOSITE KEY FOR TENANT-SCOPED RESOURCE REFERENCES
-- ============================================================
--
-- evidence_media.id is already the resource identifier.
-- The composite unique constraint is required so a signed URL
-- record can prove that the resource belongs to the same tenant.
--
-- This does NOT duplicate the evidence_media table.
-- ============================================================

ALTER TABLE tasks_field_reports.evidence_media
    ADD CONSTRAINT uq_evidence_media_organization_id_id
    UNIQUE (organization_id, id);


-- ============================================================
-- 4. TENANT- AND RESOURCE-SCOPED OBJECT KEY POLICY
-- ============================================================
--
-- Required key format:
--
--   tenant/<organization_id>/evidence/<evidence_media_id>/...
--
-- Example:
--
--   tenant/11111111-1111-1111-1111-111111111111/
--   evidence/22222222-2222-2222-2222-222222222222/image.jpg
--
-- The prefix binds the object to:
--   organization_id
--   evidence_media.id
--
-- A suffix is allowed so providers can use filenames, hashes,
-- extensions, or additional object path components.
-- ============================================================

ALTER TABLE tasks_field_reports.evidence_media
    ADD CONSTRAINT chk_evidence_media_object_storage_key_scope
    CHECK (
        object_storage_key =
            'tenant/' ||
            organization_id::text ||
            '/evidence/' ||
            id::text ||
            '/'
            || substring(object_storage_key
                FROM length(
                    'tenant/' ||
                    organization_id::text ||
                    '/evidence/' ||
                    id::text ||
                    '/'
                ) + 1
            )
        AND object_storage_key LIKE
            'tenant/' ||
            organization_id::text ||
            '/evidence/' ||
            id::text ||
            '/%'
    );


-- ============================================================
-- 5. ORIGINAL-METADATA OBJECT KEY POLICY
-- ============================================================
--
-- original_metadata_key is also an object-storage key.
-- When populated, it must use the same tenant/resource scope.
-- ============================================================

ALTER TABLE tasks_field_reports.evidence_media
    ADD CONSTRAINT chk_evidence_media_original_metadata_key_scope
    CHECK (
        original_metadata_key IS NULL
        OR
        original_metadata_key LIKE
            'tenant/' ||
            organization_id::text ||
            '/evidence/' ||
            id::text ||
            '/%'
    );


-- ============================================================
-- 6. INDEX FOR TENANT/RESOURCE OBJECT LOOKUP
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_evidence_media_org_id_id
    ON tasks_field_reports.evidence_media
    (
        organization_id,
        id
    );


CREATE INDEX IF NOT EXISTS idx_evidence_media_org_object_key
    ON tasks_field_reports.evidence_media
    (
        organization_id,
        object_storage_key
    );


-- ============================================================
-- 7. SIGNED URL ISSUANCE TABLE
-- ============================================================
--
-- Stores authorization/issuance metadata only.
-- The signed URL itself is deliberately not persisted.
--
-- resource_id is represented by evidence_media_id because
-- evidence_media is the existing object-storage resource in
-- the current schema.
-- ============================================================

CREATE TABLE IF NOT EXISTS object_storage_security.signed_url_issuance
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    evidence_media_id UUID NOT NULL,

    object_storage_key TEXT NOT NULL,

    operation VARCHAR(10) NOT NULL DEFAULT 'GET',

    issued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    expires_at TIMESTAMPTZ NOT NULL,

    requested_by UUID NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_signed_url_issuance
        PRIMARY KEY (id),

    CONSTRAINT fk_signed_url_issuance_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_signed_url_issuance_resource
        FOREIGN KEY (organization_id, evidence_media_id)
        REFERENCES tasks_field_reports.evidence_media
            (organization_id, id),

    CONSTRAINT chk_signed_url_operation
        CHECK (
            operation IN ('GET', 'PUT')
        ),

    CONSTRAINT chk_signed_url_expiry_after_issue
        CHECK (
            expires_at > issued_at
        ),

    CONSTRAINT chk_signed_url_max_15_minutes
        CHECK (
            expires_at <= issued_at + INTERVAL '15 minutes'
        ),

    CONSTRAINT chk_signed_url_key_scope
        CHECK (
            object_storage_key =
                'tenant/' ||
                organization_id::text ||
                '/evidence/' ||
                evidence_media_id::text ||
                '/'
                || substring(
                    object_storage_key
                    FROM length(
                        'tenant/' ||
                        organization_id::text ||
                        '/evidence/' ||
                        evidence_media_id::text ||
                        '/'
                    ) + 1
                )
            AND object_storage_key LIKE
                'tenant/' ||
                organization_id::text ||
                '/evidence/' ||
                evidence_media_id::text ||
                '/%'
        )
);


-- ============================================================
-- 8. SIGNED URL INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_signed_url_issuance_org_resource
    ON object_storage_security.signed_url_issuance
    (
        organization_id,
        evidence_media_id
    );


CREATE INDEX IF NOT EXISTS idx_signed_url_issuance_org_expiry
    ON object_storage_security.signed_url_issuance
    (
        organization_id,
        expires_at
    );


CREATE INDEX IF NOT EXISTS idx_signed_url_issuance_org_key
    ON object_storage_security.signed_url_issuance
    (
        organization_id,
        object_storage_key
    );


-- ============================================================
-- 9. EXPIRED SIGNED URL CLEANUP SUPPORT
-- ============================================================
--
-- Allows efficient removal/archival of expired issuance records.
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_signed_url_issuance_expires_at
    ON object_storage_security.signed_url_issuance
    (
        expires_at
    );


-- ============================================================
-- 10. POLICY FUNCTION FOR SIGNED-URL EXPIRY
-- ============================================================
--
-- Central validation function for application/service code.
-- The table CHECK constraint remains the final database guard.
-- ============================================================

CREATE OR REPLACE FUNCTION object_storage_security.validate_signed_url_expiry
(
    p_issued_at  TIMESTAMPTZ,
    p_expires_at TIMESTAMPTZ
)
RETURNS BOOLEAN
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    IF p_issued_at IS NULL OR p_expires_at IS NULL THEN
        RETURN FALSE;
    END IF;

    IF p_expires_at <= p_issued_at THEN
        RETURN FALSE;
    END IF;

    IF p_expires_at > p_issued_at + INTERVAL '15 minutes' THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$;


-- ============================================================
-- 11. SIGNED URL ISSUANCE FUNCTION
-- ============================================================
--
-- This function provides a single database-side issuance path.
--
-- It validates:
--   - tenant/resource ownership
--   - exact object-storage key
--   - operation
--   - expiry window <= 15 minutes
--
-- It returns the issuance id and expiry timestamp.
-- The signed URL is generated by the object-storage/application
-- layer and is never stored in this database table.
-- ============================================================

CREATE OR REPLACE FUNCTION object_storage_security.register_signed_url
(
    p_organization_id  UUID,
    p_evidence_media_id UUID,
    p_object_storage_key TEXT,
    p_operation VARCHAR(10),
    p_issued_at TIMESTAMPTZ,
    p_expires_at TIMESTAMPTZ,
    p_requested_by UUID DEFAULT NULL
)
RETURNS TABLE
(
    issuance_id UUID,
    issued_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_resource_key TEXT;
BEGIN
    IF NOT object_storage_security.validate_signed_url_expiry(
        p_issued_at,
        p_expires_at
    ) THEN
        RAISE EXCEPTION
            'Signed URL expiry must be after issued_at and no more than 15 minutes';
    END IF;

    IF p_operation NOT IN ('GET', 'PUT') THEN
        RAISE EXCEPTION
            'Unsupported signed URL operation: %. Allowed operations: GET, PUT',
            p_operation;
    END IF;

    SELECT em.object_storage_key
      INTO v_resource_key
      FROM tasks_field_reports.evidence_media em
     WHERE em.organization_id = p_organization_id
       AND em.id = p_evidence_media_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Evidence resource % does not belong to organization %',
            p_evidence_media_id,
            p_organization_id;
    END IF;

    IF v_resource_key <> p_object_storage_key THEN
        RAISE EXCEPTION
            'Object-storage key does not match the requested tenant/resource';
    END IF;

    RETURN QUERY
    INSERT INTO object_storage_security.signed_url_issuance
    (
        organization_id,
        evidence_media_id,
        object_storage_key,
        operation,
        issued_at,
        expires_at,
        requested_by
    )
    VALUES
    (
        p_organization_id,
        p_evidence_media_id,
        p_object_storage_key,
        p_operation,
        p_issued_at,
        p_expires_at,
        p_requested_by
    )
    RETURNING
        id,
        signed_url_issuance.issued_at,
        signed_url_issuance.expires_at;
END;
$$;


-- ============================================================
-- 12. COMMENTS / IMPLEMENTATION CONTRACT
-- ============================================================

COMMENT ON SCHEMA object_storage_security IS
    'Tenant/resource-scoped object-storage security controls and signed-URL issuance policy.';

COMMENT ON TABLE object_storage_security.signed_url_issuance IS
    'Records signed URL issuance metadata. URLs themselves are not stored. Expiry is limited to 15 minutes by database constraint.';

COMMENT ON COLUMN object_storage_security.signed_url_issuance.organization_id IS
    'Tenant identifier. Must match the evidence_media resource tenant.';

COMMENT ON COLUMN object_storage_security.signed_url_issuance.evidence_media_id IS
    'Resource identifier. References the tenant-scoped evidence_media resource.';

COMMENT ON COLUMN object_storage_security.signed_url_issuance.object_storage_key IS
    'Tenant/resource-scoped storage key. Must use tenant/<organization_id>/evidence/<evidence_media_id>/... format.';

COMMENT ON COLUMN object_storage_security.signed_url_issuance.expires_at IS
    'Signed URL expiry timestamp. Database policy limits lifetime to 15 minutes from issued_at.';

COMMENT ON FUNCTION object_storage_security.register_signed_url(
    UUID, UUID, TEXT, VARCHAR, TIMESTAMPTZ, TIMESTAMPTZ, UUID
) IS
    'Registers a tenant/resource-scoped signed URL issuance after validating ownership, object key and maximum 15-minute expiry.';


-- ============================================================
-- 13. VERIFICATION QUERIES
-- ============================================================
--
-- These are read-only verification queries. They do not modify
-- application data.
-- ============================================================

SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    con.conname AS constraint_name,
    pg_get_constraintdef(con.oid) AS definition
FROM pg_constraint con
JOIN pg_class c
  ON c.oid = con.conrelid
JOIN pg_namespace n
  ON n.oid = c.relnamespace
WHERE n.nspname = 'tasks_field_reports'
  AND c.relname = 'evidence_media'
  AND con.conname IN
      (
          'uq_evidence_media_organization_id_id',
          'chk_evidence_media_object_storage_key_scope',
          'chk_evidence_media_original_metadata_key_scope'
      )
ORDER BY con.conname;


SELECT
    table_schema,
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'object_storage_security'
  AND table_name = 'signed_url_issuance'
ORDER BY ordinal_position;


SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname IN
    (
        'tasks_field_reports',
        'object_storage_security'
    )
  AND (
        indexname LIKE '%evidence_media%'
        OR indexname LIKE '%signed_url%'
      )
ORDER BY schemaname, indexname;


SELECT
    conname,
    pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid =
      'object_storage_security.signed_url_issuance'::regclass
ORDER BY conname;


COMMIT;

-- ============================================================
-- END OF object_storage_key_scoping.sql
-- ============================================================
