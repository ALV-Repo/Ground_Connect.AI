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

