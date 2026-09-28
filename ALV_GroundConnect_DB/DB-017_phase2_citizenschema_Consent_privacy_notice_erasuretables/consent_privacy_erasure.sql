-- ============================================================
-- DB-017: CONSENT, PRIVACY NOTICE, ERASURE & RETENTION CONTROLS
-- ============================================================
-- Incremental migration.
-- Extends existing consent_privacy_erasure tables created by 15_consent_privacy_erasure.sql.
-- Does NOT recreate existing consent/privacy/erasure tables.
--
-- Requirements:
--   PRV-03 Privacy notices shown in user language; shown version recorded.
--   PRV-04 Consent or other lawful basis recorded per interaction.
--   PRV-06 Verified erasure tracking, cascade log, certificate, audit preservation.
--   PRV-07 Retention schedules, legal-hold override, live obligations dashboard.
--
-- Operational note:
-- PostgreSQL cannot invoke a function solely because a timestamp expires.
-- Retention enforcement and external deletion (OpenSearch / AI caches / object
-- storage) therefore require a scheduler/worker. This migration provides the
-- authoritative configuration, durable work log, and dashboard state.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- 1. TENANT-SCOPED REFERENTIAL INTEGRITY
-- ============================================================

CREATE UNIQUE INDEX IF NOT EXISTS uq_privacy_notices_organization_id_id
    ON consent_privacy_erasure.privacy_notices (organization_id, id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_consent_receipts_organization_id_id
    ON consent_privacy_erasure.consent_receipts (organization_id, id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_erasure_requests_organization_id_id
    ON consent_privacy_erasure.erasure_requests (organization_id, id);

ALTER TABLE consent_privacy_erasure.consent_receipts
    DROP CONSTRAINT IF EXISTS fk_consent_receipts_privacy_notice;

ALTER TABLE consent_privacy_erasure.consent_receipts
    ADD CONSTRAINT fk_consent_receipts_privacy_notice_tenant
    FOREIGN KEY (organization_id, privacy_notice_id)
    REFERENCES consent_privacy_erasure.privacy_notices (organization_id, id);

ALTER TABLE consent_privacy_erasure.erasure_requests
    DROP CONSTRAINT IF EXISTS fk_erasure_requests_consent_receipt;

ALTER TABLE consent_privacy_erasure.erasure_requests
    ADD CONSTRAINT fk_erasure_requests_consent_receipt_tenant
    FOREIGN KEY (organization_id, consent_receipt_id)
    REFERENCES consent_privacy_erasure.consent_receipts (organization_id, id);

-- ============================================================
-- 2. PRV-03 / PRV-04: RECEIPT SNAPSHOT + LAWFUL BASIS
-- ============================================================

ALTER TABLE consent_privacy_erasure.consent_receipts
    ADD COLUMN IF NOT EXISTS privacy_notice_version TEXT;

UPDATE consent_privacy_erasure.consent_receipts cr
SET privacy_notice_version = pn.version
FROM consent_privacy_erasure.privacy_notices pn
WHERE cr.privacy_notice_id = pn.id
  AND cr.privacy_notice_version IS NULL;

ALTER TABLE consent_privacy_erasure.consent_receipts
    ALTER COLUMN privacy_notice_version SET NOT NULL;

ALTER TABLE consent_privacy_erasure.consent_receipts
    ADD COLUMN IF NOT EXISTS lawful_basis_type TEXT;

UPDATE consent_privacy_erasure.consent_receipts
SET lawful_basis_type = 'consent'
WHERE lawful_basis_type IS NULL;

ALTER TABLE consent_privacy_erasure.consent_receipts
    ALTER COLUMN lawful_basis_type SET NOT NULL;

ALTER TABLE consent_privacy_erasure.consent_receipts
    ADD COLUMN IF NOT EXISTS lawful_basis_reference TEXT NULL,
    ADD COLUMN IF NOT EXISTS interaction_reference TEXT NULL,
    ADD COLUMN IF NOT EXISTS receipt_metadata JSONB NOT NULL DEFAULT '{}'::JSONB;

ALTER TABLE consent_privacy_erasure.consent_receipts
    DROP CONSTRAINT IF EXISTS chk_consent_receipts_lawful_basis;

ALTER TABLE consent_privacy_erasure.consent_receipts
    ADD CONSTRAINT chk_consent_receipts_lawful_basis
    CHECK (
        lawful_basis_type IN (
            'consent',
            'contract',
            'legal_obligation',
            'vital_interests',
            'public_task',
            'legitimate_interests',
            'other'
        )
    );

CREATE INDEX IF NOT EXISTS idx_consent_receipts_org_interaction
    ON consent_privacy_erasure.consent_receipts
    (organization_id, interaction_reference, consented_at DESC);

CREATE INDEX IF NOT EXISTS idx_consent_receipts_org_notice_version
    ON consent_privacy_erasure.consent_receipts
    (organization_id, privacy_notice_version, language_shown);

-- ============================================================
-- 3. PRV-06: VERIFIED ERASURE + DURABLE CASCADE LOG
-- ============================================================

ALTER TABLE consent_privacy_erasure.erasure_requests
    ADD COLUMN IF NOT EXISTS verification_method TEXT NULL,
    ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS verified_by UUID NULL,
    ADD COLUMN IF NOT EXISTS certificate_issued_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS identity_anonymized_at TIMESTAMPTZ NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_erasure_requests_verified_by'
          AND conrelid = 'consent_privacy_erasure.erasure_requests'::regclass
    ) THEN
        ALTER TABLE consent_privacy_erasure.erasure_requests
            ADD CONSTRAINT fk_erasure_requests_verified_by
            FOREIGN KEY (verified_by)
            REFERENCES identity_authentication_sessions.users(id);
    END IF;
END $$;

ALTER TABLE consent_privacy_erasure.erasure_requests
    DROP CONSTRAINT IF EXISTS chk_erasure_requests_verified_completion;

ALTER TABLE consent_privacy_erasure.erasure_requests
    ADD CONSTRAINT chk_erasure_requests_verified_completion
    CHECK (
        status <> 'completed'
        OR (
            verified_at IS NOT NULL
            AND certificate IS NOT NULL
            AND certificate_issued_at IS NOT NULL
        )
    );

CREATE TABLE IF NOT EXISTS consent_privacy_erasure.erasure_cascade_log
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    erasure_request_id UUID NOT NULL,
    system_type TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NULL,
    action_type TEXT NOT NULL,
    data_class TEXT NULL,
    outcome TEXT NOT NULL,
    retained BOOLEAN NOT NULL DEFAULT FALSE,
    retention_reason TEXT NULL,
    details JSONB NOT NULL DEFAULT '{}'::JSONB,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ NULL,

    CONSTRAINT pk_erasure_cascade_log PRIMARY KEY (id),
    CONSTRAINT fk_erasure_cascade_log_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT fk_erasure_cascade_log_erasure_request_tenant
        FOREIGN KEY (organization_id, erasure_request_id)
        REFERENCES consent_privacy_erasure.erasure_requests
            (organization_id, id),
    CONSTRAINT chk_erasure_cascade_log_system
        CHECK (system_type IN (
            'postgresql',
            'object_storage',
            'retrieval_index',
            'ai_cache',
            'notification',
            'other'
        )),
    CONSTRAINT chk_erasure_cascade_log_action
        CHECK (action_type IN (
            'remove',
            'anonymize',
            'retain',
            'skip'
        )),
    CONSTRAINT chk_erasure_cascade_log_outcome
        CHECK (outcome IN (
            'pending',
            'completed',
            'failed',
            'retained'
        )),
    CONSTRAINT chk_erasure_cascade_log_retention_reason
        CHECK (
            retained = FALSE
            OR (
                retention_reason IS NOT NULL
                AND length(trim(retention_reason)) > 0
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_erasure_cascade_log_org_request
    ON consent_privacy_erasure.erasure_cascade_log
    (organization_id, erasure_request_id, attempted_at);

CREATE INDEX IF NOT EXISTS idx_erasure_cascade_log_org_outcome
    ON consent_privacy_erasure.erasure_cascade_log
    (organization_id, outcome);

ALTER TABLE consent_privacy_erasure.erasure_cascade_log
    ADD COLUMN IF NOT EXISTS evidence_type TEXT NULL,
    ADD COLUMN IF NOT EXISTS external_reference TEXT NULL,
    ADD COLUMN IF NOT EXISTS evidence_hash TEXT NULL,
    ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS verified_by UUID NULL;

ALTER TABLE consent_privacy_erasure.erasure_cascade_log
    DROP CONSTRAINT IF EXISTS chk_erasure_cascade_log_external_evidence;

ALTER TABLE consent_privacy_erasure.erasure_cascade_log
    ADD CONSTRAINT chk_erasure_cascade_log_external_evidence
    CHECK (
        system_type NOT IN ('retrieval_index', 'ai_cache')
        OR (
            evidence_type IS NOT NULL
            AND length(trim(evidence_type)) > 0
            AND external_reference IS NOT NULL
            AND length(trim(external_reference)) > 0
            AND evidence_hash IS NOT NULL
            AND evidence_hash ~ '^[0-9a-fA-F]{64}$'
            AND verified_at IS NOT NULL
        )
    );

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_erasure_cascade_log_verified_by'
          AND conrelid = 'consent_privacy_erasure.erasure_cascade_log'::regclass
    ) THEN
        ALTER TABLE consent_privacy_erasure.erasure_cascade_log
            ADD CONSTRAINT fk_erasure_cascade_log_verified_by
            FOREIGN KEY (verified_by)
            REFERENCES identity_authentication_sessions.users(id);
    END IF;
END $$;

-- ============================================================
-- 4. PRV-06: ERASURE CERTIFICATE GENERATION
-- ============================================================

CREATE OR REPLACE FUNCTION consent_privacy_erasure.issue_erasure_certificate(
    p_organization_id UUID,
    p_erasure_request_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
DECLARE
    v_certificate JSONB;
    v_verified TIMESTAMPTZ;
BEGIN
    PERFORM app.require_organization_context();

    IF app.current_organization_id() <> p_organization_id THEN
        RAISE EXCEPTION 'PRV-06: organization context mismatch';
    END IF;

    SELECT verified_at
      INTO v_verified
      FROM consent_privacy_erasure.erasure_requests
     WHERE organization_id = p_organization_id
       AND id = p_erasure_request_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'PRV-06: erasure request not found';
    END IF;

    IF v_verified IS NULL THEN
        RAISE EXCEPTION 'PRV-06: erasure request is not verified';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM consent_privacy_erasure.erasure_cascade_log
         WHERE organization_id = p_organization_id
           AND erasure_request_id = p_erasure_request_id
           AND outcome IN ('pending', 'failed')
    ) THEN
        RAISE EXCEPTION 'PRV-06: cascade log contains incomplete actions';
    END IF;

    v_certificate := jsonb_build_object(
        'erasure_request_id', p_erasure_request_id,
        'verified_at', v_verified,
        'issued_at', CURRENT_TIMESTAMP,
        'removed', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'system_type', system_type,
                    'resource_type', resource_type,
                    'resource_id', resource_id,
                    'data_class', data_class,
                    'action', action_type,
                    'evidence_type', evidence_type,
                    'external_reference', external_reference,
                    'evidence_hash', evidence_hash,
                    'verified_at', verified_at,
                    'details', details
                )
            )
            FROM consent_privacy_erasure.erasure_cascade_log
            WHERE organization_id = p_organization_id
              AND erasure_request_id = p_erasure_request_id
              AND retained = FALSE
              AND action_type IN ('remove','anonymize')
              AND outcome = 'completed'
        ), '[]'::JSONB),
        'retained', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'system_type', system_type,
                    'resource_type', resource_type,
                    'resource_id', resource_id,
                    'data_class', data_class,
                    'reason', retention_reason,
                    'details', details
                )
            )
            FROM consent_privacy_erasure.erasure_cascade_log
            WHERE organization_id = p_organization_id
              AND erasure_request_id = p_erasure_request_id
              AND retained = TRUE
        ), '[]'::JSONB)
    );

    UPDATE consent_privacy_erasure.erasure_requests
       SET certificate = v_certificate,
           certificate_issued_at = CURRENT_TIMESTAMP,
           status = 'completed',
           processed_at = COALESCE(processed_at, CURRENT_TIMESTAMP)
     WHERE organization_id = p_organization_id
       AND id = p_erasure_request_id;

    PERFORM audit_trail.append_audit_event(
        p_organization_id,
        NULL,
        NULL,
        NULL,
        'PRIVACY_ERASURE_COMPLETED',
        'erasure_request',
        p_erasure_request_id,
        jsonb_build_object(
            'erasure_request_id', p_erasure_request_id,
            'certificate', v_certificate,
            'identity_retained', FALSE
        ),
        NULL,
        FALSE,
        CURRENT_TIMESTAMP
    );

    RETURN v_certificate;
