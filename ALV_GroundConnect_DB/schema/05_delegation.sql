CREATE SCHEMA delegation;


-- CRATING TABLE DELEGATIONS

CREATE TABLE delegation.delegations (
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    delegator_id UUID NOT NULL,

    delegatee_id UUID NOT NULL,

    scope JSONB NOT NULL,

    depth SMALLINT NOT NULL
        CHECK (depth >= 1),

    valid_from TIMESTAMPTZ NOT NULL,

    valid_to TIMESTAMPTZ NOT NULL,

    revoked_at TIMESTAMPTZ NULL,

    revoked_by UUID NULL,

    created_at TIMESTAMPTZ NOT NULL,


    -- Primary Key
    CONSTRAINT pk_delegations
        PRIMARY KEY (id),

    -- Foreign Keys
    CONSTRAINT fk_delegations_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_delegations_delegator
        FOREIGN KEY (delegator_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_delegations_delegatee
        FOREIGN KEY (delegatee_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_delegations_revoked_by
        FOREIGN KEY (revoked_by)
        REFERENCES identity_authentication_sessions.users(id)
);



-- INDEXES
CREATE INDEX idx_delegations_organization_id
ON delegation.delegations (organization_id);

CREATE INDEX idx_delegations_delegator_id
ON delegation.delegations (delegator_id);

CREATE INDEX idx_delegations_delegatee_id
ON delegation.delegations (delegatee_id);

-- DEPENDENT CONSTRAINT

ALTER TABLE hierarchy_bitemporal_model.node_assignments
ADD CONSTRAINT fk_node_assignments_delegation
    FOREIGN KEY (delegation_id)
    REFERENCES delegation.delegations(id);

