CREATE SCHEMA IF NOT EXISTS audit_trail;

-- ============================================================
-- AUDIT EVENTS
-- Monthly range partitioning by created_at.
-- ============================================================

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

    -- Partitioned-table primary key must include the partition key.
    CONSTRAINT pk_audit_events
        PRIMARY KEY (id, created_at),

    -- seq is generated from one global PostgreSQL sequence.
    -- Therefore seq remains globally monotonic/unique in normal operation.
    -- A standalone UNIQUE(seq) constraint is not possible on a range-partitioned
    -- table unless created with the partition key included.
    CONSTRAINT unq_audit_events_seq_created_at
        UNIQUE (seq, created_at)
)
PARTITION BY RANGE (created_at);

-- ============================================================
-- PARTITION CREATION FUNCTION
-- Creates one monthly partition when it does not already exist.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.create_monthly_audit_partition(
    p_month_start DATE
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_month_start TIMESTAMPTZ;
    v_next_month  TIMESTAMPTZ;
    v_partition_name TEXT;
BEGIN
    v_month_start := p_month_start::TIMESTAMPTZ;
    v_next_month  := (p_month_start + INTERVAL '1 month')::TIMESTAMPTZ;

    v_partition_name := format(
        'audit_events_%s',
        to_char(p_month_start, 'YYYY_MM')
    );

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS audit_trail.%I PARTITION OF audit_trail.audit_events
         FOR VALUES FROM (%L) TO (%L)',
        v_partition_name,
        v_month_start,
        v_next_month
    );
END;
$$;

-- ============================================================
-- CREATE CURRENT + FUTURE MONTHLY PARTITIONS
-- Creates the current month plus the next 12 months.
-- ============================================================

CREATE OR REPLACE FUNCTION audit_trail.create_future_audit_partitions(
    p_months_ahead INTEGER DEFAULT 12
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_month_start DATE;
    v_i INTEGER;
BEGIN
    IF p_months_ahead < 0 OR p_months_ahead > 120 THEN
        RAISE EXCEPTION 'p_months_ahead must be between 0 and 120';
    END IF;

    v_month_start := date_trunc('month', CURRENT_TIMESTAMP)::DATE;

    FOR v_i IN 0..p_months_ahead LOOP
        PERFORM audit_trail.create_monthly_audit_partition(
            (v_month_start + make_interval(months => v_i))::DATE
        );
    END LOOP;
END;
$$;

-- Create the current month and the next 12 months immediately.
SELECT audit_trail.create_future_audit_partitions(12);

-- ============================================================
-- INDEXES
-- These are created on the partitioned parent and propagated to
-- every existing/future partition automatically.
-- ============================================================

CREATE INDEX idx_audit_events_organization_id
ON audit_trail.audit_events (organization_id);

CREATE INDEX idx_audit_events_org_seq_desc
ON audit_trail.audit_events (organization_id, seq DESC);

CREATE INDEX idx_audit_events_action_type
ON audit_trail.audit_events (action_type);

CREATE INDEX idx_audit_events_resource_type
ON audit_trail.audit_events (resource_type);

CREATE INDEX idx_audit_events_created_at
ON audit_trail.audit_events (created_at);

CREATE INDEX idx_audit_events_org_created_at
ON audit_trail.audit_events (organization_id, created_at);

-- ============================================================
-- SCHEDULED PARTITION MAINTENANCE
-- Uses pg_cron to maintain the current month + next 12 months.
-- pg_cron must be installed/enabled on the PostgreSQL server.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_cron;

SELECT cron.schedule(
    'audit-trail-create-future-monthly-partitions',
    '5 0 * * *',
    $$SELECT audit_trail.create_future_audit_partitions(12);$$
)
WHERE NOT EXISTS (
    SELECT 1
    FROM cron.job
    WHERE jobname = 'audit-trail-create-future-monthly-partitions'
);

-- ============================================================
-- AUDIT CHECKPOINTS
-- ============================================================

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




