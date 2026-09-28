CREATE SCHEMA IF NOT EXISTS authorization_state;

CREATE TABLE IF NOT EXISTS authorization_state.identities (
    subject_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    branch_id TEXT NULL,
    role TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    parent_id TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_identity_parent
        FOREIGN KEY (parent_id)
        REFERENCES authorization_state.identities(subject_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_identity_not_self_parent
        CHECK (parent_id IS NULL OR parent_id <> subject_id)
);

CREATE INDEX IF NOT EXISTS idx_authorization_identities_tenant
    ON authorization_state.identities (tenant_id);

CREATE INDEX IF NOT EXISTS idx_authorization_identities_branch
    ON authorization_state.identities (tenant_id, branch_id);

CREATE INDEX IF NOT EXISTS idx_authorization_identities_parent
    ON authorization_state.identities (parent_id);


CREATE TABLE IF NOT EXISTS authorization_state.grants (
    subject_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    action TEXT NOT NULL,
    branch_id TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_authorization_grant_subject
        FOREIGN KEY (subject_id)
        REFERENCES authorization_state.identities(subject_id)
        ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_authorization_grants
    ON authorization_state.grants (
        subject_id,
        tenant_id,
        resource_type,
        resource_id,
        action,
        branch_id
    );

CREATE INDEX IF NOT EXISTS idx_authorization_grants_subject
    ON authorization_state.grants (subject_id);

CREATE INDEX IF NOT EXISTS idx_authorization_grants_tenant
    ON authorization_state.grants (tenant_id);

CREATE INDEX IF NOT EXISTS idx_authorization_grants_resource
    ON authorization_state.grants (
        tenant_id,
        resource_type,
        resource_id
    );