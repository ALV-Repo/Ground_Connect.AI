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
