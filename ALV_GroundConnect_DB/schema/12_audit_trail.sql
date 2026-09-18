CREATE SCHEMA audit_trail;


-- creating table audit_events

CREATE TABLE audit_trail.audit_events (
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    seq BIGSERIAL NOT NULL,

    prev_hash TEXT NOT NULL,

    hash TEXT NOT NULL,

    actor_id UUID NULL,

    acting_for_id UUID NULL,

    session_id UUID NULL,

    action_type TEXT NOT NULL,

    resource_type TEXT NULL,

    resource_id UUID NULL,

    payload JSONB NULL,

    ip_hash TEXT NULL,

    legal_hold BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Primary Key
    CONSTRAINT pk_audit_events
        PRIMARY KEY (id),

    -- Sequence must be unique
    CONSTRAINT unq_audit_events_seq
        UNIQUE (seq)
);

CREATE INDEX idx_audit_events_organization_id
ON audit_trail.audit_events (organization_id);

CREATE INDEX idx_audit_events_action_type
ON audit_trail.audit_events (action_type);

CREATE INDEX idx_audit_events_resource_type
ON audit_trail.audit_events (resource_type);

CREATE INDEX idx_audit_events_created_at
ON audit_trail.audit_events (created_at);







-- creating table audit_checkpoints

CREATE TABLE audit_trail.audit_checkpoints (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    seq_at_checkpoint BIGINT NOT NULL,
    chain_hash TEXT NOT NULL,
    checkpointed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    external_storage_ref TEXT NOT NULL,

    CONSTRAINT pk_audit_checkpoints
        PRIMARY KEY (id)
);

CREATE INDEX idx_audit_checkpoints_organization_id
    ON audit_trail.audit_checkpoints (organization_id);



