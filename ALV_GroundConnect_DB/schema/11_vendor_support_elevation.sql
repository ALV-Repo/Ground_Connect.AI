CREATE SCHEMA vendor_support_elevation;


-- creating table support_elevations

CREATE TABLE vendor_support_elevation.support_elevations (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    operator_id UUID NOT NULL,
    approved_by UUID NOT NULL,
    stated_reason TEXT NOT NULL,
    duration_hours SMALLINT NOT NULL DEFAULT 4,
    granted_at TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NULL,
    expired_at TIMESTAMPTZ NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_support_elevations
        PRIMARY KEY (id),

    CONSTRAINT fk_support_elevations_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_support_elevations_operator
        FOREIGN KEY (operator_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_support_elevations_approved_by
        FOREIGN KEY (approved_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_support_elevations_duration_hours
        CHECK (duration_hours <= 24),

    CONSTRAINT chk_support_elevations_status
        CHECK (
            status IN (
                'pending',
                'active',
                'expired',
                'revoked'
            )
        )
);

CREATE INDEX idx_support_elevations_organization_id
    ON vendor_support_elevation.support_elevations (organization_id);