END;
$$;

-- ============================================================
-- 5. PRV-07: RETENTION CONFIGURATION + ENFORCEMENT LOG
-- ============================================================

ALTER TABLE consent_privacy_erasure.retention_schedules
    ADD COLUMN IF NOT EXISTS legal_hold_required BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS enforcement_started_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS owner_role_name TEXT NOT NULL DEFAULT 'privacy_officer',
    ADD COLUMN IF NOT EXISTS alert_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS alert_before_days INTEGER NOT NULL DEFAULT 0;

ALTER TABLE consent_privacy_erasure.retention_schedules
    DROP CONSTRAINT IF EXISTS chk_retention_schedules_owner_role;

ALTER TABLE consent_privacy_erasure.retention_schedules
    ADD CONSTRAINT chk_retention_schedules_owner_role
    CHECK (length(trim(owner_role_name)) > 0);

ALTER TABLE consent_privacy_erasure.retention_schedules
    DROP CONSTRAINT IF EXISTS chk_retention_schedules_alert_before_days;

ALTER TABLE consent_privacy_erasure.retention_schedules
    ADD CONSTRAINT chk_retention_schedules_alert_before_days
    CHECK (alert_before_days >= 0);

ALTER TABLE consent_privacy_erasure.retention_schedules
    DROP CONSTRAINT IF EXISTS chk_retention_schedules_days;

