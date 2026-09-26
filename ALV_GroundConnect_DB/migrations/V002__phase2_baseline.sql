-- ============================================================================
-- V002__phase2_baseline.sql
-- PHASE 2 BASELINE MIGRATION
-- ============================================================================
-- Generated strictly from the attached Phase 2 schema files.
--
-- Source execution order is dependency-aware:
--   1. consent_privacy_erasure
--   2. citizen_issues
--   3. ai_governance
--   4. compliance_mode
--   5. documents_meetings
--   6. recurring_tasks
--
-- Prerequisite: Phase 1 baseline objects referenced by foreign keys must exist.
-- ============================================================================

BEGIN;

-- ============================================================================
-- SOURCE 1: 15_consent_privacy_erasure.sql
-- ============================================================================

-- ============================================================
-- PHASE 2: CONSENT, PRIVACY, AND ERASURE
-- ============================================================

-- Required for UUID defaults used by Phase 2 tables.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS consent_privacy_erasure;

-- privacy_notices
CREATE TABLE consent_privacy_erasure.privacy_notices
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    version TEXT NOT NULL,
    language TEXT NOT NULL,
    content TEXT NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL,
    superseded_at TIMESTAMPTZ NULL,

    CONSTRAINT pk_privacy_notices PRIMARY KEY (id),

    CONSTRAINT fk_privacy_notices_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

	CONSTRAINT uq_privacy_notices_org_version_language
        UNIQUE (organization_id, version, language)
);



--  CONSENT RECEIPTS

CREATE TABLE consent_privacy_erasure.consent_receipts
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    citizen_handle TEXT NULL,
    user_id UUID NULL,
    purpose TEXT NOT NULL,
    privacy_notice_id UUID NOT NULL,
    language_shown TEXT NOT NULL,
    mechanism TEXT NOT NULL,
    consented_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    withdrawn_at TIMESTAMPTZ NULL,

    CONSTRAINT pk_consent_receipts PRIMARY KEY (id),

    CONSTRAINT fk_consent_receipts_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_consent_receipts_user
        FOREIGN KEY (user_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_consent_receipts_privacy_notice
        FOREIGN KEY (privacy_notice_id)
        REFERENCES consent_privacy_erasure.privacy_notices(id),

    CONSTRAINT chk_consent_receipts_purpose
        CHECK (
            purpose IN (
                'grievance_resolution',
                'service_notification',
                'internal_comms'
            )
        ),

    CONSTRAINT chk_consent_receipts_mechanism
        CHECK (
            mechanism IN (
                'in_app_tap',
                'voice_confirm',
                'sms_reply'
            )
        ),

    CONSTRAINT chk_consent_receipts_status
        CHECK (
            status IN (
                'active',
                'withdrawn',
                'erasure_requested'
            )
        )
);

CREATE INDEX idx_consent_receipts_organization_id
    ON consent_privacy_erasure.consent_receipts (organization_id);

CREATE INDEX idx_consent_receipts_citizen_handle
    ON consent_privacy_erasure.consent_receipts (citizen_handle);


 
--  ERASURE REQUESTS

CREATE TABLE consent_privacy_erasure.erasure_requests
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    consent_receipt_id UUID NOT NULL,
    requested_by_handle TEXT NULL,
    requested_by_user_id UUID NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ NULL,
    processed_by UUID NULL,
    status TEXT NOT NULL,
    certificate JSONB NULL,

    CONSTRAINT pk_erasure_requests PRIMARY KEY (id),

    CONSTRAINT fk_erasure_requests_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_erasure_requests_consent_receipt
        FOREIGN KEY (consent_receipt_id)
        REFERENCES consent_privacy_erasure.consent_receipts(id),

    CONSTRAINT fk_erasure_requests_requested_by_user
        FOREIGN KEY (requested_by_user_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_erasure_requests_processed_by
        FOREIGN KEY (processed_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_erasure_requests_status
        CHECK (
            status IN (
                'pending',
                'processing',
                'completed',
                'rejected'
            )
        )
);

CREATE INDEX idx_erasure_requests_organization_id
    ON consent_privacy_erasure.erasure_requests (organization_id);



--  RETENTION SCHEDULES

CREATE TABLE consent_privacy_erasure.retention_schedules
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    data_class TEXT NOT NULL,
    max_retention_days INTEGER NOT NULL,
    auto_enforce BOOLEAN NOT NULL,
    legal_hold_exempt BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_retention_schedules PRIMARY KEY (id),

    CONSTRAINT fk_retention_schedules_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id)
);

