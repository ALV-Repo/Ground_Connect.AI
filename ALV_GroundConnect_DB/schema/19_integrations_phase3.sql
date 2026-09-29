-- ============================================================
-- INTEGRATIONS PHASE 3
-- INT-01: Versioned REST API / Credentials / Webhooks
-- INT-02: SMS and Email Provider Abstraction
-- ============================================================

CREATE SCHEMA IF NOT EXISTS integrations_phase3;


-- ============================================================
-- INT-01
-- API CREDENTIALS
-- ============================================================

CREATE TABLE integrations_phase3.api_credentials
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name TEXT NOT NULL,
    client_id TEXT NOT NULL,
    client_secret_hash TEXT NOT NULL,
    scopes TEXT[] NOT NULL,
    rate_limits JSONB NOT NULL,
    webhook_urls TEXT[] NULL,
    webhook_secret_hash TEXT NULL,
    active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_api_credentials
        PRIMARY KEY (id),

    CONSTRAINT fk_api_credentials_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT uq_api_credentials_client_id
        UNIQUE (client_id)
);

CREATE INDEX idx_api_credentials_organization_id
    ON integrations_phase3.api_credentials (organization_id);


-- ============================================================
-- INT-01
-- WEBHOOK DELIVERIES
-- ============================================================

CREATE TABLE integrations_phase3.webhook_deliveries
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    credential_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL,
    response_status INTEGER NULL,
    retry_count SMALLINT NOT NULL,
    next_retry_at TIMESTAMPTZ NULL,
    delivered_at TIMESTAMPTZ NULL,

    CONSTRAINT pk_webhook_deliveries
        PRIMARY KEY (id),

    CONSTRAINT fk_webhook_deliveries_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_webhook_deliveries_credential
        FOREIGN KEY (credential_id)
        REFERENCES integrations_phase3.api_credentials(id)
);

CREATE INDEX idx_webhook_deliveries_organization_id
    ON integrations_phase3.webhook_deliveries (organization_id);