ALTER TABLE consent_privacy_erasure.retention_schedules
    ADD CONSTRAINT chk_retention_schedules_days
    CHECK (max_retention_days > 0);

CREATE UNIQUE INDEX IF NOT EXISTS uq_retention_schedules_org_data_class
    ON consent_privacy_erasure.retention_schedules
    (organization_id, data_class);

CREATE INDEX IF NOT EXISTS idx_retention_schedules_due
    ON consent_privacy_erasure.retention_schedules
    (organization_id, auto_enforce, max_retention_days);

CREATE TABLE IF NOT EXISTS consent_privacy_erasure.retention_enforcement_log
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    retention_schedule_id UUID NOT NULL,
    data_class TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NULL,
    action_type TEXT NOT NULL,
    outcome TEXT NOT NULL,
    legal_hold_applied BOOLEAN NOT NULL DEFAULT FALSE,
    reason TEXT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_retention_enforcement_log PRIMARY KEY (id),
    CONSTRAINT fk_retention_enforcement_log_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT fk_retention_enforcement_log_schedule_tenant
        FOREIGN KEY (organization_id, retention_schedule_id)
        REFERENCES consent_privacy_erasure.retention_schedules
            (organization_id, id),
    CONSTRAINT chk_retention_enforcement_log_action
        CHECK (action_type IN ('purge','anonymize','retain')),
    CONSTRAINT chk_retention_enforcement_log_outcome
        CHECK (outcome IN ('pending','completed','failed','skipped')),
    CONSTRAINT chk_retention_enforcement_log_hold_reason
        CHECK (
            legal_hold_applied = FALSE
            OR reason IS NOT NULL
        )
);

