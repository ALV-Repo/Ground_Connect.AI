-- ============================================================
-- append_only_hash_chained_audit.sql
-- APPEND-ONLY HASH-CHAINED AUDIT, CHECKPOINTS, RETENTION,
-- LEGAL HOLD, SEARCH AND EXPORT CONTROLS
-- ============================================================
--
-- AUD-01..AUD-05
--
-- This is an incremental migration over audit_trail.audit_events
-- and audit_trail.audit_checkpoints created by 12_audit_trail.sql.
--
-- It does not recreate audit_events or audit_checkpoints.
--
-- Security model:
--   * Audit events are inserted only through append_audit_event().
--   * UPDATE/DELETE are rejected by a database trigger.
--   * UPDATE/DELETE privileges are revoked from PUBLIC.
--   * Direct INSERT is revoked from PUBLIC; INSERT is performed by
--     the controlled SECURITY DEFINER append function.
--   * Each event contains SHA-256(prev_hash + canonical event data).
--   * Chain verification recomputes every hash and predecessor link.
--   * Checkpoints store a chain hash and external storage reference.
--   * Retention is tenant-policy driven.
--   * Legal holds prevent retention archival/deletion while active.
--   * Because the audit table is strictly append-only, this migration
--     does NOT provide a DELETE-based purge. Retention processing is
--     represented by controlled retention candidates/checkpoints and
--     external archival/deletion under the organization's retention
--     and legal-hold process.
--   * Search/export execute only through permission-controlled
--     SECURITY DEFINER functions and each operation creates an audit
--     event.
--
-- IMPORTANT:
-- PostgreSQL superusers/BYPASSRLS users are inherently trusted
-- database administrators and can disable triggers or alter database
-- objects. No PostgreSQL migration can cryptographically prevent a
-- superuser from modifying the database itself. The controls below
-- prevent ordinary roles, application roles and table owners from
-- updating/deleting audit rows through normal SQL privileges.
-- ============================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- 1. DEPENDENCY VALIDATION
-- ============================================================

DO $$
BEGIN
    IF to_regclass('audit_trail.audit_events') IS NULL THEN
        RAISE EXCEPTION
            'Required table audit_trail.audit_events does not exist';
    END IF;

    IF to_regclass('audit_trail.audit_checkpoints') IS NULL THEN
        RAISE EXCEPTION
            'Required table audit_trail.audit_checkpoints does not exist';
    END IF;

    IF to_regclass('tenant_and_configuration.tenants') IS NULL THEN
        RAISE EXCEPTION
            'Required table tenant_and_configuration.tenants does not exist';
    END IF;
END
$$;


-- ============================================================
-- 2. HASH-CHAIN BASELINE CONSTRAINTS
-- ============================================================

ALTER TABLE audit_trail.audit_events
    ADD CONSTRAINT chk_audit_events_prev_hash_sha256
    CHECK (
        prev_hash ~ '^[0-9a-f]{64}$'
    );

ALTER TABLE audit_trail.audit_events
    ADD CONSTRAINT chk_audit_events_hash_sha256
    CHECK (
        hash ~ '^[0-9a-f]{64}$'
    );


-- ============================================================
-- 3. RETENTION POLICY
-- ============================================================
--
-- Tenant-specific retention policy.
--
-- retention_days:
--   Number of days audit records are retained before they become
--   eligible for controlled purge.
--
-- A legal hold always overrides ordinary retention.
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_trail.audit_retention_policies
(
    organization_id UUID NOT NULL,

    retention_days INTEGER NOT NULL DEFAULT 2555,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_by UUID NULL,

    CONSTRAINT pk_audit_retention_policies
        PRIMARY KEY (organization_id),

    CONSTRAINT fk_audit_retention_policies_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT chk_audit_retention_days
        CHECK (retention_days >= 1)
);

CREATE INDEX IF NOT EXISTS idx_audit_retention_policies_updated_at
    ON audit_trail.audit_retention_policies (updated_at);


