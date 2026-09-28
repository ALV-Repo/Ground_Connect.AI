-- ============================================================
-- DB-016: SLA & ESCALATION + COMPLIANCE MODE CONFIGURATION
-- Requirements: CIT-13, CMP-01, CMP-02
--
-- Incremental migration:
--   * Reuses citizen_issues.sla_config
--   * Reuses compliance_mode.compliance_profiles
--   * Reuses compliance_mode.compliance_profile_activations
--   * Does NOT recreate existing Phase-2 tables
--
-- IMPORTANT:
-- PostgreSQL cannot wake up on wall-clock time by itself. The function
-- citizen_issues.process_sla_breaches() must be invoked by the existing
-- scheduler/worker at a regular interval (recommended: <= 1 minute).
-- It creates idempotent escalation outbox events; a notification worker
-- dispatches those events through the existing notification infrastructure.
-- ============================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF to_regclass('citizen_issues.sla_config') IS NULL
       OR to_regclass('citizen_issues.canonical_issues') IS NULL
       OR to_regclass('compliance_mode.compliance_profiles') IS NULL
       OR to_regclass('compliance_mode.compliance_profile_activations') IS NULL
       OR to_regclass('tenant_and_configuration.tenants') IS NULL
       OR to_regclass('identity_authentication_sessions.users') IS NULL
    THEN
        RAISE EXCEPTION 'DB-016 prerequisites are missing';
    END IF;

    IF to_regprocedure(
        'audit_trail.append_audit_event(uuid,uuid,uuid,uuid,text,text,uuid,jsonb,text,boolean,timestamptz)'
    ) IS NULL
    THEN
        RAISE EXCEPTION
            'DB-016 requires audit_trail.append_audit_event(...) from the audit implementation';
    END IF;
END $$;

-- ============================================================
-- 1. SLA MATRIX
-- ============================================================

ALTER TABLE citizen_issues.sla_config
    ADD COLUMN IF NOT EXISTS escalation_chain_id UUID,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- Keep the legacy JSON configuration column for backward compatibility,
-- but the normalized chain is the DB-016 source of truth.
ALTER TABLE citizen_issues.sla_config
    ALTER COLUMN escalation_chain DROP NOT NULL;

DO $$
BEGIN
    ALTER TABLE citizen_issues.sla_config
        ADD CONSTRAINT chk_sla_config_response_target_positive
        CHECK (response_target_minutes > 0);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE citizen_issues.sla_config
        ADD CONSTRAINT chk_sla_config_resolution_target_positive
        CHECK (resolution_target_minutes > 0);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE citizen_issues.sla_config
        ADD CONSTRAINT chk_sla_config_response_le_resolution
        CHECK (response_target_minutes <= resolution_target_minutes);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_sla_config_org_category_priority
    ON citizen_issues.sla_config (organization_id, category, priority);

CREATE UNIQUE INDEX IF NOT EXISTS uq_sla_config_org_id
    ON citizen_issues.sla_config (organization_id, id);

-- ============================================================
-- 2. ESCALATION CHAIN CONFIGURATION
-- ============================================================

CREATE TABLE IF NOT EXISTS citizen_issues.sla_escalation_chains
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_sla_escalation_chains PRIMARY KEY (id),
    CONSTRAINT fk_sla_escalation_chains_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT uq_sla_escalation_chains_org_name_version
        UNIQUE (organization_id, name, version),
    CONSTRAINT chk_sla_escalation_chains_name
        CHECK (length(trim(name)) > 0),
    CONSTRAINT chk_sla_escalation_chains_version
        CHECK (version > 0)
);

