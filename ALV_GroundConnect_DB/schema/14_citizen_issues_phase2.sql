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