-- ============================================================
-- 4. LEGAL-HOLD REGISTRY
-- ============================================================
--
-- Legal holds are separate from audit_events because audit events
-- themselves are immutable. A hold can therefore be applied after
-- an audit event was created without UPDATE-ing that event.
--
-- Scope:
--   resource_type + resource_id
--
-- NULL resource_id means the hold applies to the whole tenant.
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_trail.audit_legal_holds
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    resource_type TEXT NULL,

    resource_id UUID NULL,

    reason TEXT NOT NULL,

    placed_by UUID NOT NULL,

    placed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    released_by UUID NULL,

    released_at TIMESTAMPTZ NULL,

    CONSTRAINT pk_audit_legal_holds
        PRIMARY KEY (id),

    CONSTRAINT fk_audit_legal_holds_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT chk_audit_legal_hold_reason
        CHECK (length(btrim(reason)) > 0),

    CONSTRAINT chk_audit_legal_hold_release
        CHECK (
            (released_at IS NULL AND released_by IS NULL)
            OR
            (released_at IS NOT NULL AND released_by IS NOT NULL)
        ),

    CONSTRAINT chk_audit_legal_hold_release_after_place
        CHECK (
            released_at IS NULL
            OR released_at >= placed_at
        )
);

CREATE INDEX IF NOT EXISTS idx_audit_legal_holds_org_resource
    ON audit_trail.audit_legal_holds
    (
        organization_id,
        resource_type,
        resource_id
    );

CREATE INDEX IF NOT EXISTS idx_audit_legal_holds_active
    ON audit_trail.audit_legal_holds
    (
        organization_id,
        resource_type,
        resource_id,
        released_at
    );


-- ============================================================
-- 5. LEGAL-HOLD CHECK FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.audit_event_is_on_legal_hold
(
    p_organization_id UUID,
    p_resource_type TEXT,
    p_resource_id UUID
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS
    (
        SELECT 1
        FROM audit_trail.audit_legal_holds h
        WHERE h.organization_id = p_organization_id
          AND h.released_at IS NULL
          AND
          (
              h.resource_id IS NULL
              OR
              (
                  h.resource_type = p_resource_type
                  AND h.resource_id = p_resource_id
              )
          )
    );
$$;


-- ============================================================
-- 6. CANONICAL HASH FUNCTION
-- ============================================================
--
-- SHA-256 input is deterministic JSON plus the predecessor hash.
-- PostgreSQL jsonb output is canonicalized for equivalent JSONB
-- values, making the hash reproducible during verification.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.audit_event_hash
(
    p_prev_hash TEXT,
    p_id UUID,
    p_organization_id UUID,
    p_seq BIGINT,
    p_actor_id UUID,
    p_acting_for_id UUID,
    p_session_id UUID,
    p_action_type TEXT,
    p_resource_type TEXT,
    p_resource_id UUID,
    p_payload JSONB,
    p_ip_hash TEXT,
    p_legal_hold BOOLEAN,
    p_created_at TIMESTAMPTZ
)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT encode(
        digest(
            convert_to(
                p_prev_hash ||
                '|' ||
                jsonb_build_object(
                    'id', p_id,
                    'organization_id', p_organization_id,
                    'seq', p_seq,
                    'actor_id', p_actor_id,
                    'acting_for_id', p_acting_for_id,
                    'session_id', p_session_id,
                    'action_type', p_action_type,
                    'resource_type', p_resource_type,
                    'resource_id', p_resource_id,
                    'payload', p_payload,
                    'ip_hash', p_ip_hash,
                    'legal_hold', p_legal_hold,
                    'created_at', p_created_at
                )::text,
                'UTF8'
            ),
            'sha256'
        ),
        'hex'
    );
$$;


-- ============================================================
-- 7. APPEND-ONLY ENFORCEMENT TRIGGER
-- ============================================================
--
-- No UPDATE or DELETE operation is allowed on audit_events,
-- regardless of normal table privileges.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.prevent_audit_event_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'audit_trail.audit_events is append-only: UPDATE and DELETE are prohibited';
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_events_append_only
    ON audit_trail.audit_events;

CREATE TRIGGER trg_audit_events_append_only
BEFORE UPDATE OR DELETE
ON audit_trail.audit_events
FOR EACH ROW
EXECUTE FUNCTION audit_trail.prevent_audit_event_mutation();


-- ============================================================
-- 8. PREVENT MANUAL HASH/SEQUENCE TAMPERING ON INSERT
-- ============================================================
--
-- Direct INSERT is not granted to ordinary roles. This trigger
-- also rejects inserts whose hash does not match the canonical
-- hash formula.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.validate_audit_event_hash()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_expected_hash TEXT;
BEGIN
    v_expected_hash := audit_trail.audit_event_hash(
        NEW.prev_hash,
        NEW.id,
        NEW.organization_id,
        NEW.seq,
        NEW.actor_id,
        NEW.acting_for_id,
        NEW.session_id,
        NEW.action_type,
        NEW.resource_type,
        NEW.resource_id,
        NEW.payload,
        NEW.ip_hash,
        NEW.legal_hold,
        NEW.created_at
    );

    IF NEW.hash <> v_expected_hash THEN
        RAISE EXCEPTION
            'Invalid audit hash for sequence %',
            NEW.seq;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_events_validate_hash
    ON audit_trail.audit_events;

CREATE TRIGGER trg_audit_events_validate_hash
BEFORE INSERT
ON audit_trail.audit_events
FOR EACH ROW
EXECUTE FUNCTION audit_trail.validate_audit_event_hash();


-- ============================================================
-- 9. CONTROLLED APPEND FUNCTION
-- ============================================================
--
-- Serializes audit-chain writes using a transaction-scoped
-- advisory lock.
--
-- First event:
--   prev_hash = 64 zeroes
--
-- Subsequent event:
--   prev_hash = hash of the immediately preceding sequence.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.append_audit_event
(
    p_organization_id UUID,
    p_actor_id UUID,
    p_acting_for_id UUID,
    p_session_id UUID,
    p_action_type TEXT,
    p_resource_type TEXT,
    p_resource_id UUID,
    p_payload JSONB,
    p_ip_hash TEXT,
    p_legal_hold BOOLEAN DEFAULT FALSE,
    p_created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = audit_trail, pg_catalog
AS $$
DECLARE
    v_id UUID := gen_random_uuid();
    v_seq BIGINT;
    v_prev_hash TEXT;
    v_hash TEXT;
BEGIN
    IF p_organization_id IS NULL THEN
        RAISE EXCEPTION 'organization_id is required';
    END IF;

    IF p_action_type IS NULL OR length(btrim(p_action_type)) = 0 THEN
        RAISE EXCEPTION 'action_type is required';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'audit-chain:' || p_organization_id::text,
            0
        )
    );

    SELECT nextval(
        pg_get_serial_sequence(
            'audit_trail.audit_events',
            'seq'
        )
    )
      INTO v_seq;

    SELECT COALESCE(
        (
            SELECT ae.hash
            FROM audit_trail.audit_events ae
            WHERE ae.organization_id = p_organization_id
            ORDER BY ae.seq DESC
            LIMIT 1
        ),
        repeat('0', 64)
    )
    INTO v_prev_hash;

    v_hash := audit_trail.audit_event_hash(
        v_prev_hash,
        v_id,
        p_organization_id,
        v_seq,
        p_actor_id,
        p_acting_for_id,
        p_session_id,
        p_action_type,
        p_resource_type,
        p_resource_id,
        p_payload,
        p_ip_hash,
        p_legal_hold,
        p_created_at
    );

    INSERT INTO audit_trail.audit_events
    (
        id,
        organization_id,
        seq,
        prev_hash,
        hash,
        actor_id,
        acting_for_id,
        session_id,
        action_type,
        resource_type,
        resource_id,
        payload,
        ip_hash,
        legal_hold,
        created_at
    )
    VALUES
    (
        v_id,
        p_organization_id,
        v_seq,
        v_prev_hash,
        v_hash,
        p_actor_id,
        p_acting_for_id,
        p_session_id,
        p_action_type,
        p_resource_type,
        p_resource_id,
        p_payload,
        p_ip_hash,
        p_legal_hold,
        p_created_at
    );

    RETURN v_id;