CREATE INDEX idx_retention_schedules_organization_id
    ON consent_privacy_erasure.retention_schedules (organization_id);



-- LEGAL HOLDS

CREATE TABLE consent_privacy_erasure.legal_holds
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID NULL,
    placed_by UUID NOT NULL,
    placed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason TEXT NOT NULL,
    released_at TIMESTAMPTZ NULL,
    released_by UUID NULL,

    CONSTRAINT pk_legal_holds PRIMARY KEY (id),

    CONSTRAINT fk_legal_holds_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_legal_holds_placed_by
        FOREIGN KEY (placed_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_legal_holds_released_by
        FOREIGN KEY (released_by)
        REFERENCES identity_authentication_sessions.users(id)
);

CREATE INDEX idx_legal_holds_organization_id
    ON consent_privacy_erasure.legal_holds (organization_id);


-- ============================================================

-- ============================================================================
-- SOURCE 2: 14_citizen_issues.sql
-- ============================================================================

-- ============================================================
-- PHASE 2: CITIZEN SERVICE / ISSUE MANAGEMENT
-- ============================================================

-- Required by citizen_submissions/canonical_issues location columns.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS citizen_issues;

-- canonical_issues
CREATE TABLE citizen_issues.canonical_issues
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    ref_number TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    location GEOGRAPHY(POINT, 4326) NULL,
    assigned_node_id UUID NULL,
    status TEXT NOT NULL,
    distinct_citizen_count INTEGER NOT NULL DEFAULT 0,
    total_corroboration_count INTEGER NOT NULL DEFAULT 0,
    sla_response_deadline TIMESTAMPTZ NULL,
    sla_resolution_deadline TIMESTAMPTZ NULL,
    sla_breach_count INTEGER NOT NULL DEFAULT 0,
    claimed_resolved_at TIMESTAMPTZ NULL,
    confirmed_resolved_at TIMESTAMPTZ NULL,
    rejection_reason TEXT NULL,
    disputed_at TIMESTAMPTZ NULL,
    dispute_sla_resolution_deadline TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_canonical_issues PRIMARY KEY (id),

    CONSTRAINT fk_canonical_issues_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_canonical_issues_assigned_node
        FOREIGN KEY (assigned_node_id)
        REFERENCES hierarchy_bitemporal_model.nodes(id),

    CONSTRAINT uq_canonical_issues_ref_number
        UNIQUE (ref_number),

    CONSTRAINT chk_canonical_issues_status
        CHECK (
            status IN (
                'New',
                'Assigned',
                'Accepted',
                'In_Progress',
                'Waiting',
                'Escalated',
                'Resolution_Proposed',
                'Resolved_Confirmed',
                'Resolved_Unconfirmed',
                'Disputed_Reopened',
                'Closed',
                'Rejected'
            )
        ),

    CONSTRAINT chk_canonical_issues_distinct_citizen_count
        CHECK (distinct_citizen_count >= 0),

    CONSTRAINT chk_canonical_issues_total_corroboration_count
        CHECK (total_corroboration_count >= 0),

    CONSTRAINT chk_canonical_issues_sla_breach_count
        CHECK (sla_breach_count >= 0),

    CONSTRAINT chk_canonical_issues_citizen_count
        CHECK (distinct_citizen_count <= total_corroboration_count),

    CONSTRAINT chk_canonical_issues_rejection_reason
        CHECK (
            status <> 'Rejected'
            OR (
                rejection_reason IS NOT NULL
                AND length(trim(rejection_reason)) > 0
            )
        )
);

CREATE INDEX idx_canonical_issues_organization_id
    ON citizen_issues.canonical_issues (organization_id);

CREATE INDEX idx_canonical_issues_status
    ON citizen_issues.canonical_issues (status);

CREATE INDEX idx_canonical_issues_location_gist
    ON citizen_issues.canonical_issues
    USING GIST (location);

CREATE INDEX idx_canonical_issues_org_status_sla
    ON citizen_issues.canonical_issues
    (organization_id, status, sla_resolution_deadline);



--  CITIZEN SUBMISSIONS

