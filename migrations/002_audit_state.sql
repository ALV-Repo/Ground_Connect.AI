CREATE SCHEMA IF NOT EXISTS audit_state;

CREATE TABLE IF NOT EXISTS audit_state.authorization_decisions (
    record_id TEXT PRIMARY KEY,
    timestamp DOUBLE PRECISION NOT NULL,

    subject_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,

    decision TEXT NOT NULL,
    reason TEXT NOT NULL,

    rules_evaluated JSONB NOT NULL DEFAULT '[]'::JSONB,
    failing_rule TEXT NULL,

    tenant_id TEXT NULL,
    branch_id TEXT NULL,
    correlation_id TEXT NULL,
    source TEXT NULL,

    CONSTRAINT chk_audit_decision
        CHECK (decision IN ('ALLOW', 'DENY'))
);

CREATE INDEX IF NOT EXISTS idx_audit_decisions_subject
    ON audit_state.authorization_decisions (subject_id);

CREATE INDEX IF NOT EXISTS idx_audit_decisions_tenant
    ON audit_state.authorization_decisions (tenant_id);

CREATE INDEX IF NOT EXISTS idx_audit_decisions_resource
    ON audit_state.authorization_decisions (
        resource_type,
        resource_id
    );

CREATE INDEX IF NOT EXISTS idx_audit_decisions_timestamp
    ON audit_state.authorization_decisions (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_decisions_decision
    ON audit_state.authorization_decisions (decision);