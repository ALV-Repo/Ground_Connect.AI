CREATE SCHEMA two_person_integrity;



-- creating table tpi_requests

CREATE TABLE two_person_integrity.tpi_requests (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    action_type TEXT NOT NULL,
    requester_id UUID NOT NULL,
    payload JSONB NOT NULL,
    threshold_context JSONB NOT NULL,
    status TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    break_glass BOOLEAN NOT NULL DEFAULT FALSE,
    break_glass_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_tpi_requests
        PRIMARY KEY (id),

    CONSTRAINT fk_tpi_requests_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_tpi_requests_requester
        FOREIGN KEY (requester_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_tpi_requests_action_type
        CHECK (
            action_type IN (
                'bulk_export',
                'mass_message',
                'bulk_reassign',
                'role_grant',
                'audit_delete',
                'ai_provider_change',
                'security_control_disable',
                'prohibited_firewall_disable',
                'hierarchy_bulk_transfer'
            )
        ),

    CONSTRAINT chk_tpi_requests_status
        CHECK (
            status IN (
                'pending',
                'approved',
                'rejected',
                'expired',
                'break_glass'
            )
        )
);

CREATE INDEX idx_tpi_requests_organization_id
    ON two_person_integrity.tpi_requests (organization_id);

CREATE INDEX idx_tpi_requests_status
    ON two_person_integrity.tpi_requests (status);




-- creating table tpi_approvals


CREATE TABLE two_person_integrity.tpi_approvals (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    request_id UUID NOT NULL,
    approver_id UUID NOT NULL,
    mfa_verified_at TIMESTAMPTZ NOT NULL,
    decision TEXT NOT NULL,
    decision_reason TEXT NULL,
    decided_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT pk_tpi_approvals
        PRIMARY KEY (id),

    CONSTRAINT fk_tpi_approvals_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_tpi_approvals_request
        FOREIGN KEY (request_id)
        REFERENCES two_person_integrity.tpi_requests(id),

    CONSTRAINT fk_tpi_approvals_approver
        FOREIGN KEY (approver_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_tpi_approvals_decision
        CHECK (
            decision IN ('approved', 'rejected')
        )
);
CREATE INDEX idx_tpi_approvals_request_id
    ON two_person_integrity.tpi_approvals (request_id);


-- DEPENDENT CONSTRAINT
ALTER TABLE hierarchy_bitemporal_model.transfers
ADD CONSTRAINT fk_transfers_tpi_request
    FOREIGN KEY (tpi_request_id)
    REFERENCES two_person_integrity.tpi_requests(id);	
	