CREATE TABLE citizen_issues.citizen_submissions
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    ref_number TEXT NOT NULL,
    anonymous BOOLEAN NOT NULL,
    citizen_handle TEXT NULL,
    text TEXT NULL,
    voice_storage_key TEXT NULL,
    photo_keys TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    video_keys TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    location GEOGRAPHY(POINT, 4326) NULL,
    consent_receipt_id UUID NOT NULL,
    ai_category TEXT NULL,
    ai_priority TEXT NULL,
    ai_location_note TEXT NULL,
    human_category TEXT NULL,
    human_priority TEXT NULL,
    human_location_note TEXT NULL,
    classified_by UUID NULL,
    classified_at TIMESTAMPTZ NULL,
    canonical_issue_id UUID NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_citizen_submissions PRIMARY KEY (id),

    CONSTRAINT fk_citizen_submissions_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_citizen_submissions_consent_receipt
        FOREIGN KEY (consent_receipt_id)
        REFERENCES consent_privacy_erasure.consent_receipts(id),

    CONSTRAINT fk_citizen_submissions_classified_by
        FOREIGN KEY (classified_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_citizen_submissions_canonical_issue
        FOREIGN KEY (canonical_issue_id)
        REFERENCES citizen_issues.canonical_issues(id),

    CONSTRAINT uq_citizen_submissions_ref_number
        UNIQUE (ref_number),

    CONSTRAINT chk_citizen_submissions_canonical_requires_classification
        CHECK (
            canonical_issue_id IS NULL
            OR classified_by IS NOT NULL
        )
);

CREATE INDEX idx_citizen_submissions_organization_id
    ON citizen_issues.citizen_submissions (organization_id);

CREATE INDEX idx_citizen_submissions_submitted_at
    ON citizen_issues.citizen_submissions (submitted_at);



-- ISSUE HISTORY

CREATE TABLE citizen_issues.issue_history
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    canonical_issue_id UUID NOT NULL,
    from_status TEXT NULL,
    to_status TEXT NOT NULL,
    actor_id UUID NULL,
    reason TEXT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_issue_history PRIMARY KEY (id),

    CONSTRAINT fk_issue_history_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_issue_history_canonical_issue
        FOREIGN KEY (canonical_issue_id)
        REFERENCES citizen_issues.canonical_issues(id),

    CONSTRAINT fk_issue_history_actor
        FOREIGN KEY (actor_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_issue_history_from_status
        CHECK (
            from_status IS NULL
            OR from_status IN (
                'New',
                'Assigned',
                'Accepted',
                'In_Progress',
                'Waiting',
                'Escalated',
                'Resolution_Proposed',
                'Resolved_Confirmed',
                'Resolved_Unconfirmed',
                'Disputed_Reopened',
                'Closed',
                'Rejected'
            )
        ),

    CONSTRAINT chk_issue_history_to_status
        CHECK (
            to_status IN (
                'New',
                'Assigned',
                'Accepted',
                'In_Progress',
                'Waiting',
                'Escalated',
                'Resolution_Proposed',
                'Resolved_Confirmed',
                'Resolved_Unconfirmed',
                'Disputed_Reopened',
                'Closed',
                'Rejected'
            )
        )
);

CREATE INDEX idx_issue_history_organization_id
    ON citizen_issues.issue_history (organization_id);

CREATE INDEX idx_issue_history_canonical_issue_id
    ON citizen_issues.issue_history (canonical_issue_id);



-- CLOSURE CONFIRMATIONS

CREATE TABLE citizen_issues.closure_confirmations
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    canonical_issue_id UUID NOT NULL,
    citizen_handle TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    channel TEXT NOT NULL,
    language TEXT NOT NULL,
    response TEXT NULL,
    responded_at TIMESTAMPTZ NULL,
    otp_hash TEXT NULL,
    triggered_by_actor UUID NULL,

    CONSTRAINT pk_closure_confirmations PRIMARY KEY (id),

    CONSTRAINT fk_closure_confirmations_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_closure_confirmations_canonical_issue
        FOREIGN KEY (canonical_issue_id)
        REFERENCES citizen_issues.canonical_issues(id),

    CONSTRAINT fk_closure_confirmations_triggered_by_actor
        FOREIGN KEY (triggered_by_actor)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_closure_confirmations_channel
        CHECK (channel IN ('sms', 'voice', 'in_app')),

    CONSTRAINT chk_closure_confirmations_response
        CHECK (
            response IS NULL
            OR response IN ('confirmed', 'disputed')
        )
);

