-- ============================================================
-- DB-020 | PER-TENANT DEDICATED DATABASE PROVISIONING
-- Requirements: TEN-06, SEC-04
-- ============================================================
-- Configuration-driven control-plane metadata for routing a tenant
-- to either a shared or dedicated PostgreSQL database.
-- Physical database creation belongs to infrastructure automation.
-- No passwords, private keys, tokens, or key material are stored here.
-- Existing key_management.key_registry is reused for SEC-04.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS tenant_database_provisioning;

CREATE TABLE IF NOT EXISTS tenant_database_provisioning.database_targets
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    target_code TEXT NOT NULL,
    deployment_mode TEXT NOT NULL,
    host_reference TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 5432,
    database_name TEXT NOT NULL,
    credential_secret_reference TEXT NOT NULL,
    tls_required BOOLEAN NOT NULL DEFAULT TRUE,
    region TEXT NULL,
    provisioning_status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_database_targets PRIMARY KEY (id),
    CONSTRAINT uq_database_targets_code UNIQUE (target_code),

    CONSTRAINT chk_database_targets_mode
        CHECK (deployment_mode IN ('shared_database','dedicated_database')),

    CONSTRAINT chk_database_targets_host_reference
        CHECK (length(btrim(host_reference)) > 0),

    CONSTRAINT chk_database_targets_database_name
        CHECK (length(btrim(database_name)) > 0),

    CONSTRAINT chk_database_targets_secret_reference
        CHECK (length(btrim(credential_secret_reference)) > 0),

    CONSTRAINT chk_database_targets_port
        CHECK (port BETWEEN 1 AND 65535),

    CONSTRAINT chk_database_targets_provisioning_status
        CHECK (
            provisioning_status IN
            ('pending','provisioning','ready','draining','decommissioned','failed')
        )
);

CREATE INDEX IF NOT EXISTS idx_database_targets_mode_status
    ON tenant_database_provisioning.database_targets
    (deployment_mode, provisioning_status);


CREATE TABLE IF NOT EXISTS tenant_database_provisioning.tenant_database_assignments
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    database_target_id UUID NOT NULL,
    assignment_mode TEXT NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMPTZ NULL,
    routing_version BIGINT NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_by UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_tenant_database_assignments PRIMARY KEY (id),

    CONSTRAINT fk_tenant_database_assignments_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_tenant_database_assignments_target
        FOREIGN KEY (database_target_id)
        REFERENCES tenant_database_provisioning.database_targets(id),

    CONSTRAINT chk_tenant_database_assignments_mode
        CHECK (assignment_mode IN ('shared_database','dedicated_database')),

    CONSTRAINT chk_tenant_database_assignments_status
        CHECK (status IN ('pending','active','draining','ended')),

    CONSTRAINT chk_tenant_database_assignments_dates
        CHECK (effective_to IS NULL OR effective_to > effective_from),

    CONSTRAINT chk_tenant_database_assignments_version
        CHECK (routing_version >= 1)
);

CREATE INDEX IF NOT EXISTS idx_tenant_database_assignments_org
    ON tenant_database_provisioning.tenant_database_assignments
    (organization_id, status);

CREATE INDEX IF NOT EXISTS idx_tenant_database_assignments_target
    ON tenant_database_provisioning.tenant_database_assignments
    (database_target_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_database_assignments_active
    ON tenant_database_provisioning.tenant_database_assignments
    (organization_id)
    WHERE status IN ('pending','active','draining');


-- SEC-04: tenant-specific database encryption key binding.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'key_management.key_registry'::regclass
          AND conname = 'uq_key_registry_organization_id_id'
    ) THEN
        ALTER TABLE key_management.key_registry
            ADD CONSTRAINT uq_key_registry_organization_id_id
            UNIQUE (organization_id, id);
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS tenant_database_provisioning.tenant_key_bindings
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    database_assignment_id UUID NOT NULL,
    key_registry_id UUID NOT NULL,
    key_purpose TEXT NOT NULL DEFAULT 'database_encryption',
    status TEXT NOT NULL DEFAULT 'active',
    bound_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    unbound_at TIMESTAMPTZ NULL,

    CONSTRAINT pk_tenant_key_bindings PRIMARY KEY (id),

    CONSTRAINT fk_tenant_key_bindings_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_tenant_key_bindings_assignment
        FOREIGN KEY (database_assignment_id)
        REFERENCES tenant_database_provisioning.tenant_database_assignments(id),

    CONSTRAINT fk_tenant_key_bindings_key
        FOREIGN KEY (organization_id, key_registry_id)
        REFERENCES key_management.key_registry
            (organization_id, id),

    CONSTRAINT chk_tenant_key_bindings_purpose
        CHECK (key_purpose = 'database_encryption'),

    CONSTRAINT chk_tenant_key_bindings_status
        CHECK (status IN ('active','retired')),

    CONSTRAINT chk_tenant_key_bindings_dates
        CHECK (unbound_at IS NULL OR unbound_at >= bound_at)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_key_bindings_active
    ON tenant_database_provisioning.tenant_key_bindings
    (organization_id, database_assignment_id)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_tenant_key_bindings_org
    ON tenant_database_provisioning.tenant_key_bindings
    (organization_id, status);