END;
$$;


-- ============================================================
-- 10. RETENTION CANDIDATE FUNCTION
-- ============================================================
--
-- The audit table is strictly append-only, so retention cannot be
-- implemented by DELETE on audit_events.
--
-- This function identifies records that have passed the tenant
-- retention period and are eligible for the controlled retention
-- workflow. Active legal holds are excluded.
--
-- The retention/archive service must use credentials separate from
-- ordinary application roles and must preserve the checkpointed
-- chain before any external archival/deletion operation.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.get_retention_candidates
(
    p_organization_id UUID,
    p_as_of TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    p_limit INTEGER DEFAULT 1000
)
RETURNS SETOF audit_trail.audit_events
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = audit_trail, pg_catalog
AS $$
DECLARE
    v_retention_days INTEGER;
    v_cutoff TIMESTAMPTZ;
BEGIN
    IF p_limit < 1 OR p_limit > 100000 THEN
        RAISE EXCEPTION 'p_limit must be between 1 and 100000';
    END IF;

    SELECT retention_days
      INTO v_retention_days
      FROM audit_trail.audit_retention_policies
     WHERE organization_id = p_organization_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'No audit retention policy exists for organization %',
            p_organization_id;
    END IF;

    v_cutoff := p_as_of - make_interval(days => v_retention_days);

    RETURN QUERY
    SELECT ae.*
    FROM audit_trail.audit_events ae
    WHERE ae.organization_id = p_organization_id
      AND ae.created_at < v_cutoff
      AND NOT ae.legal_hold
      AND NOT audit_trail.audit_event_is_on_legal_hold(
          ae.organization_id,
          ae.resource_type,
          ae.resource_id
      )
    ORDER BY ae.seq
    LIMIT p_limit;