CREATE INDEX idx_closure_confirmations_organization_id
    ON citizen_issues.closure_confirmations (organization_id);

CREATE INDEX idx_closure_confirmations_canonical_issue_id
    ON citizen_issues.closure_confirmations (canonical_issue_id);

CREATE INDEX idx_closure_confirmations_citizen_handle
    ON citizen_issues.closure_confirmations (citizen_handle);



-- AI CLASSIFICATION FEEDBACK

CREATE TABLE citizen_issues.ai_classification_feedback
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    submission_id UUID NOT NULL,
    ai_category TEXT NOT NULL,
    ai_priority TEXT NOT NULL,
    human_category TEXT NOT NULL,
    human_priority TEXT NOT NULL,
    corrected_by UUID NOT NULL,
    corrected_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT pk_ai_classification_feedback PRIMARY KEY (id),

    CONSTRAINT fk_ai_classification_feedback_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_ai_classification_feedback_submission
        FOREIGN KEY (submission_id)
        REFERENCES citizen_issues.citizen_submissions(id),

    CONSTRAINT fk_ai_classification_feedback_corrected_by
        FOREIGN KEY (corrected_by)
        REFERENCES identity_authentication_sessions.users(id)
);

CREATE INDEX idx_ai_classification_feedback_organization_id
    ON citizen_issues.ai_classification_feedback (organization_id);



-- SLA CONFIG

CREATE TABLE citizen_issues.sla_config
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    response_target_minutes INTEGER NOT NULL,
    resolution_target_minutes INTEGER NOT NULL,
    escalation_chain JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_sla_config PRIMARY KEY (id),

    CONSTRAINT fk_sla_config_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT uq_sla_config_organization_category_priority
        UNIQUE (organization_id, category, priority),

    CONSTRAINT chk_sla_config_priority
        CHECK (priority IN ('High', 'Medium', 'Low'))
);

CREATE INDEX idx_sla_config_organization_id
    ON citizen_issues.sla_config (organization_id);



-- SERVICE DEBT INDEX

CREATE TABLE citizen_issues.service_debt_index
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    node_id UUID NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    score NUMERIC(5,2) NOT NULL,
    unresolved_weighted NUMERIC(10,4) NOT NULL,
    confirmed_resolution_rate NUMERIC(5,4) NOT NULL,
    corroboration_weighted_severity NUMERIC(10,4) NOT NULL,
    sla_breach_frequency NUMERIC(10,4) NOT NULL,
    unit_size INTEGER NOT NULL,
    intake_count INTEGER NOT NULL,
    source_issue_ids UUID[] NOT NULL,

    CONSTRAINT pk_service_debt_index PRIMARY KEY (id),

    CONSTRAINT fk_service_debt_index_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_service_debt_index_node
        FOREIGN KEY (node_id)
        REFERENCES hierarchy_bitemporal_model.nodes(id),

    CONSTRAINT chk_service_debt_index_score
        CHECK (score >= 0 AND score <= 100),

    CONSTRAINT chk_service_debt_index_resolution_rate
        CHECK (
            confirmed_resolution_rate >= 0
            AND confirmed_resolution_rate <= 1
        ),

    CONSTRAINT chk_service_debt_index_unit_size
        CHECK (unit_size >= 0),

    CONSTRAINT chk_service_debt_index_intake_count
        CHECK (intake_count >= 0)
);

CREATE INDEX idx_service_debt_index_organization_id
    ON citizen_issues.service_debt_index (organization_id);

CREATE INDEX idx_service_debt_index_node_id
    ON citizen_issues.service_debt_index (node_id);

CREATE INDEX idx_service_debt_index_computed_at
    ON citizen_issues.service_debt_index (computed_at);


-- ============================================================

-- ============================================================================
-- SOURCE 3: 13_ai_governance.sql
-- ============================================================================

-- ============================================================
-- PHASE 2: AI GOVERNANCE
-- ============================================================
-- SRS / Review coverage:
--   AIB-08  ai_query_log append-only + AI gateway INSERT only
--   AID-01  ai_providers TPI-gated changes
--   AID-02  opaque user_handle
--   AID-03  no-training guarantee documentation
--   AID-04  provider governance approval
--   AIC-06  AI evaluation results for CI/CD release gating
--
-- Review requirement:
--   ai_query_log, ai_providers, ai_eval_results,
-- ============================================================