CREATE OR REPLACE FUNCTION
tenant_database_provisioning.validate_tenant_database_key()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_key_org UUID;
    v_key_purpose TEXT;
BEGIN
    SELECT organization_id, key_purpose
      INTO v_key_org, v_key_purpose
      FROM key_management.key_registry
     WHERE id = NEW.key_registry_id;

    IF v_key_org IS NULL THEN
        RAISE EXCEPTION 'SEC-04: tenant-scoped KMS/HSM key is required';
    END IF;

    IF v_key_org <> NEW.organization_id THEN
        RAISE EXCEPTION
            'SEC-04: database encryption key belongs to another tenant';
    END IF;

    IF v_key_purpose <> 'database_encryption' THEN
        RAISE EXCEPTION
            'SEC-04: bound key must have database_encryption purpose';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validate_tenant_database_key
ON tenant_database_provisioning.tenant_key_bindings;

CREATE TRIGGER trg_validate_tenant_database_key
BEFORE INSERT OR UPDATE OF organization_id, key_registry_id
ON tenant_database_provisioning.tenant_key_bindings
FOR EACH ROW
EXECUTE FUNCTION tenant_database_provisioning.validate_tenant_database_key();


CREATE OR REPLACE FUNCTION
tenant_database_provisioning.validate_database_assignment()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_target_mode TEXT;
BEGIN
    SELECT deployment_mode
      INTO v_target_mode
      FROM tenant_database_provisioning.database_targets
     WHERE id = NEW.database_target_id;

    IF v_target_mode IS NULL THEN
        RAISE EXCEPTION 'TEN-06: database target does not exist';
    END IF;

    IF v_target_mode <> NEW.assignment_mode THEN
        RAISE EXCEPTION
            'TEN-06: assignment mode does not match database target mode';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validate_database_assignment
ON tenant_database_provisioning.tenant_database_assignments;

CREATE TRIGGER trg_validate_database_assignment
BEFORE INSERT OR UPDATE OF database_target_id, assignment_mode
ON tenant_database_provisioning.tenant_database_assignments
FOR EACH ROW
EXECUTE FUNCTION tenant_database_provisioning.validate_database_assignment();


CREATE OR REPLACE VIEW tenant_database_provisioning.active_tenant_database_routes
WITH (security_invoker = true)
AS
SELECT
    a.organization_id,
    a.id AS assignment_id,
    a.assignment_mode,
    a.routing_version,
    t.id AS database_target_id,
    t.target_code,
    t.host_reference,
    t.port,
    t.database_name,
    t.credential_secret_reference,
    t.tls_required,
    t.region,
    a.effective_from
FROM tenant_database_provisioning.tenant_database_assignments a
JOIN tenant_database_provisioning.database_targets t
  ON t.id = a.database_target_id
WHERE a.status = 'active'
  AND t.provisioning_status = 'ready'
  AND a.effective_from <= CURRENT_TIMESTAMP
  AND (a.effective_to IS NULL OR a.effective_to > CURRENT_TIMESTAMP);


CREATE OR REPLACE VIEW tenant_database_provisioning.dedicated_database_readiness
WITH (security_invoker = true)
AS
SELECT
    a.organization_id,
    a.id AS assignment_id,
    a.assignment_mode,
    a.status AS assignment_status,
    t.target_code,
    t.provisioning_status,
    CASE
        WHEN a.assignment_mode <> 'dedicated_database' THEN FALSE
        WHEN t.provisioning_status <> 'ready' THEN FALSE
        WHEN kb.id IS NULL THEN FALSE
        WHEN kb.status <> 'active' THEN FALSE
        ELSE TRUE
    END AS ready_for_dedicated_tenant_routing