END;
$$;


-- ============================================================
-- 11. LEGAL-HOLD CONTROLLED OPERATIONS
-- ============================================================
--
-- Legal holds are applied/released through controlled functions.
-- Direct table mutation is not granted to ordinary roles.
-- Both actions are themselves audited.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.place_legal_hold
(
    p_organization_id UUID,
    p_resource_type TEXT,
    p_resource_id UUID,
    p_reason TEXT,
    p_placed_by UUID
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = audit_trail, pg_catalog
AS $$
DECLARE
    v_id UUID := gen_random_uuid();
BEGIN
    IF p_reason IS NULL OR length(btrim(p_reason)) = 0 THEN
        RAISE EXCEPTION 'Legal-hold reason is required';
    END IF;

    INSERT INTO audit_trail.audit_legal_holds
    (
        id,
        organization_id,
        resource_type,
        resource_id,
        reason,
        placed_by
    )
    VALUES
    (
        v_id,
        p_organization_id,
        p_resource_type,
        p_resource_id,
        p_reason,
        p_placed_by
    );

    PERFORM audit_trail.append_audit_event(
        p_organization_id,
        p_placed_by,
        NULL,
        NULL,
        'LEGAL_HOLD_PLACED',
        p_resource_type,
        p_resource_id,
        jsonb_build_object(
            'legal_hold_id', v_id,
            'reason', p_reason
        ),
        NULL,
        TRUE
    );

    RETURN v_id;
END;
$$;


CREATE OR REPLACE FUNCTION audit_trail.release_legal_hold
(
    p_legal_hold_id UUID,
    p_released_by UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = audit_trail, pg_catalog
AS $$
DECLARE
    v_organization_id UUID;
    v_resource_type TEXT;
    v_resource_id UUID;
BEGIN
    SELECT
        organization_id,
        resource_type,
        resource_id
    INTO
        v_organization_id,
        v_resource_type,
        v_resource_id
    FROM audit_trail.audit_legal_holds
    WHERE id = p_legal_hold_id
      AND released_at IS NULL
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Active legal hold % was not found',
            p_legal_hold_id;
    END IF;

    UPDATE audit_trail.audit_legal_holds
       SET released_by = p_released_by,
           released_at = CURRENT_TIMESTAMP
     WHERE id = p_legal_hold_id;

    PERFORM audit_trail.append_audit_event(
        v_organization_id,
        p_released_by,
        NULL,
        NULL,
        'LEGAL_HOLD_RELEASED',
        v_resource_type,
        v_resource_id,
        jsonb_build_object(
            'legal_hold_id', p_legal_hold_id
        ),
        NULL,
        TRUE
    );

    RETURN TRUE;
END;
$$;

REVOKE ALL ON FUNCTION audit_trail.place_legal_hold(
    UUID, TEXT, UUID, TEXT, UUID
) FROM PUBLIC;

REVOKE ALL ON FUNCTION audit_trail.release_legal_hold(
    UUID, UUID
) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION audit_trail.place_legal_hold(
    UUID, TEXT, UUID, TEXT, UUID
) TO audit_legal_hold_role;

GRANT EXECUTE ON FUNCTION audit_trail.release_legal_hold(
    UUID, UUID
) TO audit_legal_hold_role;


-- ============================================================
-- 11. CHECKPOINT REGISTRATION
-- ============================================================
--
-- A checkpoint records the latest verified chain position.
-- external_storage_ref is the immutable/object-storage reference
-- returned by the external anchoring service.
--
-- The actual external anchor must be written using credentials
-- separate from production DB/application credentials.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.register_chain_checkpoint
(
    p_organization_id UUID,
    p_seq_at_checkpoint BIGINT,
    p_chain_hash TEXT,
    p_external_storage_ref TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = audit_trail, pg_catalog
AS $$
DECLARE
    v_id UUID := gen_random_uuid();
    v_actual_hash TEXT;
BEGIN
    IF p_external_storage_ref IS NULL
       OR length(btrim(p_external_storage_ref)) = 0 THEN
        RAISE EXCEPTION 'external_storage_ref is required';
    END IF;

    SELECT hash
      INTO v_actual_hash
      FROM audit_trail.audit_events
     WHERE organization_id = p_organization_id
       AND seq = p_seq_at_checkpoint;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'No audit event exists at sequence % for organization %',
            p_seq_at_checkpoint,
            p_organization_id;
    END IF;

    IF p_chain_hash <> v_actual_hash THEN
        RAISE EXCEPTION
            'Checkpoint hash does not match audit chain';
    END IF;

    INSERT INTO audit_trail.audit_checkpoints
    (
        id,
        organization_id,
        seq_at_checkpoint,
        chain_hash,
        checkpointed_at,
        external_storage_ref
    )
    VALUES
    (
        v_id,
        p_organization_id,
        p_seq_at_checkpoint,
        p_chain_hash,
        CURRENT_TIMESTAMP,
        p_external_storage_ref
    );

    RETURN v_id;
END;
$$;


-- ============================================================
-- 12. CHECKPOINT MATERIAL FOR EXTERNAL ANCHORING
-- ============================================================
--
-- Returns the latest verified chain position for a tenant.
-- A scheduled external checkpoint worker should:
--   1. call this function using the dedicated checkpoint role;
--   2. write the returned seq/hash to external storage using
--      credentials that are NOT the production DB/application
--      credentials;
--   3. call register_chain_checkpoint() with the immutable storage
--      reference.
--
-- The database intentionally does not store external-storage
-- credentials.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.get_checkpoint_material
(
    p_organization_id UUID
)
RETURNS TABLE
(
    seq_at_checkpoint BIGINT,
    chain_hash TEXT,
    checkpointed_at TIMESTAMPTZ
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = audit_trail, pg_catalog
AS $$
    SELECT
        ae.seq,
        ae.hash,
        CURRENT_TIMESTAMP
    FROM audit_trail.audit_events ae
    WHERE ae.organization_id = p_organization_id
    ORDER BY ae.seq DESC
    LIMIT 1;
$$;

REVOKE ALL ON FUNCTION audit_trail.get_checkpoint_material(UUID) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION audit_trail.get_checkpoint_material(UUID)
    TO audit_checkpoint_role;


-- ============================================================
-- 12. FULL CHAIN VERIFICATION
-- ============================================================
--
-- Returns one row per audit event with:
--   sequence correctness
--   predecessor correctness
--   SHA-256 correctness
--
-- A tampered row produces hash_valid = FALSE.
-- A broken predecessor link produces predecessor_valid = FALSE.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.verify_audit_chain
(
    p_organization_id UUID
)
RETURNS TABLE
(
    seq BIGINT,
    event_id UUID,
    predecessor_valid BOOLEAN,
    hash_valid BOOLEAN,
    expected_hash TEXT,
    stored_hash TEXT
)
LANGUAGE sql
STABLE
AS $$
    WITH ordered AS
    (
        SELECT
            ae.*,
            lag(ae.hash) OVER (ORDER BY ae.seq) AS calculated_prev_hash,
            row_number() OVER (ORDER BY ae.seq) AS chain_position
        FROM audit_trail.audit_events ae
        WHERE ae.organization_id = p_organization_id
    )
    SELECT
        o.seq,
        o.id AS event_id,

        (
            CASE
                WHEN o.chain_position = 1
                    THEN o.prev_hash = repeat('0', 64)
                ELSE o.prev_hash = o.calculated_prev_hash
            END
        ) AS predecessor_valid,

        (
            o.hash =
            audit_trail.audit_event_hash(
                o.prev_hash,
                o.id,
                o.organization_id,
                o.seq,
                o.actor_id,
                o.acting_for_id,
                o.session_id,
                o.action_type,
                o.resource_type,
                o.resource_id,
                o.payload,
                o.ip_hash,
                o.legal_hold,
                o.created_at
            )
        ) AS hash_valid,

        audit_trail.audit_event_hash(
            o.prev_hash,
            o.id,
            o.organization_id,
            o.seq,
            o.actor_id,
            o.acting_for_id,
            o.session_id,
            o.action_type,
            o.resource_type,
            o.resource_id,
            o.payload,
            o.ip_hash,
            o.legal_hold,
            o.created_at
        ) AS expected_hash,

        o.hash AS stored_hash
    FROM ordered o
    ORDER BY o.seq;
$$;


-- ============================================================
-- 13. CHAIN STATUS FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.audit_chain_is_valid
(
    p_organization_id UUID
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        bool_and(predecessor_valid AND hash_valid),
        TRUE
    )
    FROM audit_trail.verify_audit_chain(p_organization_id);
$$;


-- ============================================================
-- 14. APPEND-ONLY CHECKPOINT ENFORCEMENT
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.prevent_checkpoint_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'audit_trail.audit_checkpoints is append-only: UPDATE and DELETE are prohibited';
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_checkpoints_append_only
    ON audit_trail.audit_checkpoints;

CREATE TRIGGER trg_audit_checkpoints_append_only
BEFORE UPDATE OR DELETE
ON audit_trail.audit_checkpoints
FOR EACH ROW
EXECUTE FUNCTION audit_trail.prevent_checkpoint_mutation();


-- ============================================================
-- 15. PERMISSION-CONTROLLED SEARCH / EXPORT ROLES
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS
    (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'audit_search_role'
    ) THEN
        CREATE ROLE audit_search_role NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;

    IF NOT EXISTS
    (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'audit_export_role'
    ) THEN
        CREATE ROLE audit_export_role NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;
    IF NOT EXISTS
    (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'audit_checkpoint_role'
    ) THEN
        CREATE ROLE audit_checkpoint_role NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;

    IF NOT EXISTS
    (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'audit_legal_hold_role'
    ) THEN
        CREATE ROLE audit_legal_hold_role NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;
END
$$;


-- ============================================================
-- 16. SEARCH FUNCTION
-- ============================================================
--
-- Tenant is taken from the authenticated session context.
-- Request-supplied organization_id is deliberately not accepted.
-- The function also creates an audit record for the search.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.search_audit_events
(
    p_from TIMESTAMPTZ DEFAULT NULL,
    p_to TIMESTAMPTZ DEFAULT NULL,
    p_action_type TEXT DEFAULT NULL,
    p_resource_type TEXT DEFAULT NULL,
    p_resource_id UUID DEFAULT NULL,
    p_limit INTEGER DEFAULT 100
)
RETURNS SETOF audit_trail.audit_events
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = audit_trail, pg_catalog
AS $$
DECLARE
    v_organization_id UUID;
    v_actor_id UUID;
    v_session_id UUID;
BEGIN
    v_organization_id :=
        NULLIF(current_setting('app.organization_id', true), '')::UUID;

    v_actor_id :=
        NULLIF(current_setting('app.user_id', true), '')::UUID;

    v_session_id :=
        NULLIF(current_setting('app.session_id', true), '')::UUID;

    IF v_organization_id IS NULL THEN
        RAISE EXCEPTION
            'Authenticated organization context is required';
    END IF;

    IF p_limit < 1 OR p_limit > 1000 THEN
        RAISE EXCEPTION
            'p_limit must be between 1 and 1000';
    END IF;

    PERFORM audit_trail.append_audit_event(
        v_organization_id,
        v_actor_id,
        NULL,
        v_session_id,
        'AUDIT_SEARCH',
        'audit_events',
        NULL,
        jsonb_build_object(
            'from', p_from,
            'to', p_to,
            'action_type', p_action_type,
            'resource_type', p_resource_type,
            'resource_id', p_resource_id,
            'limit', p_limit
        ),
        NULL,
        FALSE
    );

    RETURN QUERY
    SELECT ae.*
    FROM audit_trail.audit_events ae
    WHERE ae.organization_id = v_organization_id
      AND (p_from IS NULL OR ae.created_at >= p_from)
      AND (p_to IS NULL OR ae.created_at < p_to)
      AND (p_action_type IS NULL OR ae.action_type = p_action_type)
      AND (p_resource_type IS NULL OR ae.resource_type = p_resource_type)
      AND (p_resource_id IS NULL OR ae.resource_id = p_resource_id)
    ORDER BY ae.seq DESC
    LIMIT p_limit;
END;
$$;


-- ============================================================
-- 17. EXPORT FUNCTION
-- ============================================================
--
-- Export is a separate permission-controlled operation.
-- The export request itself is written to the audit chain.
--
-- Export returns JSONB records so the application can serialize
-- them to CSV/JSON without granting direct table SELECT.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.export_audit_events
(
    p_from TIMESTAMPTZ DEFAULT NULL,
    p_to TIMESTAMPTZ DEFAULT NULL,
    p_action_type TEXT DEFAULT NULL,
    p_resource_type TEXT DEFAULT NULL,
    p_resource_id UUID DEFAULT NULL,
    p_limit INTEGER DEFAULT 10000
)
RETURNS SETOF JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = audit_trail, pg_catalog
AS $$
DECLARE
    v_organization_id UUID;
    v_actor_id UUID;
    v_session_id UUID;
BEGIN
    v_organization_id :=
        NULLIF(current_setting('app.organization_id', true), '')::UUID;

    v_actor_id :=
        NULLIF(current_setting('app.user_id', true), '')::UUID;

    v_session_id :=
        NULLIF(current_setting('app.session_id', true), '')::UUID;

    IF v_organization_id IS NULL THEN
        RAISE EXCEPTION
            'Authenticated organization context is required';
    END IF;

    IF p_limit < 1 OR p_limit > 10000 THEN
        RAISE EXCEPTION
            'p_limit must be between 1 and 10000';
    END IF;

    PERFORM audit_trail.append_audit_event(
        v_organization_id,
        v_actor_id,
        NULL,
        v_session_id,
        'AUDIT_EXPORT',
        'audit_events',
        NULL,
        jsonb_build_object(
            'from', p_from,
            'to', p_to,
            'action_type', p_action_type,
            'resource_type', p_resource_type,
            'resource_id', p_resource_id,
            'limit', p_limit
        ),
        NULL,
        FALSE
    );

    RETURN QUERY
    SELECT to_jsonb(ae)
    FROM audit_trail.audit_events ae
    WHERE ae.organization_id = v_organization_id
      AND (p_from IS NULL OR ae.created_at >= p_from)
      AND (p_to IS NULL OR ae.created_at < p_to)
      AND (p_action_type IS NULL OR ae.action_type = p_action_type)
      AND (p_resource_type IS NULL OR ae.resource_type = p_resource_type)
      AND (p_resource_id IS NULL OR ae.resource_id = p_resource_id)
    ORDER BY ae.seq;
END;
$$;


-- ============================================================
-- 18. PERMISSION HARDENING
-- ============================================================
--
-- No ordinary role receives direct mutation privileges.
-- Search/export roles receive only their corresponding functions.
-- Retention/checkpoint roles receive only their corresponding
-- controlled functions.
-- ============================================================

REVOKE ALL ON TABLE audit_trail.audit_events FROM PUBLIC;
REVOKE ALL ON TABLE audit_trail.audit_checkpoints FROM PUBLIC;

REVOKE ALL ON TABLE audit_trail.audit_retention_policies FROM PUBLIC;
REVOKE ALL ON TABLE audit_trail.audit_legal_holds FROM PUBLIC;

REVOKE ALL ON FUNCTION audit_trail.prevent_checkpoint_mutation() FROM PUBLIC;

REVOKE ALL ON FUNCTION audit_trail.append_audit_event(
    UUID, UUID, UUID, UUID, TEXT, TEXT, UUID, JSONB, TEXT, BOOLEAN, TIMESTAMPTZ
) FROM PUBLIC;

REVOKE ALL ON FUNCTION audit_trail.search_audit_events(
    TIMESTAMPTZ, TIMESTAMPTZ, TEXT, TEXT, UUID, INTEGER
) FROM PUBLIC;

REVOKE ALL ON FUNCTION audit_trail.export_audit_events(
    TIMESTAMPTZ, TIMESTAMPTZ, TEXT, TEXT, UUID, INTEGER
) FROM PUBLIC;

REVOKE ALL ON FUNCTION audit_trail.register_chain_checkpoint(
    UUID, BIGINT, TEXT, TEXT
) FROM PUBLIC;

REVOKE ALL ON FUNCTION audit_trail.verify_audit_chain(
    UUID
) FROM PUBLIC;

REVOKE ALL ON FUNCTION audit_trail.audit_chain_is_valid(
    UUID
) FROM PUBLIC;

REVOKE ALL ON FUNCTION audit_trail.audit_event_is_on_legal_hold(
    UUID, TEXT, UUID
) FROM PUBLIC;

REVOKE ALL ON FUNCTION audit_trail.audit_event_hash(
    TEXT, UUID, UUID, BIGINT, UUID, UUID, UUID, TEXT, TEXT, UUID,
    JSONB, TEXT, BOOLEAN, TIMESTAMPTZ
) FROM PUBLIC;

GRANT USAGE ON SCHEMA audit_trail
    TO audit_search_role, audit_export_role,
       audit_checkpoint_role, audit_legal_hold_role;

GRANT EXECUTE ON FUNCTION audit_trail.search_audit_events(
    TIMESTAMPTZ, TIMESTAMPTZ, TEXT, TEXT, UUID, INTEGER
) TO audit_search_role;

GRANT EXECUTE ON FUNCTION audit_trail.export_audit_events(
    TIMESTAMPTZ, TIMESTAMPTZ, TEXT, TEXT, UUID, INTEGER
) TO audit_export_role;

GRANT EXECUTE ON FUNCTION audit_trail.get_retention_candidates(
    UUID, TIMESTAMPTZ, INTEGER
) TO audit_search_role;

GRANT EXECUTE ON FUNCTION audit_trail.register_chain_checkpoint(
    UUID, BIGINT, TEXT, TEXT
) TO audit_checkpoint_role;

GRANT EXECUTE ON FUNCTION audit_trail.verify_audit_chain(
    UUID
) TO audit_search_role, audit_export_role;

GRANT EXECUTE ON FUNCTION audit_trail.audit_chain_is_valid(
    UUID
) TO audit_search_role, audit_export_role;


-- ============================================================
-- 19. INDEXES FOR AUDIT SEARCH / RETENTION / VERIFICATION
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_audit_events_org_created_seq
    ON audit_trail.audit_events
    (
        organization_id,
        created_at,
        seq
    );

CREATE INDEX IF NOT EXISTS idx_audit_events_org_action_created
    ON audit_trail.audit_events
    (
        organization_id,
        action_type,
        created_at
    );

CREATE INDEX IF NOT EXISTS idx_audit_events_org_resource_created
    ON audit_trail.audit_events
    (
        organization_id,
        resource_type,
        resource_id,
        created_at
    );

CREATE INDEX IF NOT EXISTS idx_audit_checkpoints_org_seq
    ON audit_trail.audit_checkpoints
    (
        organization_id,
        seq_at_checkpoint
    );


-- ============================================================
-- 20. COMMENTS
-- ============================================================

COMMENT ON TABLE audit_trail.audit_events IS
    'Immutable append-only audit chain. Every row contains a SHA-256 hash over the canonical row data and the previous event hash.';

COMMENT ON COLUMN audit_trail.audit_events.prev_hash IS
    'SHA-256 hash of the immediately preceding audit event; first event uses 64 zeroes.';

COMMENT ON COLUMN audit_trail.audit_events.hash IS
    'SHA-256 digest of prev_hash plus the canonical audit event contents.';

COMMENT ON TABLE audit_trail.audit_retention_policies IS
    'Tenant-specific audit retention policy.';

COMMENT ON TABLE audit_trail.audit_legal_holds IS
    'Immutable audit-record protection metadata. Active legal holds override ordinary retention purge.';

COMMENT ON TABLE audit_trail.audit_checkpoints IS
    'Chain checkpoints anchored to external storage. The external anchor must use credentials separate from production credentials.';

COMMENT ON FUNCTION audit_trail.get_checkpoint_material(UUID) IS
    'Returns the latest tenant chain position for an external checkpoint worker. External storage credentials are intentionally outside PostgreSQL.';


-- ============================================================
-- 21. VERIFICATION QUERIES
-- ============================================================

SELECT
    c.relname AS table_name,
    c.relrowsecurity AS row_security_enabled,
    c.relforcerowsecurity AS force_row_security
FROM pg_class c
JOIN pg_namespace n
  ON n.oid = c.relnamespace
WHERE n.nspname = 'audit_trail'
  AND c.relname IN
      (
          'audit_events',
          'audit_checkpoints',
          'audit_retention_policies',
          'audit_legal_holds'
      )
ORDER BY c.relname;


SELECT
    tg.tgname,
    pg_get_triggerdef(tg.oid) AS trigger_definition
FROM pg_trigger tg
JOIN pg_class c
  ON c.oid = tg.tgrelid
JOIN pg_namespace n
  ON n.oid = c.relnamespace
WHERE n.nspname = 'audit_trail'
  AND c.relname = 'audit_events'
  AND NOT tg.tgisinternal
ORDER BY tg.tgname;


SELECT
    routine_schema,
    routine_name,
    routine_type
FROM information_schema.routines
WHERE routine_schema = 'audit_trail'
  AND routine_name IN
      (
          'append_audit_event',
          'verify_audit_chain',
          'audit_chain_is_valid',
          'register_chain_checkpoint',
          'get_checkpoint_material',
          'place_legal_hold',
          'release_legal_hold',
          'get_retention_candidates',
          'search_audit_events',
          'export_audit_events'
      )
ORDER BY routine_name;


SELECT
    grantee,
    table_schema,
    table_name,
    privilege_type
FROM information_schema.role_table_grants
WHERE table_schema = 'audit_trail'
  AND table_name = 'audit_events'
ORDER BY grantee, privilege_type;


COMMIT;

-- ============================================================
-- END OF append_only_hash_chained_audit.sql
-- ============================================================
