CREATE SCHEMA messaging;



-- CREATING TABLE MESSAGES




CREATE TABLE messaging.messages (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    sender_id UUID NOT NULL,
    sender_assignment_id UUID NOT NULL,
    message_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_encrypted BYTEA NOT NULL,
    body_language TEXT NOT NULL,
    target_spec JSONB NOT NULL,
    propagation_policy JSONB NOT NULL,
    response_mode TEXT NOT NULL,
    scheduled_for TIMESTAMPTZ NULL,
    dispatch_started_at TIMESTAMPTZ NULL,
    halt_requested_at TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NULL,
    tpi_request_id UUID NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_messages
        PRIMARY KEY (id),

    CONSTRAINT fk_messages_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_messages_sender
        FOREIGN KEY (sender_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_messages_sender_assignment
        FOREIGN KEY (sender_assignment_id)
        REFERENCES hierarchy_bitemporal_model.node_assignments(id),

    CONSTRAINT fk_messages_tpi_request
        FOREIGN KEY (tpi_request_id)
        REFERENCES two_person_integrity.tpi_requests(id),

    CONSTRAINT chk_messages_message_type
        CHECK (
            message_type IN (
                'Announcement',
                'Instruction',
                'Task-linked',
                'Information',
                'Meeting',
                'Document',
                'Survey',
                'Emergency',
                'Issue-linked'
            )
        ),

    CONSTRAINT chk_messages_response_mode
        CHECK (
            response_mode IN (
                'none',
                'acknowledge',
                'reply_parent',
                'reply_chain',
                'aggregated',
                'escalation'
            )
        ),

    CONSTRAINT chk_messages_status
        CHECK (
            status IN (
                'draft',
                'scheduled',
                'dispatching',
                'dispatched',
                'halted',
                'expired'
            )
        )
);

-- INDEXES

CREATE INDEX idx_messages_organization_id
    ON messaging.messages (organization_id);

CREATE INDEX idx_messages_sender_id
    ON messaging.messages (sender_id);

CREATE INDEX idx_messages_status
    ON messaging.messages (status);


-- CREATING TABLE MESSAGE_RECIPIENTS


CREATE TABLE messaging.message_recipients (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    message_id UUID NOT NULL,
    recipient_id UUID NOT NULL,
    recipient_assignment_id UUID NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    failure_reason TEXT NULL,
    queued_at TIMESTAMPTZ NULL,
    delivered_at TIMESTAMPTZ NULL,
    read_at TIMESTAMPTZ NULL,
    acknowledged_at TIMESTAMPTZ NULL,
    revoked_at TIMESTAMPTZ NULL,
    offline_purge_pending BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT pk_message_recipients
        PRIMARY KEY (id),

    CONSTRAINT fk_message_recipients_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_message_recipients_message
        FOREIGN KEY (message_id)
        REFERENCES messaging.messages(id),

    CONSTRAINT fk_message_recipients_recipient
        FOREIGN KEY (recipient_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_message_recipients_assignment
        FOREIGN KEY (recipient_assignment_id)
        REFERENCES hierarchy_bitemporal_model.node_assignments(id),

    CONSTRAINT chk_message_recipients_channel
        CHECK (
            channel IN (
                'push',
                'in_app',
                'sms',
                'email',
                'whatsapp'
            )
        ),

    CONSTRAINT chk_message_recipients_status
        CHECK (
            status IN (
                'queued',
                'delivered',
                'read',
                'acknowledged',
                'failed',
                'revoked'
            )
        )
);

-- INDEXES
CREATE INDEX idx_message_recipients_organization_id
    ON messaging.message_recipients (organization_id);

CREATE INDEX idx_message_recipients_message_id
    ON messaging.message_recipients (message_id);

CREATE INDEX idx_message_recipients_recipient_id
    ON messaging.message_recipients (recipient_id);

CREATE INDEX idx_message_recipients_status
    ON messaging.message_recipients (status);

CREATE INDEX idx_message_recipients_message_status
    ON messaging.message_recipients (message_id, status);
	
/* CANT CREATE SECOND COMPOSITE INDEX (recipient_id, created_at DESC) for inbox queries , 
BECAUSE CREATED_AT COLUMN NOT PRESENT IN  message_recipients*/


-- CREATING TABLE MESSAGE_GROUPS

CREATE TABLE messaging.message_groups (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    spec JSONB NOT NULL,
    member_ids UUID[] NOT NULL,
    last_recomputed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_message_groups
        PRIMARY KEY (id),

    CONSTRAINT fk_message_groups_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT chk_message_groups_type
        CHECK (
            type IN (
                'hierarchy_level',
                'node_subtree',
                'custom'
            )
        ),

    CONSTRAINT chk_message_groups_spec_object
        CHECK (
            jsonb_typeof(spec) = 'object'
        )
);

CREATE INDEX idx_message_groups_organization_id
    ON messaging.message_groups (organization_id);