FROM tenant_database_provisioning.tenant_database_assignments a
JOIN tenant_database_provisioning.database_targets t
  ON t.id = a.database_target_id
LEFT JOIN tenant_database_provisioning.tenant_key_bindings kb
  ON kb.database_assignment_id = a.id
 AND kb.organization_id = a.organization_id
 AND kb.status = 'active';


ALTER TABLE tenant_database_provisioning.database_targets
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE tenant_database_provisioning.database_targets
    FORCE ROW LEVEL SECURITY;

ALTER TABLE tenant_database_provisioning.tenant_database_assignments
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE tenant_database_provisioning.tenant_database_assignments
    FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_database_assignments_tenant_isolation
ON tenant_database_provisioning.tenant_database_assignments;

CREATE POLICY tenant_database_assignments_tenant_isolation
ON tenant_database_provisioning.tenant_database_assignments
USING (organization_id = app.require_organization_context())
WITH CHECK (organization_id = app.require_organization_context());


ALTER TABLE tenant_database_provisioning.tenant_key_bindings
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE tenant_database_provisioning.tenant_key_bindings
    FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_key_bindings_tenant_isolation
ON tenant_database_provisioning.tenant_key_bindings;

CREATE POLICY tenant_key_bindings_tenant_isolation
ON tenant_database_provisioning.tenant_key_bindings
USING (organization_id = app.require_organization_context())
WITH CHECK (organization_id = app.require_organization_context());


COMMENT ON SCHEMA tenant_database_provisioning IS
    'DB-020 TEN-06/SEC-04 control-plane metadata for shared/dedicated PostgreSQL routing and tenant key separation.';

COMMENT ON TABLE tenant_database_provisioning.database_targets IS
    'Routable PostgreSQL targets. Stores secret-manager references, never credentials or key material.';

COMMENT ON TABLE tenant_database_provisioning.tenant_database_assignments IS
    'Tenant-to-database routing assignment. Switching shared/dedicated targets is configuration-driven.';

COMMENT ON TABLE tenant_database_provisioning.tenant_key_bindings IS
    'SEC-04 tenant-specific database-encryption KMS/HSM key binding.';


-- ============================================================
-- DB-020 REVIEW FIXES
-- ============================================================


-- ============================================================
-- 10. DEDICATED DATABASE EXCLUSIVITY
-- ============================================================
-- A physical dedicated PostgreSQL target may belong to only one
-- tenant at a time. Shared targets may be referenced by many tenants.

CREATE UNIQUE INDEX IF NOT EXISTS uq_dedicated_database_target_exclusive
    ON tenant_database_provisioning.tenant_database_assignments
    (database_target_id)
    WHERE assignment_mode = 'dedicated_database'
      AND status IN ('pending', 'active', 'draining');


-- ============================================================
-- 11. PROVISIONING AUDIT TRAIL
-- ============================================================
-- This is an immutable DB-020 operational audit stream.
-- The existing audit_trail.audit_events remains the platform-wide
-- audit system; this table provides a dedicated, query-friendly
-- provisioning history with explicit lifecycle event names.
--
-- No secrets or credentials are stored.

