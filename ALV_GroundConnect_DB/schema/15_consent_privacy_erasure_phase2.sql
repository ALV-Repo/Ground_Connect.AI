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