CREATE INDEX IF NOT EXISTS idx_retention_enforcement_log_org_class
    ON consent_privacy_erasure.retention_enforcement_log
    (organization_id, data_class, executed_at DESC);

-- ============================================================
-- 5A. PRV-07: RETENTION ENFORCEMENT AUTOMATION
-- ============================================================

CREATE TABLE IF NOT EXISTS consent_privacy_erasure.retention_enforcement_queue
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    retention_schedule_id UUID NOT NULL,
    data_class TEXT NOT NULL,
    due_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    queued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    last_error TEXT NULL,

    CONSTRAINT pk_retention_enforcement_queue PRIMARY KEY (id),
    CONSTRAINT fk_retention_enforcement_queue_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT fk_retention_enforcement_queue_schedule_tenant
        FOREIGN KEY (organization_id, retention_schedule_id)
        REFERENCES consent_privacy_erasure.retention_schedules
            (organization_id, id),
    CONSTRAINT chk_retention_enforcement_queue_status
        CHECK (
            status IN ('queued','processing','completed','failed','skipped')
        ),
    CONSTRAINT chk_retention_enforcement_queue_attempts
        CHECK (attempt_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_retention_enforcement_queue_due
    ON consent_privacy_erasure.retention_enforcement_queue
    (organization_id, status, due_at);

-- Scheduler/worker entry point.
-- A scheduler such as pg_cron, an application worker, or a managed
-- scheduler must invoke this function periodically.
CREATE OR REPLACE FUNCTION consent_privacy_erasure.enqueue_due_retention_work(
    p_organization_id UUID DEFAULT NULL
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    INSERT INTO consent_privacy_erasure.retention_enforcement_queue
    (
        organization_id,
        retention_schedule_id,
        data_class,
        due_at
    )
    SELECT
        rs.organization_id,
        rs.id,
        rs.data_class,
        CURRENT_TIMESTAMP
    FROM consent_privacy_erasure.retention_schedules rs
    WHERE rs.auto_enforce = TRUE
      AND (
          p_organization_id IS NULL
          OR rs.organization_id = p_organization_id
      )
      AND NOT EXISTS (
          SELECT 1
          FROM consent_privacy_erasure.retention_enforcement_queue q
          WHERE q.organization_id = rs.organization_id
            AND q.retention_schedule_id = rs.id
            AND q.status IN ('queued','processing')
      );

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

-- ============================================================
-- 5B. PRV-07: ALERTING FRAMEWORK + NAMED OWNERSHIP
-- ============================================================

CREATE TABLE IF NOT EXISTS consent_privacy_erasure.privacy_alert_rules
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    rule_code TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    threshold INTEGER NOT NULL DEFAULT 1,
    owner_role_name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_privacy_alert_rules PRIMARY KEY (id),
    CONSTRAINT fk_privacy_alert_rules_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT uq_privacy_alert_rules_org_code
        UNIQUE (organization_id, rule_code),
    CONSTRAINT chk_privacy_alert_rules_type
        CHECK (
            alert_type IN (
                'erasure_failure',
                'retention_failure',
                'retention_due',
                'legal_hold',
                'external_purge_failure'
            )
        ),
    CONSTRAINT chk_privacy_alert_rules_threshold
        CHECK (threshold >= 1),
    CONSTRAINT chk_privacy_alert_rules_owner
        CHECK (length(trim(owner_role_name)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_privacy_alert_rules_org_enabled
    ON consent_privacy_erasure.privacy_alert_rules
    (organization_id, enabled);

CREATE TABLE IF NOT EXISTS consent_privacy_erasure.privacy_alerts
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    rule_id UUID NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'high',
    owner_role_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    source_reference TEXT NULL,
    message TEXT NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMPTZ NULL,
    resolved_at TIMESTAMPTZ NULL,
    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    CONSTRAINT pk_privacy_alerts PRIMARY KEY (id),
    CONSTRAINT fk_privacy_alerts_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT fk_privacy_alerts_rule_tenant
        FOREIGN KEY (organization_id, rule_id)
        REFERENCES consent_privacy_erasure.privacy_alert_rules
            (organization_id, id),
    CONSTRAINT chk_privacy_alerts_type
        CHECK (
            alert_type IN (
                'erasure_failure',
                'retention_failure',
                'retention_due',
                'legal_hold',
                'external_purge_failure'
            )
        ),
    CONSTRAINT chk_privacy_alerts_severity
        CHECK (severity IN ('low','medium','high','critical')),
    CONSTRAINT chk_privacy_alerts_status
        CHECK (status IN ('open','acknowledged','resolved')),
    CONSTRAINT chk_privacy_alerts_owner
        CHECK (length(trim(owner_role_name)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_privacy_alerts_org_status
    ON consent_privacy_erasure.privacy_alerts
    (organization_id, status, opened_at DESC);

-- Creates durable alert records from current DB-017 obligation failures.
-- A scheduler/worker should invoke this together with
-- enqueue_due_retention_work().
CREATE OR REPLACE FUNCTION consent_privacy_erasure.refresh_privacy_alerts(
    p_organization_id UUID DEFAULT NULL
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER := 0;
BEGIN
    INSERT INTO consent_privacy_erasure.privacy_alerts
    (
        organization_id,
        rule_id,
        alert_type,
        severity,
        owner_role_name,
        source_reference,
        message,
        details
    )
    SELECT
        r.organization_id,
        r.id,
        r.alert_type,
        CASE
            WHEN r.alert_type IN ('external_purge_failure','erasure_failure')
                THEN 'critical'
            ELSE 'high'
        END,
        r.owner_role_name,
        CASE r.alert_type
            WHEN 'external_purge_failure'
                THEN 'erasure_cascade_log'
            WHEN 'erasure_failure'
                THEN 'erasure_requests'
            WHEN 'retention_failure'
                THEN 'retention_enforcement_log'
            WHEN 'retention_due'
                THEN 'retention_enforcement_queue'
            ELSE 'legal_holds'
        END,
        'DB-017 privacy obligation requires attention',
        jsonb_build_object('rule_code', r.rule_code)
    FROM consent_privacy_erasure.privacy_alert_rules r
    WHERE r.enabled = TRUE
      AND (
          p_organization_id IS NULL
          OR r.organization_id = p_organization_id
      )
      AND (
          (r.alert_type = 'erasure_failure' AND EXISTS (
              SELECT 1
              FROM consent_privacy_erasure.erasure_cascade_log e
              WHERE e.organization_id = r.organization_id
                AND e.outcome = 'failed'
          ))
          OR
          (r.alert_type = 'external_purge_failure' AND EXISTS (
              SELECT 1
              FROM consent_privacy_erasure.erasure_cascade_log e
              WHERE e.organization_id = r.organization_id
                AND e.system_type IN ('retrieval_index','ai_cache')
                AND e.outcome = 'failed'
          ))
          OR
          (r.alert_type = 'retention_failure' AND EXISTS (
              SELECT 1
              FROM consent_privacy_erasure.retention_enforcement_log e
              WHERE e.organization_id = r.organization_id
                AND e.outcome = 'failed'
          ))
          OR
          (r.alert_type = 'retention_due' AND EXISTS (
              SELECT 1
              FROM consent_privacy_erasure.retention_enforcement_queue q
              WHERE q.organization_id = r.organization_id
                AND q.status = 'queued'
                AND q.due_at <= CURRENT_TIMESTAMP
          ))
          OR
          (r.alert_type = 'legal_hold' AND EXISTS (
              SELECT 1
              FROM consent_privacy_erasure.legal_holds h
              WHERE h.organization_id = r.organization_id
                AND h.released_at IS NULL
          ))
      )
      AND NOT EXISTS (
          SELECT 1
          FROM consent_privacy_erasure.privacy_alerts a
          WHERE a.organization_id = r.organization_id
            AND a.rule_id = r.id
            AND a.status IN ('open','acknowledged')
            AND a.alert_type = r.alert_type
      );

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

-- ============================================================
-- 6. PRV-07: LIVE OBLIGATIONS DASHBOARD
-- ============================================================

DROP VIEW IF EXISTS consent_privacy_erasure.privacy_obligations_dashboard;

CREATE VIEW consent_privacy_erasure.privacy_obligations_dashboard
WITH (security_invoker = true)
AS
SELECT
    rs.organization_id,
    rs.data_class,
    rs.max_retention_days,
    rs.auto_enforce,
    rs.legal_hold_required,
    rs.owner_role_name,
    rs.alert_enabled,
    rs.alert_before_days,
    rs.updated_at AS schedule_updated_at,
    COALESCE(open_erasure.pending_count, 0) AS pending_erasure_requests,
    COALESCE(failed_cascade.failed_count, 0) AS failed_erasure_actions,
    COALESCE(retention_fail.failed_count, 0) AS failed_retention_actions,
    COALESCE(active_holds.active_count, 0) AS active_legal_holds,
    COALESCE(open_alerts.open_count, 0) AS open_alerts,
    CASE
        WHEN COALESCE(failed_cascade.failed_count, 0) > 0
          OR COALESCE(retention_fail.failed_count, 0) > 0
            THEN 'attention_required'
        WHEN COALESCE(open_erasure.pending_count, 0) > 0
          OR COALESCE(active_holds.active_count, 0) > 0
          OR COALESCE(open_alerts.open_count, 0) > 0
            THEN 'open_obligations'
        ELSE 'clear'
    END AS obligation_status,
    CURRENT_TIMESTAMP AS dashboard_refreshed_at
FROM consent_privacy_erasure.retention_schedules rs
LEFT JOIN (
    SELECT organization_id, count(*) AS pending_count
    FROM consent_privacy_erasure.erasure_requests
    WHERE status IN ('pending','processing')
    GROUP BY organization_id
) open_erasure
  ON open_erasure.organization_id = rs.organization_id
LEFT JOIN (
    SELECT organization_id, count(*) AS failed_count
    FROM consent_privacy_erasure.erasure_cascade_log
    WHERE outcome = 'failed'
    GROUP BY organization_id
) failed_cascade
  ON failed_cascade.organization_id = rs.organization_id
LEFT JOIN (
    SELECT organization_id, count(*) AS failed_count
    FROM consent_privacy_erasure.retention_enforcement_log
    WHERE outcome = 'failed'
    GROUP BY organization_id
) retention_fail
  ON retention_fail.organization_id = rs.organization_id
LEFT JOIN (
    SELECT organization_id, count(*) AS active_count
    FROM consent_privacy_erasure.legal_holds
    WHERE released_at IS NULL
    GROUP BY organization_id
) active_holds
  ON active_holds.organization_id = rs.organization_id
LEFT JOIN (
    SELECT organization_id, count(*) AS open_count
    FROM consent_privacy_erasure.privacy_alerts
    WHERE status IN ('open','acknowledged')
    GROUP BY organization_id
) open_alerts
  ON open_alerts.organization_id = rs.organization_id;

-- ============================================================
-- 7. TENANT ISOLATION
-- ============================================================

DO $$
DECLARE
    v_table TEXT;
BEGIN
    FOREACH v_table IN ARRAY ARRAY[
        'consent_privacy_erasure.privacy_notices',
        'consent_privacy_erasure.consent_receipts',
        'consent_privacy_erasure.erasure_requests',
        'consent_privacy_erasure.retention_schedules',
        'consent_privacy_erasure.legal_holds',
        'consent_privacy_erasure.erasure_cascade_log',
        'consent_privacy_erasure.retention_enforcement_log',
        'consent_privacy_erasure.retention_enforcement_queue',
        'consent_privacy_erasure.privacy_alert_rules',
        'consent_privacy_erasure.privacy_alerts'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', v_table);
        EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', v_table);
    END LOOP;
END $$;

DROP POLICY IF EXISTS db017_privacy_notices_tenant
    ON consent_privacy_erasure.privacy_notices;
CREATE POLICY db017_privacy_notices_tenant
    ON consent_privacy_erasure.privacy_notices
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db017_consent_receipts_tenant
    ON consent_privacy_erasure.consent_receipts;
CREATE POLICY db017_consent_receipts_tenant
    ON consent_privacy_erasure.consent_receipts
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db017_erasure_requests_tenant
    ON consent_privacy_erasure.erasure_requests;
CREATE POLICY db017_erasure_requests_tenant
    ON consent_privacy_erasure.erasure_requests
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db017_retention_schedules_tenant
    ON consent_privacy_erasure.retention_schedules;
CREATE POLICY db017_retention_schedules_tenant
    ON consent_privacy_erasure.retention_schedules
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db017_legal_holds_tenant
    ON consent_privacy_erasure.legal_holds;
CREATE POLICY db017_legal_holds_tenant
    ON consent_privacy_erasure.legal_holds
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());


DROP POLICY IF EXISTS db017_erasure_cascade_log_tenant
    ON consent_privacy_erasure.erasure_cascade_log;
CREATE POLICY db017_erasure_cascade_log_tenant
    ON consent_privacy_erasure.erasure_cascade_log
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db017_retention_enforcement_log_tenant
    ON consent_privacy_erasure.retention_enforcement_log;
CREATE POLICY db017_retention_enforcement_log_tenant
    ON consent_privacy_erasure.retention_enforcement_log
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db017_retention_enforcement_queue_tenant
    ON consent_privacy_erasure.retention_enforcement_queue;
CREATE POLICY db017_retention_enforcement_queue_tenant
    ON consent_privacy_erasure.retention_enforcement_queue
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db017_privacy_alert_rules_tenant
    ON consent_privacy_erasure.privacy_alert_rules;
CREATE POLICY db017_privacy_alert_rules_tenant
    ON consent_privacy_erasure.privacy_alert_rules
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS db017_privacy_alerts_tenant
    ON consent_privacy_erasure.privacy_alerts;
CREATE POLICY db017_privacy_alerts_tenant
    ON consent_privacy_erasure.privacy_alerts
    FOR ALL
    USING (organization_id = app.current_organization_id())
    WITH CHECK (organization_id = app.current_organization_id());

-- The existing append-only, hash-chained audit infrastructure remains the
-- authoritative record of the fact of erasure. DB-017 does not create a
-- second audit chain.

COMMIT;