CREATE SCHEMA IF NOT EXISTS ai_governance;


-- 1. AI QUERY LOG


CREATE TABLE ai_governance.ai_query_log
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    user_handle TEXT NOT NULL,
    session_id UUID NOT NULL,
    feature TEXT NOT NULL,
    retrieval_scope JSONB NOT NULL,
    citations JSONB NOT NULL,
    denied BOOLEAN NOT NULL,
    denial_reason TEXT NULL,
    tokens_in INTEGER NULL,
    tokens_out INTEGER NULL,
    provider TEXT NULL,
    queried_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_ai_query_log PRIMARY KEY (id),

    CONSTRAINT fk_ai_query_log_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_ai_query_log_session
        FOREIGN KEY (session_id)
        REFERENCES identity_authentication_sessions.sessions(id),

    CONSTRAINT chk_ai_query_log_feature
        CHECK (
            feature IN (
                'copilot',
                'daily_briefing',
                'summariser',
                'translation',
                'voice',
                'classifier',
                'analytics',
                'dark_radar',
                'meeting_analysis'
            )
        )
);

CREATE INDEX idx_ai_query_log_organization_id
    ON ai_governance.ai_query_log (organization_id);

CREATE INDEX idx_ai_query_log_queried_at
    ON ai_governance.ai_query_log (queried_at);


-- ============================================================
-- AIB-08: APPEND-ONLY ENFORCEMENT
-- ============================================================

CREATE OR REPLACE FUNCTION ai_governance.prevent_ai_query_log_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'ai_governance.ai_query_log is append-only; % is not permitted',
        TG_OP;
END;
$$;

CREATE TRIGGER trg_ai_query_log_append_only
BEFORE UPDATE OR DELETE
ON ai_governance.ai_query_log
FOR EACH ROW
EXECUTE FUNCTION ai_governance.prevent_ai_query_log_mutation();


-- ============================================================
-- AIB-08: AI GATEWAY INSERT-ONLY PRIVILEGE
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'ai_gateway_app_role'
    ) THEN
        CREATE ROLE ai_gateway_app_role NOLOGIN;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA ai_governance TO ai_gateway_app_role;
GRANT INSERT ON ai_governance.ai_query_log TO ai_gateway_app_role;
REVOKE UPDATE, DELETE, TRUNCATE ON ai_governance.ai_query_log
FROM ai_gateway_app_role;



-- 2. AI PROVIDERS


CREATE TABLE ai_governance.ai_providers
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name TEXT NOT NULL,
    endpoint_type TEXT NOT NULL,
    endpoint_url TEXT NULL,
    no_training_guarantee BOOLEAN NOT NULL,
    no_training_doc_ref TEXT NULL,
    governance_approval_by UUID NULL,
    governance_approved_at TIMESTAMPTZ NULL,
    active BOOLEAN NOT NULL,
    tpi_request_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_ai_providers PRIMARY KEY (id),

    CONSTRAINT fk_ai_providers_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_ai_providers_governance_approval_by
        FOREIGN KEY (governance_approval_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_ai_providers_tpi_request
        FOREIGN KEY (tpi_request_id)
        REFERENCES two_person_integrity.tpi_requests(id),

    CONSTRAINT chk_ai_providers_endpoint_type
        CHECK (
            endpoint_type IN (
                'hosted',
                'self_hosted',
                'private_endpoint'
            )
        )
);

CREATE INDEX idx_ai_providers_organization_id
    ON ai_governance.ai_providers (organization_id);


-- ============================================================
-- AID-01: TPI GATE
-- Every INSERT/UPDATE requires:
--   1. tpi_request_id is present
--   2. TPI belongs to the same organization
--   3. action_type = ai_provider_change
--   4. status = approved


CREATE OR REPLACE FUNCTION ai_governance.validate_ai_provider_tpi()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ai_governance, two_person_integrity, pg_catalog
AS $$
DECLARE
    v_tpi_organization_id UUID;
    v_tpi_action_type TEXT;
    v_tpi_status TEXT;
