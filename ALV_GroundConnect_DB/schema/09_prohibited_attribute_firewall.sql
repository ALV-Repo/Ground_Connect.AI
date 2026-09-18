CREATE SCHEMA prohibited_attribute_firewall;


-- CREATING TABLE PROHIBITED_TERMS

CREATE TABLE prohibited_attribute_firewall.prohibited_terms (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NULL,
    term TEXT NOT NULL,
    language TEXT NOT NULL,
    transliterations TEXT[] NOT NULL,
    category TEXT NOT NULL,
    version INTEGER NOT NULL,
    added_by UUID NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    removed_at TIMESTAMPTZ NULL,

    CONSTRAINT pk_prohibited_terms
        PRIMARY KEY (id),

    CONSTRAINT fk_prohibited_terms_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_prohibited_terms_added_by
        FOREIGN KEY (added_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_prohibited_terms_language
        CHECK (
            language IN (
                'en',
                'hi',
                'kn'
            )
        ),

    CONSTRAINT chk_prohibited_terms_category
        CHECK (
            category IN (
                'religion',
                'caste',
                'community',
                'political',
                'persuasion',
                'custom'
            )
        )
);



-- CREATING TABLE PROHIBITED_ALERTS

CREATE TABLE prohibited_attribute_firewall.prohibited_alerts (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    attempted_field TEXT NOT NULL,
    matched_term_id UUID NOT NULL,
    actor_id UUID NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID NULL,
    blocked_at TIMESTAMPTZ NOT NULL,
    reported_to_co_at TIMESTAMPTZ NULL,
    compliance_officer_id UUID NULL,

    CONSTRAINT pk_prohibited_alerts
        PRIMARY KEY (id),

    CONSTRAINT fk_prohibited_alerts_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_prohibited_alerts_matched_term
        FOREIGN KEY (matched_term_id)
        REFERENCES prohibited_attribute_firewall.prohibited_terms(id),

    CONSTRAINT fk_prohibited_alerts_actor
        FOREIGN KEY (actor_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_prohibited_alerts_compliance_officer
        FOREIGN KEY (compliance_officer_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_prohibited_alerts_resource_type
        CHECK (
            resource_type IN (
                'custom_field',
                'free_text',
                'export'
            )
        )
);
-- INDEXES
CREATE INDEX idx_prohibited_alerts_organization_id
    ON prohibited_attribute_firewall.prohibited_alerts (organization_id);

CREATE INDEX idx_prohibited_alerts_blocked_at
    ON prohibited_attribute_firewall.prohibited_alerts (blocked_at);