CREATE TABLE IF NOT EXISTS citizen_issues.sla_escalation_chain_steps
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    escalation_chain_id UUID NOT NULL,
    step_no INTEGER NOT NULL,
    trigger_after_minutes INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_ref UUID NULL,
    target_value TEXT NULL,
    notification_channel TEXT NOT NULL DEFAULT 'in_app',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_sla_escalation_chain_steps PRIMARY KEY (id),
    CONSTRAINT fk_sla_escalation_chain_steps_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT fk_sla_escalation_chain_steps_chain
        FOREIGN KEY (organization_id, escalation_chain_id)
        REFERENCES citizen_issues.sla_escalation_chains(organization_id, id),
    CONSTRAINT uq_sla_escalation_chain_steps_chain_step
        UNIQUE (escalation_chain_id, step_no),
    CONSTRAINT chk_sla_escalation_chain_steps_step_no
        CHECK (step_no > 0),
    CONSTRAINT chk_sla_escalation_chain_steps_trigger
        CHECK (trigger_after_minutes >= 0),
    CONSTRAINT chk_sla_escalation_chain_steps_target_type
        CHECK (target_type IN ('user','node','role','channel')),
    CONSTRAINT chk_sla_escalation_chain_steps_target
        CHECK (
            (target_type IN ('user','node','role')
             AND target_ref IS NOT NULL AND target_value IS NULL)
            OR
            (target_type = 'channel'
             AND target_ref IS NULL
             AND target_value IS NOT NULL
             AND length(trim(target_value)) > 0)
        ),
    CONSTRAINT chk_sla_escalation_chain_steps_channel
        CHECK (notification_channel IN ('in_app','sms','voice','email','webhook'))
);

CREATE INDEX IF NOT EXISTS idx_sla_escalation_chains_org_enabled
    ON citizen_issues.sla_escalation_chains (organization_id, enabled);

CREATE INDEX IF NOT EXISTS idx_sla_escalation_chain_steps_chain
    ON citizen_issues.sla_escalation_chain_steps
       (organization_id, escalation_chain_id, step_no);

DO $$
BEGIN
    ALTER TABLE citizen_issues.sla_config
        ADD CONSTRAINT fk_sla_config_escalation_chain_tenant
        FOREIGN KEY (organization_id, escalation_chain_id)
        REFERENCES citizen_issues.sla_escalation_chains(organization_id, id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_sla_config_escalation_chain
    ON citizen_issues.sla_config (organization_id, escalation_chain_id);

-- ============================================================
-- 3. SLA BREACH / ESCALATION OUTBOX
-- ============================================================

ALTER TABLE citizen_issues.canonical_issues
    ADD COLUMN IF NOT EXISTS sla_response_breached_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS sla_resolution_breached_at TIMESTAMPTZ NULL;

CREATE TABLE IF NOT EXISTS citizen_issues.sla_escalation_events
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    issue_id UUID NOT NULL,
    sla_config_id UUID NOT NULL,
    escalation_chain_id UUID NOT NULL,
    escalation_step_id UUID NOT NULL,
    breach_type TEXT NOT NULL,
    breach_at TIMESTAMPTZ NOT NULL,
    available_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    dispatched_at TIMESTAMPTZ NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_sla_escalation_events PRIMARY KEY (id),
    CONSTRAINT fk_sla_escalation_events_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT fk_sla_escalation_events_issue
        FOREIGN KEY (issue_id)
        REFERENCES citizen_issues.canonical_issues(id),
    CONSTRAINT fk_sla_escalation_events_sla_config
        FOREIGN KEY (sla_config_id)
        REFERENCES citizen_issues.sla_config(id),
    CONSTRAINT fk_sla_escalation_events_sla_config_tenant
        FOREIGN KEY (organization_id, sla_config_id)
        REFERENCES citizen_issues.sla_config(organization_id, id),
    CONSTRAINT fk_sla_escalation_events_chain_step
        FOREIGN KEY (escalation_step_id)
        REFERENCES citizen_issues.sla_escalation_chain_steps(id),
    CONSTRAINT fk_sla_escalation_events_chain_step_tenant
        FOREIGN KEY (organization_id, escalation_step_id)
        REFERENCES citizen_issues.sla_escalation_chain_steps(organization_id, id),
    CONSTRAINT chk_sla_escalation_events_breach_type
        CHECK (breach_type IN ('response','resolution')),
    CONSTRAINT chk_sla_escalation_events_status
        CHECK (status IN ('pending','processing','dispatched','failed','cancelled')),
    CONSTRAINT chk_sla_escalation_events_attempt_count
        CHECK (attempt_count >= 0),
    CONSTRAINT uq_sla_escalation_events_idempotency
        UNIQUE (issue_id, breach_type, escalation_step_id)
);