BEGIN
    IF NEW.tpi_request_id IS NULL THEN
        RAISE EXCEPTION
            'AI provider change requires an approved TPI request';
    END IF;

    SELECT
        organization_id,
        action_type,
        status
    INTO
        v_tpi_organization_id,
        v_tpi_action_type,
        v_tpi_status
    FROM two_person_integrity.tpi_requests
    WHERE id = NEW.tpi_request_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'TPI request % does not exist',
            NEW.tpi_request_id;
    END IF;

    IF v_tpi_organization_id <> NEW.organization_id THEN
        RAISE EXCEPTION
            'TPI request belongs to a different organization';
    END IF;

    IF v_tpi_action_type <> 'ai_provider_change' THEN
        RAISE EXCEPTION
            'TPI request % is not an ai_provider_change request',
            NEW.tpi_request_id;
    END IF;

    IF v_tpi_status <> 'approved' THEN
        RAISE EXCEPTION
            'TPI request % is not approved; current status: %',
            NEW.tpi_request_id,
            v_tpi_status;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_ai_providers_tpi_gate
BEFORE INSERT OR UPDATE
ON ai_governance.ai_providers
FOR EACH ROW
EXECUTE FUNCTION ai_governance.validate_ai_provider_tpi();



-- 3. AI EVALUATION RESULTS


CREATE TABLE ai_governance.ai_eval_results
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    metric_name TEXT NOT NULL,
    value NUMERIC(6,4) NOT NULL,
    threshold NUMERIC(6,4) NOT NULL,
    passing BOOLEAN NOT NULL,
    eval_set_version TEXT NOT NULL,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_ai_eval_results PRIMARY KEY (id),

    CONSTRAINT fk_ai_eval_results_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT chk_ai_eval_results_metric_name
        CHECK (
            metric_name IN (
                'hallucination_rate',
                'citation_validity',
                'correct_abstention_rate',
                'classification_accuracy'
            )
        )
);

CREATE INDEX idx_ai_eval_results_organization_id
    ON ai_governance.ai_eval_results (organization_id);

CREATE INDEX idx_ai_eval_results_measured_at
    ON ai_governance.ai_eval_results (measured_at);


-- ============================================================
-- AIC-06: CI/CD RELEASE GATE QUERY
-- ============================================================
-- The release pipeline must fail when a release-blocking
-- evaluation result has passing = FALSE.
--
-- Gate query:
--
-- SELECT EXISTS (
--     SELECT 1
--     FROM ai_governance.ai_eval_results
--     WHERE passing = FALSE
-- ) AS release_blocked;

-- ============================================================

-- ============================================================================
-- SOURCE 4: 16_compliance_mode.sql
-- ============================================================================

-- ============================================================
-- PHASE 2: COMPLIANCE MODE
-- ============================================================

CREATE SCHEMA IF NOT EXISTS compliance_mode;

-- compliance_profiles

CREATE TABLE compliance_mode.compliance_profiles
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    config JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_compliance_profiles PRIMARY KEY (id),

    CONSTRAINT fk_compliance_profiles_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id)
);

CREATE INDEX idx_compliance_profiles_organization_id
    ON compliance_mode.compliance_profiles (organization_id);



--  COMPLIANCE PROFILE ACTIVATIONS

CREATE TABLE compliance_mode.compliance_profile_activations
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    profile_config_snapshot JSONB NOT NULL,
    activated_at TIMESTAMPTZ NOT NULL,
    activated_by UUID NOT NULL,
    deactivated_at TIMESTAMPTZ NULL,
    deactivated_by UUID NULL,

    CONSTRAINT pk_compliance_profile_activations PRIMARY KEY (id),

    CONSTRAINT fk_compliance_profile_activations_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_compliance_profile_activations_profile
        FOREIGN KEY (profile_id)
        REFERENCES compliance_mode.compliance_profiles(id),

    CONSTRAINT fk_compliance_profile_activations_activated_by
        FOREIGN KEY (activated_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_compliance_profile_activations_deactivated_by
        FOREIGN KEY (deactivated_by)
        REFERENCES identity_authentication_sessions.users(id)
);

CREATE INDEX idx_compliance_profile_activations_organization_id
    ON compliance_mode.compliance_profile_activations (organization_id);


-- ============================================================

-- ============================================================================
-- SOURCE 5: 17_documents_meetings.sql
-- ============================================================================

-- ============================================================
-- PHASE 2: DOCUMENTS AND MEETINGS
-- ============================================================