CREATE TABLE IF NOT EXISTS
tenant_database_provisioning.provisioning_audit_events
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    database_target_id UUID NULL,

    database_assignment_id UUID NULL,

    event_type TEXT NOT NULL,

    previous_status TEXT NULL,

    new_status TEXT NULL,

    actor_id UUID NULL,

    infrastructure_operation_id TEXT NULL,

    event_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_provisioning_audit_events
        PRIMARY KEY (id),

    CONSTRAINT fk_provisioning_audit_events_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_provisioning_audit_events_target
        FOREIGN KEY (database_target_id)
        REFERENCES tenant_database_provisioning.database_targets(id),

    CONSTRAINT fk_provisioning_audit_events_assignment
        FOREIGN KEY (database_assignment_id)
        REFERENCES tenant_database_provisioning.tenant_database_assignments(id),

    CONSTRAINT chk_provisioning_audit_event_type
        CHECK (
            event_type IN (
                'TARGET_REGISTERED',
                'PROVISIONING_STARTED',
                'PROVISIONING_READY',
                'PROVISIONING_FAILED',
                'ASSIGNMENT_CREATED',
                'ASSIGNMENT_ACTIVATED',
                'ASSIGNMENT_DRAINING',
                'ASSIGNMENT_ENDED',
                'TARGET_DECOMMISSIONED',
                'PROVISIONING_ROLLBACK'
            )
        ),

    CONSTRAINT chk_provisioning_audit_metadata_object
        CHECK (jsonb_typeof(event_metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_provisioning_audit_org_time
    ON tenant_database_provisioning.provisioning_audit_events
    (organization_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_provisioning_audit_target_time
    ON tenant_database_provisioning.provisioning_audit_events
    (database_target_id, occurred_at DESC);


-- Prevent UPDATE/DELETE so provisioning history remains immutable.
CREATE OR REPLACE FUNCTION
tenant_database_provisioning.prevent_provisioning_audit_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'DB-020: provisioning audit events are append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_provisioning_audit_immutable
ON tenant_database_provisioning.provisioning_audit_events;

CREATE TRIGGER trg_provisioning_audit_immutable
BEFORE UPDATE OR DELETE
ON tenant_database_provisioning.provisioning_audit_events
FOR EACH ROW
EXECUTE FUNCTION
tenant_database_provisioning.prevent_provisioning_audit_mutation();


-- ============================================================
-- 12. MIGRATION / CUTOVER TRACKING
-- ============================================================
-- Records shared -> dedicated and dedicated -> shared transitions.
-- A cutover is not considered complete until validation succeeds.

CREATE TABLE IF NOT EXISTS
tenant_database_provisioning.database_cutovers
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    from_assignment_id UUID NULL,
    from_database_target_id UUID NULL,

    to_assignment_id UUID NOT NULL,
    to_database_target_id UUID NOT NULL,

    cutover_type TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'planned',

    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,

    validation_started_at TIMESTAMPTZ NULL,
    validation_completed_at TIMESTAMPTZ NULL,

    validation_status TEXT NULL,

    rows_migrated BIGINT NULL,

    rollback_at TIMESTAMPTZ NULL,
    rollback_reason TEXT NULL,

    migration_operation_id TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_database_cutovers
        PRIMARY KEY (id),

    CONSTRAINT fk_database_cutovers_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_database_cutovers_from_assignment
        FOREIGN KEY (from_assignment_id)
        REFERENCES tenant_database_provisioning.tenant_database_assignments(id),

    CONSTRAINT fk_database_cutovers_from_target
        FOREIGN KEY (from_database_target_id)
        REFERENCES tenant_database_provisioning.database_targets(id),

    CONSTRAINT fk_database_cutovers_to_assignment
        FOREIGN KEY (to_assignment_id)
        REFERENCES tenant_database_provisioning.tenant_database_assignments(id),

    CONSTRAINT fk_database_cutovers_to_target
        FOREIGN KEY (to_database_target_id)
        REFERENCES tenant_database_provisioning.database_targets(id),

    CONSTRAINT chk_database_cutovers_type
        CHECK (
            cutover_type IN (
                'shared_to_dedicated',
                'dedicated_to_shared',
                'dedicated_to_dedicated'
            )
        ),

    CONSTRAINT chk_database_cutovers_status
        CHECK (
            status IN (
                'planned',
                'provisioning',
                'migrating',
                'validating',
                'completed',
                'failed',
                'rolled_back'
            )
        ),

    CONSTRAINT chk_database_cutovers_validation
        CHECK (
            validation_status IS NULL
            OR validation_status IN (
                'pending',
                'passed',
                'failed'
            )
        ),

    CONSTRAINT chk_database_cutovers_rows
        CHECK (
            rows_migrated IS NULL
            OR rows_migrated >= 0
        ),

    CONSTRAINT chk_database_cutovers_dates
        CHECK (
            completed_at IS NULL
            OR started_at IS NULL
            OR completed_at >= started_at
        ),

    CONSTRAINT chk_database_cutovers_rollback
        CHECK (
            (rollback_at IS NULL AND rollback_reason IS NULL)
            OR
            (rollback_at IS NOT NULL AND rollback_reason IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_database_cutovers_org_time
    ON tenant_database_provisioning.database_cutovers
    (organization_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_database_cutovers_status
    ON tenant_database_provisioning.database_cutovers
    (organization_id, status);


-- ============================================================
-- 13. KEY ROTATION EVIDENCE
-- ============================================================
-- Records evidence that the tenant-specific DB encryption key
-- used by a dedicated database was rotated and verified.
--
-- Actual key material is never stored.
-- Only external KMS/HSM references are recorded.

CREATE TABLE IF NOT EXISTS
tenant_database_provisioning.key_rotation_evidence
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    database_assignment_id UUID NOT NULL,

    key_registry_id UUID NOT NULL,

    previous_key_version_reference TEXT NULL,

    new_key_version_reference TEXT NOT NULL,

    rotation_history_id UUID NULL,

    rotation_started_at TIMESTAMPTZ NOT NULL,

    rotation_completed_at TIMESTAMPTZ NULL,

    verification_status TEXT NOT NULL DEFAULT 'pending',

    verified_at TIMESTAMPTZ NULL,

    verification_evidence_ref TEXT NULL,

    verification_details JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_key_rotation_evidence
        PRIMARY KEY (id),

    CONSTRAINT fk_key_rotation_evidence_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_key_rotation_evidence_assignment
        FOREIGN KEY (database_assignment_id)
        REFERENCES tenant_database_provisioning.tenant_database_assignments(id),

    CONSTRAINT fk_key_rotation_evidence_key
        FOREIGN KEY (organization_id, key_registry_id)
        REFERENCES key_management.key_registry
            (organization_id, id),

    CONSTRAINT chk_key_rotation_evidence_new_reference
        CHECK (length(btrim(new_key_version_reference)) > 0),

    CONSTRAINT chk_key_rotation_evidence_status
        CHECK (
            verification_status IN (
                'pending',
                'verified',
                'failed'
            )
        ),

    CONSTRAINT chk_key_rotation_evidence_dates
        CHECK (
            rotation_completed_at IS NULL
            OR rotation_completed_at >= rotation_started_at
        ),

    CONSTRAINT chk_key_rotation_evidence_verified
        CHECK (
            verification_status <> 'verified'
            OR verified_at IS NOT NULL
        ),

    CONSTRAINT chk_key_rotation_evidence_details
        CHECK (jsonb_typeof(verification_details) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_key_rotation_evidence_org_time
    ON tenant_database_provisioning.key_rotation_evidence
    (organization_id, rotation_started_at DESC);

CREATE INDEX IF NOT EXISTS idx_key_rotation_evidence_assignment
    ON tenant_database_provisioning.key_rotation_evidence
    (organization_id, database_assignment_id);

CREATE INDEX IF NOT EXISTS idx_key_rotation_evidence_status
    ON tenant_database_provisioning.key_rotation_evidence
    (organization_id, verification_status);


-- ============================================================
-- 14. RLS FOR NEW TENANT-OWNED TABLES
-- ============================================================

ALTER TABLE tenant_database_provisioning.provisioning_audit_events
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE tenant_database_provisioning.provisioning_audit_events
    FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS provisioning_audit_events_tenant_isolation
ON tenant_database_provisioning.provisioning_audit_events;

CREATE POLICY provisioning_audit_events_tenant_isolation
ON tenant_database_provisioning.provisioning_audit_events
USING (
    organization_id = app.require_organization_context()
)
WITH CHECK (
    organization_id = app.require_organization_context()
);


ALTER TABLE tenant_database_provisioning.database_cutovers
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE tenant_database_provisioning.database_cutovers
    FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS database_cutovers_tenant_isolation
ON tenant_database_provisioning.database_cutovers;

CREATE POLICY database_cutovers_tenant_isolation
ON tenant_database_provisioning.database_cutovers
USING (
    organization_id = app.require_organization_context()
)
WITH CHECK (
    organization_id = app.require_organization_context()
);


ALTER TABLE tenant_database_provisioning.key_rotation_evidence
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE tenant_database_provisioning.key_rotation_evidence
    FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS key_rotation_evidence_tenant_isolation
ON tenant_database_provisioning.key_rotation_evidence;

CREATE POLICY key_rotation_evidence_tenant_isolation
ON tenant_database_provisioning.key_rotation_evidence
USING (
    organization_id = app.require_organization_context()
)
WITH CHECK (
    organization_id = app.require_organization_context()
);


-- ============================================================
-- 15. REVIEW COMMENTS
-- ============================================================

COMMENT ON INDEX
tenant_database_provisioning.uq_dedicated_database_target_exclusive IS
    'TEN-06: one active tenant may exclusively own a dedicated PostgreSQL target.';

COMMENT ON TABLE
tenant_database_provisioning.provisioning_audit_events IS
    'DB-020 immutable provisioning lifecycle audit history.';

COMMENT ON TABLE
tenant_database_provisioning.database_cutovers IS
    'DB-020 shared/dedicated database migration and cutover lifecycle.';

COMMENT ON TABLE
tenant_database_provisioning.key_rotation_evidence IS
    'SEC-04 evidence that tenant-specific database encryption key rotation was completed and verified.';


COMMIT;