CREATE INDEX IF NOT EXISTS idx_sla_escalation_events_dispatch
    ON citizen_issues.sla_escalation_events
       (organization_id, status, available_at);

CREATE INDEX IF NOT EXISTS idx_sla_escalation_events_issue
    ON citizen_issues.sla_escalation_events
       (organization_id, issue_id, breach_type);

-- ============================================================
-- 4. SLA BREACH PROCESSOR
-- ============================================================

CREATE OR REPLACE FUNCTION citizen_issues.process_sla_breaches(
    p_organization_id UUID,
    p_now TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
DECLARE
    v_inserted INTEGER := 0;
BEGIN
    IF p_organization_id IS NULL THEN
        RAISE EXCEPTION 'CIT-13: organization context is required';
    END IF;

    -- Response breach.
    UPDATE citizen_issues.canonical_issues i
       SET sla_response_breached_at = COALESCE(i.sla_response_breached_at, p_now),
           sla_breach_count = CASE
               WHEN i.sla_response_breached_at IS NULL
               THEN i.sla_breach_count + 1
               ELSE i.sla_breach_count
           END,
           updated_at = p_now
     WHERE i.organization_id = p_organization_id
       AND i.sla_response_deadline IS NOT NULL
       AND i.sla_response_deadline <= p_now
       AND i.sla_response_breached_at IS NULL
       AND i.status NOT IN ('Resolved_Confirmed','Closed','Rejected');

    -- Resolution breach.
    UPDATE citizen_issues.canonical_issues i
       SET sla_resolution_breached_at = COALESCE(i.sla_resolution_breached_at, p_now),
           sla_breach_count = CASE
               WHEN i.sla_resolution_breached_at IS NULL
               THEN i.sla_breach_count + 1
               ELSE i.sla_breach_count
           END,
           updated_at = p_now
     WHERE i.organization_id = p_organization_id
       AND i.sla_resolution_deadline IS NOT NULL
       AND i.sla_resolution_deadline <= p_now
       AND i.sla_resolution_breached_at IS NULL
       AND i.status NOT IN ('Resolved_Confirmed','Closed','Rejected');

    INSERT INTO citizen_issues.sla_escalation_events
    (
        organization_id, issue_id, sla_config_id, escalation_chain_id,
        escalation_step_id, breach_type, breach_at, available_at
    )
    SELECT
        i.organization_id,
        i.id,
        sc.id,
        sc.escalation_chain_id,
        st.id,
        b.breach_type,
        CASE b.breach_type
            WHEN 'response' THEN i.sla_response_breached_at
            ELSE i.sla_resolution_breached_at
        END,
        (
            CASE b.breach_type
                WHEN 'response' THEN i.sla_response_breached_at
                ELSE i.sla_resolution_breached_at
            END
            + make_interval(mins => st.trigger_after_minutes)
        )
    FROM citizen_issues.canonical_issues i
    JOIN citizen_issues.sla_config sc
      ON sc.organization_id = i.organization_id
     AND sc.category = i.category
     AND sc.priority = i.priority
     AND sc.escalation_chain_id IS NOT NULL
    JOIN citizen_issues.sla_escalation_chains ec
      ON ec.organization_id = sc.organization_id
     AND ec.id = sc.escalation_chain_id
     AND ec.enabled
    JOIN citizen_issues.sla_escalation_chain_steps st
      ON st.organization_id = ec.organization_id
     AND st.escalation_chain_id = ec.id
     AND st.enabled
    CROSS JOIN LATERAL (
        VALUES
          ('response'::TEXT, i.sla_response_breached_at),
          ('resolution'::TEXT, i.sla_resolution_breached_at)
    ) b(breach_type, breach_marker)
    WHERE i.organization_id = p_organization_id
      AND b.breach_marker IS NOT NULL
      AND (
          CASE b.breach_type
              WHEN 'response' THEN i.sla_response_breached_at
              ELSE i.sla_resolution_breached_at
          END
          + make_interval(mins => st.trigger_after_minutes)
      ) <= p_now
    ON CONFLICT (issue_id, breach_type, escalation_step_id) DO NOTHING;

    GET DIAGNOSTICS v_inserted = ROW_COUNT;

    RETURN v_inserted;
END;
$$;

-- ============================================================
-- 5. COMPLIANCE PROFILE CONFIGURATION
-- ============================================================

ALTER TABLE compliance_mode.compliance_profiles
    ADD COLUMN IF NOT EXISTS feature_availability JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS retention_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS mandatory_disclaimers JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS approval_requirements JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS export_restrictions JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS audit_granularity TEXT NOT NULL DEFAULT 'standard';

CREATE UNIQUE INDEX IF NOT EXISTS uq_compliance_profiles_org_name_version
    ON compliance_mode.compliance_profiles (organization_id, name, version);

CREATE UNIQUE INDEX IF NOT EXISTS uq_compliance_profiles_org_id
    ON compliance_mode.compliance_profiles (organization_id, id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_compliance_profile_activations_org_id
    ON compliance_mode.compliance_profile_activations (organization_id, id);

DO $$
BEGIN
    ALTER TABLE compliance_mode.compliance_profiles
        ADD CONSTRAINT chk_compliance_profiles_name
        CHECK (length(trim(name)) > 0);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE compliance_mode.compliance_profiles
        ADD CONSTRAINT chk_compliance_profiles_version
        CHECK (length(trim(version)) > 0);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE compliance_mode.compliance_profiles
        ADD CONSTRAINT chk_compliance_profiles_audit_granularity
        CHECK (audit_granularity IN ('standard','detailed','maximum'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Profiles are versioned configuration records. Once created they are
-- immutable; create a new version instead of editing an active profile.
CREATE OR REPLACE FUNCTION compliance_mode.prevent_profile_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'CMP-01: compliance profiles are immutable; create a new version';
END;
$$;

DROP TRIGGER IF EXISTS trg_compliance_profiles_immutable
    ON compliance_mode.compliance_profiles;

CREATE TRIGGER trg_compliance_profiles_immutable
BEFORE UPDATE OR DELETE
ON compliance_mode.compliance_profiles
FOR EACH ROW
EXECUTE FUNCTION compliance_mode.prevent_profile_mutation();

-- ============================================================
-- 6. ACTIVATION HISTORY
-- ============================================================

CREATE TABLE IF NOT EXISTS compliance_mode.profile_activation_history
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    profile_name TEXT NOT NULL,
    profile_version TEXT NOT NULL,
    action TEXT NOT NULL,
    profile_contents JSONB NOT NULL,
    activated_at TIMESTAMPTZ NULL,
    deactivated_at TIMESTAMPTZ NULL,
    action_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    action_by UUID NOT NULL,
    source_activation_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_profile_activation_history PRIMARY KEY (id),
    CONSTRAINT fk_profile_activation_history_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT fk_profile_activation_history_profile
        FOREIGN KEY (profile_id)
        REFERENCES compliance_mode.compliance_profiles(id),
    CONSTRAINT fk_profile_activation_history_actor
        FOREIGN KEY (action_by)
        REFERENCES identity_authentication_sessions.users(id),
    CONSTRAINT fk_profile_activation_history_activation
        FOREIGN KEY (source_activation_id)
        REFERENCES compliance_mode.compliance_profile_activations(id),
    CONSTRAINT chk_profile_activation_history_action
        CHECK (action IN ('activate','deactivate')),
    CONSTRAINT chk_profile_activation_history_contents
        CHECK (jsonb_typeof(profile_contents) = 'object'),
    CONSTRAINT chk_profile_activation_history_times
        CHECK (
            (action = 'activate'
             AND activated_at IS NOT NULL
             AND deactivated_at IS NULL)
            OR
            (action = 'deactivate'
             AND deactivated_at IS NOT NULL)
        )
);

DO $$
BEGIN
    ALTER TABLE compliance_mode.compliance_profile_activations
        ADD CONSTRAINT fk_compliance_profile_activations_profile_tenant
        FOREIGN KEY (organization_id, profile_id)
        REFERENCES compliance_mode.compliance_profiles(organization_id, id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_profile_activation_history_org_time
    ON compliance_mode.profile_activation_history (organization_id, action_at DESC);

CREATE INDEX IF NOT EXISTS idx_profile_activation_history_profile
    ON compliance_mode.profile_activation_history
       (organization_id, profile_id, action_at DESC);

DO $$
BEGIN
    ALTER TABLE compliance_mode.profile_activation_history
        ADD CONSTRAINT fk_profile_activation_history_profile_tenant
        FOREIGN KEY (organization_id, profile_id)
        REFERENCES compliance_mode.compliance_profiles(organization_id, id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_compliance_profile_activations_one_active
    ON compliance_mode.compliance_profile_activations (organization_id)
    WHERE deactivated_at IS NULL;

CREATE OR REPLACE FUNCTION compliance_mode.prevent_profile_history_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'CMP-02: compliance profile activation history is append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_profile_activation_history_append_only
    ON compliance_mode.profile_activation_history;

CREATE TRIGGER trg_profile_activation_history_append_only
BEFORE UPDATE OR DELETE
ON compliance_mode.profile_activation_history
FOR EACH ROW
EXECUTE FUNCTION compliance_mode.prevent_profile_history_mutation();

-- Existing activation rows must retain their snapshot. Only deactivation
-- metadata is mutable through the controlled function below.
CREATE OR REPLACE FUNCTION compliance_mode.protect_activation_row()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'CMP-02: activation records cannot be deleted';
    END IF;

    IF NEW.organization_id <> OLD.organization_id
       OR NEW.profile_id <> OLD.profile_id
       OR NEW.profile_config_snapshot IS DISTINCT FROM OLD.profile_config_snapshot
       OR NEW.activated_at <> OLD.activated_at
       OR NEW.activated_by <> OLD.activated_by
    THEN
        RAISE EXCEPTION
            'CMP-02: activation identity and snapshot are immutable';
    END IF;

    IF OLD.deactivated_at IS NOT NULL
       AND (
           NEW.deactivated_at IS DISTINCT FROM OLD.deactivated_at
           OR NEW.deactivated_by IS DISTINCT FROM OLD.deactivated_by
       )
    THEN
        RAISE EXCEPTION 'CMP-02: deactivation metadata is immutable once recorded';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_compliance_profile_activations_protect
    ON compliance_mode.compliance_profile_activations;

CREATE TRIGGER trg_compliance_profile_activations_protect
BEFORE UPDATE OR DELETE
ON compliance_mode.compliance_profile_activations
FOR EACH ROW
EXECUTE FUNCTION compliance_mode.protect_activation_row();

-- ============================================================
-- 7. CURRENT PROFILE VIEW
-- ============================================================

CREATE OR REPLACE VIEW compliance_mode.current_profile AS
SELECT
    a.organization_id,
    a.id AS activation_id,
    a.profile_id,
    a.activated_at,
    a.profile_config_snapshot
FROM compliance_mode.compliance_profile_activations a
WHERE a.deactivated_at IS NULL;

-- ============================================================
-- 8. ATOMIC, AUDITED ACTIVATION / DEACTIVATION
-- ============================================================

CREATE OR REPLACE FUNCTION compliance_mode.activate_profile(
    p_organization_id UUID,
    p_profile_id UUID,
    p_activated_by UUID
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
DECLARE
    v_profile compliance_mode.compliance_profiles%ROWTYPE;
    v_activation_id UUID;
    v_snapshot JSONB;
BEGIN
    PERFORM app.require_organization_context();

    IF app.current_organization_id() <> p_organization_id THEN
        RAISE EXCEPTION 'CMP-01: organization context mismatch';
    END IF;

    SELECT *
      INTO v_profile
      FROM compliance_mode.compliance_profiles
     WHERE id = p_profile_id
       AND organization_id = p_organization_id
     FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'CMP-01: compliance profile does not belong to organization';
    END IF;

    PERFORM 1
      FROM tenant_and_configuration.tenants
     WHERE id = p_organization_id
     FOR UPDATE;

    IF EXISTS (
        SELECT 1
          FROM compliance_mode.compliance_profile_activations
         WHERE organization_id = p_organization_id
           AND deactivated_at IS NULL
    ) THEN
        RAISE EXCEPTION
            'CMP-01: organization already has an active compliance profile; deactivate it first';
    END IF;

    v_snapshot := jsonb_build_object(
        'name', v_profile.name,
        'version', v_profile.version,
        'config', v_profile.config,
        'feature_availability', v_profile.feature_availability,
        'retention_policy', v_profile.retention_policy,
        'mandatory_disclaimers', v_profile.mandatory_disclaimers,
        'approval_requirements', v_profile.approval_requirements,
        'export_restrictions', v_profile.export_restrictions,
        'audit_granularity', v_profile.audit_granularity
    );

    INSERT INTO compliance_mode.compliance_profile_activations
    (
        organization_id,
        profile_id,
        profile_config_snapshot,
        activated_at,
        activated_by
    )
    VALUES
    (
        p_organization_id,
        p_profile_id,
        v_snapshot,
        CURRENT_TIMESTAMP,
        p_activated_by
    )
    RETURNING id INTO v_activation_id;

    UPDATE tenant_and_configuration.tenants
       SET compliance_profile_id = p_profile_id,
           updated_at = CURRENT_TIMESTAMP
     WHERE id = p_organization_id;

    INSERT INTO compliance_mode.profile_activation_history
    (
        organization_id, profile_id, profile_name, profile_version,
        action, profile_contents, activated_at, action_at, action_by,
        source_activation_id
    )
    VALUES
    (
        p_organization_id, p_profile_id, v_profile.name, v_profile.version,
        'activate', v_snapshot, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
        p_activated_by, v_activation_id
    );

    PERFORM audit_trail.append_audit_event(
        p_organization_id,
        p_activated_by,
        NULL,
        NULL,
        'COMPLIANCE_PROFILE_ACTIVATED',
        'compliance_profile',
        p_profile_id,
        jsonb_build_object(
            'activation_id', v_activation_id,
            'profile_name', v_profile.name,
            'profile_version', v_profile.version,
            'profile_contents', v_snapshot
        ),
        NULL,
        FALSE,
        CURRENT_TIMESTAMP
    );

    RETURN v_activation_id;
END;
$$;

CREATE OR REPLACE FUNCTION compliance_mode.deactivate_profile(
    p_organization_id UUID,
    p_activation_id UUID,
    p_deactivated_by UUID
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
DECLARE
    v_activation compliance_mode.compliance_profile_activations%ROWTYPE;
    v_profile compliance_mode.compliance_profiles%ROWTYPE;
BEGIN
    PERFORM app.require_organization_context();

    IF app.current_organization_id() <> p_organization_id THEN
        RAISE EXCEPTION 'CMP-02: organization context mismatch';
    END IF;

    PERFORM 1
      FROM tenant_and_configuration.tenants
     WHERE id = p_organization_id
     FOR UPDATE;

    SELECT *
      INTO v_activation
      FROM compliance_mode.compliance_profile_activations
     WHERE id = p_activation_id
       AND organization_id = p_organization_id
     FOR UPDATE;

    IF NOT FOUND OR v_activation.deactivated_at IS NOT NULL THEN
        RAISE EXCEPTION
            'CMP-02: active compliance profile activation not found';
    END IF;

    SELECT *
      INTO v_profile
      FROM compliance_mode.compliance_profiles
     WHERE id = v_activation.profile_id
       AND organization_id = p_organization_id;

    UPDATE compliance_mode.compliance_profile_activations
       SET deactivated_at = CURRENT_TIMESTAMP,
           deactivated_by = p_deactivated_by
     WHERE id = p_activation_id;

    UPDATE tenant_and_configuration.tenants
       SET compliance_profile_id = NULL,
           updated_at = CURRENT_TIMESTAMP
     WHERE id = p_organization_id;

    INSERT INTO compliance_mode.profile_activation_history
    (
        organization_id, profile_id, profile_name, profile_version,
        action, profile_contents, activated_at, deactivated_at,
        action_at, action_by, source_activation_id
    )
    VALUES
    (
        p_organization_id, v_activation.profile_id,
        v_profile.name, v_profile.version, 'deactivate',
        v_activation.profile_config_snapshot,
        v_activation.activated_at, CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP, p_deactivated_by, p_activation_id
    );

    PERFORM audit_trail.append_audit_event(
        p_organization_id,
        p_deactivated_by,
        NULL,
        NULL,
        'COMPLIANCE_PROFILE_DEACTIVATED',
        'compliance_profile',
        v_activation.profile_id,
        jsonb_build_object(
            'activation_id', p_activation_id,
            'profile_name', v_profile.name,
            'profile_version', v_profile.version,
            'profile_contents', v_activation.profile_config_snapshot
        ),
        NULL,
        FALSE,
        CURRENT_TIMESTAMP
    );
END;
$$;

-- ============================================================
-- 9. RLS
-- ============================================================

DO $$
DECLARE
    v_table TEXT;
BEGIN
    FOREACH v_table IN ARRAY ARRAY[
        'citizen_issues.sla_config',
        'citizen_issues.sla_escalation_chains',
        'citizen_issues.sla_escalation_chain_steps',
        'citizen_issues.sla_escalation_events',
        'compliance_mode.compliance_profiles',
        'compliance_mode.compliance_profile_activations',
        'compliance_mode.profile_activation_history'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', v_table);
        EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', v_table);
    END LOOP;
END $$;

DROP POLICY IF EXISTS db016_sla_config_tenant_isolation
    ON citizen_issues.sla_config;
CREATE POLICY db016_sla_config_tenant_isolation
    ON citizen_issues.sla_config
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db016_sla_escalation_chains_tenant_isolation
    ON citizen_issues.sla_escalation_chains;
CREATE POLICY db016_sla_escalation_chains_tenant_isolation
    ON citizen_issues.sla_escalation_chains
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db016_sla_escalation_steps_tenant_isolation
    ON citizen_issues.sla_escalation_chain_steps;
CREATE POLICY db016_sla_escalation_steps_tenant_isolation
    ON citizen_issues.sla_escalation_chain_steps
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db016_sla_escalation_events_tenant_isolation
    ON citizen_issues.sla_escalation_events;
CREATE POLICY db016_sla_escalation_events_tenant_isolation
    ON citizen_issues.sla_escalation_events
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db016_compliance_profiles_tenant_isolation
    ON compliance_mode.compliance_profiles;
CREATE POLICY db016_compliance_profiles_tenant_isolation
    ON compliance_mode.compliance_profiles
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db016_compliance_activations_tenant_isolation
    ON compliance_mode.compliance_profile_activations;
CREATE POLICY db016_compliance_activations_tenant_isolation
    ON compliance_mode.compliance_profile_activations
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db016_profile_history_tenant_isolation
    ON compliance_mode.profile_activation_history;
CREATE POLICY db016_profile_history_tenant_isolation
    ON compliance_mode.profile_activation_history
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

-- ============================================================
-- 10. COMMENTS
-- ============================================================

COMMENT ON TABLE citizen_issues.sla_escalation_events IS
    'CIT-13 durable escalation outbox. A scheduler calls process_sla_breaches(); a notification worker dispatches pending events.';

COMMENT ON FUNCTION citizen_issues.process_sla_breaches(UUID,TIMESTAMPTZ) IS
    'Detects overdue response/resolution SLAs and creates idempotent tenant-configured escalation events.';

COMMENT ON VIEW compliance_mode.current_profile IS
    'Current tenant-wide compliance profile and immutable activation snapshot.';

COMMENT ON FUNCTION compliance_mode.activate_profile(UUID,UUID,UUID) IS
    'Atomically activates a named/versioned compliance profile, updates tenant state, records immutable history, and writes an audit event.';

COMMENT ON FUNCTION compliance_mode.deactivate_profile(UUID,UUID,UUID) IS
    'Atomically deactivates a compliance profile, updates tenant state, records immutable history, and writes an audit event.';

COMMIT;