CREATE SCHEMA IF NOT EXISTS documents_meetings;

-- documents

CREATE TABLE documents_meetings.documents
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    uploader_id UUID NOT NULL,
    title TEXT NOT NULL,
    object_storage_key TEXT NOT NULL,
    media_type TEXT NOT NULL,
    malware_scanned BOOLEAN NOT NULL,
    malware_scan_at TIMESTAMPTZ NULL,
    exif_stripped_key TEXT NULL,
    original_metadata_key TEXT NULL,
    policy JSONB NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_documents PRIMARY KEY (id),

    CONSTRAINT fk_documents_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_documents_uploader
        FOREIGN KEY (uploader_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_documents_media_type
        CHECK (
            media_type IN (
                'pdf',
                'image',
                'video',
                'office'
            )
        )
);

CREATE INDEX idx_documents_organization_id
    ON documents_meetings.documents (organization_id);


--  MEETINGS

CREATE TABLE documents_meetings.meetings
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    title TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    location TEXT NULL,
    organizer_id UUID NOT NULL,
    participant_ids UUID[] NOT NULL,
    agenda TEXT NULL,
    recording_storage_key TEXT NULL,
    recording_consent_captured BOOLEAN NOT NULL,
    consent_receipt_ids UUID[] NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_meetings PRIMARY KEY (id),

    CONSTRAINT fk_meetings_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_meetings_organizer
        FOREIGN KEY (organizer_id)
        REFERENCES identity_authentication_sessions.users(id)
);

CREATE INDEX idx_meetings_organization_id
    ON documents_meetings.meetings (organization_id);


--  MEETING ACTION ITEMS

CREATE TABLE documents_meetings.meeting_action_items
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    meeting_id UUID NOT NULL,
    proposed_task JSONB NOT NULL,
    ai_confidence NUMERIC(4,3) NULL,
    confirmed_task_id UUID NULL,
    confirmed_at TIMESTAMPTZ NULL,
    confirmed_by UUID NULL,
    rejected_at TIMESTAMPTZ NULL,
    rejected_by UUID NULL,

    CONSTRAINT pk_meeting_action_items PRIMARY KEY (id),

    CONSTRAINT fk_meeting_action_items_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_meeting_action_items_meeting
        FOREIGN KEY (meeting_id)
        REFERENCES documents_meetings.meetings(id),

    CONSTRAINT fk_meeting_action_items_confirmed_task
        FOREIGN KEY (confirmed_task_id)
        REFERENCES tasks_field_reports.tasks(id),

    CONSTRAINT fk_meeting_action_items_confirmed_by
        FOREIGN KEY (confirmed_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_meeting_action_items_rejected_by
        FOREIGN KEY (rejected_by)
        REFERENCES identity_authentication_sessions.users(id)
);

CREATE INDEX idx_meeting_action_items_organization_id
    ON documents_meetings.meeting_action_items (organization_id);

CREATE INDEX idx_meeting_action_items_meeting_id
    ON documents_meetings.meeting_action_items (meeting_id);


-- ============================================================

-- ============================================================================
-- SOURCE 6: 18_recurring_tasks.sql
-- ============================================================================

-- ============================================================
-- PHASE 2: RECURRING TASK TEMPLATES
-- ============================================================

CREATE SCHEMA IF NOT EXISTS recurring_tasks;

-- recurring_task_templates

CREATE TABLE recurring_tasks.recurring_task_templates
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    title_template TEXT NOT NULL,
    description TEXT NULL,
    assignee_role TEXT NOT NULL,
    priority TEXT NOT NULL,
    schedule_type TEXT NOT NULL,
    cron_expression TEXT NULL,
    deadline_offset_hours INTEGER NULL,
    escalation_rule JSONB NULL,
    active BOOLEAN NOT NULL,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_recurring_task_templates PRIMARY KEY (id),

    CONSTRAINT fk_recurring_task_templates_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_recurring_task_templates_created_by
        FOREIGN KEY (created_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_recurring_task_templates_schedule_type
        CHECK (
            schedule_type IN (
                'daily',
                'weekly',
                'monthly',
                'custom_cron'
            )
        )
);

CREATE INDEX idx_recurring_task_templates_organization_id
    ON recurring_tasks.recurring_task_templates (organization_id);

COMMIT;
