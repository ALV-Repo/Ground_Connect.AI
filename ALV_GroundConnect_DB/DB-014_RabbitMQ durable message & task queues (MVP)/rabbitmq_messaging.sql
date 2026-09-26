-- ================================================================
-- FILE: rabbitmq_messaging.sql
-- DB-014 — RabbitMQ Durable Message & Task Queues (MVP)
--
-- PostgreSQL control-plane only.
-- RabbitMQ remains responsible for queues, routing, delivery,
-- acknowledgements, requeue/retry and broker durability.
--
-- Existing authoritative business tables are NOT duplicated:
--   messaging.messages
--   messaging.message_recipients
--   tasks_field_reports.task_history
--   audit_trail.audit_events
--   notifications.notification_log
--
-- New DB-014 control objects:
--   rabbitmq_messaging.consumer_idempotency
--   rabbitmq_messaging.delivery_events
--   rabbitmq_messaging.delivery_halt_control
--
-- The consumer_idempotency functions implement the database-side
-- claim protocol. They do not replace RabbitMQ ACK/NACK behavior.
-- ================================================================

CREATE SCHEMA IF NOT EXISTS rabbitmq_messaging;

-- ================================================================
-- 1. CONSUMER IDEMPOTENCY
-- ================================================================

CREATE TABLE IF NOT EXISTS rabbitmq_messaging.consumer_idempotency (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    message_id UUID NOT NULL,
    consumer_name TEXT NOT NULL,
    processing_status TEXT NOT NULL DEFAULT 'processing',
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processing_started_at TIMESTAMPTZ NULL,
    lease_expires_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    last_error TEXT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_consumer_idempotency
        PRIMARY KEY (id),

    CONSTRAINT fk_consumer_idempotency_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT uq_consumer_idempotency_message_consumer
        UNIQUE (organization_id, message_id, consumer_name),

    CONSTRAINT chk_consumer_idempotency_status
        CHECK (
            processing_status IN ('processing', 'completed', 'failed')
        ),

    CONSTRAINT chk_consumer_idempotency_attempt_count
        CHECK (attempt_count >= 1),

    CONSTRAINT chk_consumer_idempotency_consumer_name
        CHECK (BTRIM(consumer_name) <> ''),

    CONSTRAINT chk_consumer_idempotency_state
        CHECK (
            (
                processing_status = 'processing'
                AND completed_at IS NULL
                AND processing_started_at IS NOT NULL
                AND lease_expires_at IS NOT NULL
            )
            OR
            (
                processing_status = 'completed'
                AND completed_at IS NOT NULL
                AND lease_expires_at IS NULL
            )
            OR
            (
                processing_status = 'failed'
                AND completed_at IS NULL
                AND lease_expires_at IS NULL
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_consumer_idempotency_status
    ON rabbitmq_messaging.consumer_idempotency
       (organization_id, processing_status);

CREATE INDEX IF NOT EXISTS idx_consumer_idempotency_updated
    ON rabbitmq_messaging.consumer_idempotency
       (organization_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_consumer_idempotency_lease
    ON rabbitmq_messaging.consumer_idempotency
       (organization_id, lease_expires_at)
    WHERE processing_status = 'processing';

-- ================================================================
-- 2. DELIVERY EVENTS
-- ================================================================

CREATE TABLE IF NOT EXISTS rabbitmq_messaging.delivery_events (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    message_id UUID NOT NULL,
    source_type TEXT NOT NULL,
    source_id UUID NOT NULL,
    queue_name TEXT NOT NULL,
    routing_key TEXT NULL,
    event_type TEXT NOT NULL,
    attempt_number INTEGER NOT NULL DEFAULT 1,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,

    CONSTRAINT pk_delivery_events
        PRIMARY KEY (id),

    CONSTRAINT fk_delivery_events_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT chk_delivery_events_source_type
        CHECK (
            source_type IN (
                'message',
                'task_event',
                'audit',
                'notification'
            )
        ),

    CONSTRAINT chk_delivery_events_event_type
        CHECK (
            event_type IN (
                'published',
                'delivered',
                'acknowledged',
                'retry',
                'failed',
                'dead_lettered',
                'halted'
            )
        ),

    CONSTRAINT chk_delivery_events_attempt_number
        CHECK (attempt_number >= 1),

    CONSTRAINT chk_delivery_events_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_delivery_events_message_time
    ON rabbitmq_messaging.delivery_events
       (organization_id, message_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_delivery_events_source
    ON rabbitmq_messaging.delivery_events
       (organization_id, source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_delivery_events_type_time
    ON rabbitmq_messaging.delivery_events
       (organization_id, event_type, occurred_at DESC);

-- ================================================================
-- 3. DELIVERY HALT CONTROL
-- ================================================================

CREATE TABLE IF NOT EXISTS rabbitmq_messaging.delivery_halt_control (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    halt_requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    halt_deadline_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'requested',
    requested_by UUID NULL,
    completed_at TIMESTAMPTZ NULL,
    released_at TIMESTAMPTZ NULL,
    reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_delivery_halt_control
        PRIMARY KEY (id),

    CONSTRAINT fk_delivery_halt_control_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_delivery_halt_control_requested_by
        FOREIGN KEY (requested_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_delivery_halt_control_status
        CHECK (
            status IN ('requested', 'active', 'completed', 'released')
        ),

    CONSTRAINT chk_delivery_halt_control_deadline
        CHECK (
            halt_deadline_at =
            halt_requested_at + INTERVAL '30 seconds'
        ),

    CONSTRAINT chk_delivery_halt_control_state
        CHECK (
            (
                status IN ('requested', 'active')
                AND completed_at IS NULL
                AND released_at IS NULL
            )
            OR
            (
                status = 'completed'
                AND completed_at IS NOT NULL
                AND released_at IS NULL
            )
            OR
            (
                status = 'released'
                AND completed_at IS NOT NULL
                AND released_at IS NOT NULL
            )
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_delivery_halt_control_active
    ON rabbitmq_messaging.delivery_halt_control (organization_id)
    WHERE status IN ('requested', 'active');

CREATE INDEX IF NOT EXISTS idx_delivery_halt_control_status
    ON rabbitmq_messaging.delivery_halt_control
       (organization_id, status);

CREATE INDEX IF NOT EXISTS idx_delivery_halt_control_requested
    ON rabbitmq_messaging.delivery_halt_control
       (organization_id, halt_requested_at DESC);

-- ================================================================
-- 4. ROW LEVEL SECURITY
-- ================================================================

ALTER TABLE rabbitmq_messaging.consumer_idempotency
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE rabbitmq_messaging.consumer_idempotency
    FORCE ROW LEVEL SECURITY;

ALTER TABLE rabbitmq_messaging.delivery_events
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE rabbitmq_messaging.delivery_events
    FORCE ROW LEVEL SECURITY;

ALTER TABLE rabbitmq_messaging.delivery_halt_control
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE rabbitmq_messaging.delivery_halt_control
    FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS consumer_idempotency_tenant_isolation
ON rabbitmq_messaging.consumer_idempotency;

CREATE POLICY consumer_idempotency_tenant_isolation
ON rabbitmq_messaging.consumer_idempotency
AS PERMISSIVE
FOR ALL
USING (organization_id = app.current_organization_id())
WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS delivery_events_tenant_isolation
ON rabbitmq_messaging.delivery_events;

CREATE POLICY delivery_events_tenant_isolation
ON rabbitmq_messaging.delivery_events
AS PERMISSIVE
FOR ALL
USING (organization_id = app.current_organization_id())
WITH CHECK (organization_id = app.current_organization_id());

DROP POLICY IF EXISTS delivery_halt_control_tenant_isolation
ON rabbitmq_messaging.delivery_halt_control;

CREATE POLICY delivery_halt_control_tenant_isolation
ON rabbitmq_messaging.delivery_halt_control
AS PERMISSIVE
FOR ALL
USING (organization_id = app.current_organization_id())
WITH CHECK (organization_id = app.current_organization_id());

-- ================================================================
-- 5. IDEMPOTENCY CONTROL FUNCTIONS
-- ================================================================

-- Atomically claim a message for a consumer.
--
-- TRUE  = this consumer owns the current processing attempt.
-- FALSE = the message is already completed or another unexpired
--         processing lease owns it.
--
-- A failed attempt can be claimed again. An expired processing lease
-- can also be reclaimed, which covers consumer crashes before fail().

CREATE OR REPLACE FUNCTION rabbitmq_messaging.claim_message(
    p_message_id UUID,
    p_consumer_name TEXT,
    p_lease_seconds INTEGER DEFAULT 60
)
RETURNS TABLE (
    claimed BOOLEAN,
    processing_status TEXT,
    attempt_count INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_organization_id UUID;
    v_status TEXT;
    v_attempt_count INTEGER;
    v_lease_expires_at TIMESTAMPTZ;
BEGIN
    v_organization_id := app.require_organization_context();

    IF p_message_id IS NULL THEN
        RAISE EXCEPTION 'DB-014: message_id is required';
    END IF;

    IF NULLIF(BTRIM(p_consumer_name), '') IS NULL THEN
        RAISE EXCEPTION 'DB-014: consumer_name is required';
    END IF;

    IF p_lease_seconds < 1 OR p_lease_seconds > 3600 THEN
        RAISE EXCEPTION 'DB-014: lease_seconds must be between 1 and 3600';
    END IF;

    INSERT INTO rabbitmq_messaging.consumer_idempotency (
        organization_id,
        message_id,
        consumer_name,
        processing_status,
        first_seen_at,
        processing_started_at,
        lease_expires_at,
        attempt_count,
        updated_at
    )
    VALUES (
        v_organization_id,
        p_message_id,
        BTRIM(p_consumer_name),
        'processing',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP + make_interval(secs => p_lease_seconds),
        1,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT (organization_id, message_id, consumer_name)
    DO NOTHING;

    IF FOUND THEN
        RETURN QUERY
        SELECT TRUE, 'processing'::TEXT, 1;
        RETURN;
    END IF;

    SELECT
        ci.processing_status,
        ci.attempt_count,
        ci.lease_expires_at
    INTO
        v_status,
        v_attempt_count,
        v_lease_expires_at
    FROM rabbitmq_messaging.consumer_idempotency ci
    WHERE ci.organization_id = v_organization_id
      AND ci.message_id = p_message_id
      AND ci.consumer_name = BTRIM(p_consumer_name)
    FOR UPDATE;

    IF v_status = 'completed' THEN
        RETURN QUERY
        SELECT FALSE, v_status, v_attempt_count;
        RETURN;
    END IF;

    IF v_status = 'processing'
       AND v_lease_expires_at > CURRENT_TIMESTAMP THEN
        RETURN QUERY
        SELECT FALSE, v_status, v_attempt_count;
        RETURN;
    END IF;

    UPDATE rabbitmq_messaging.consumer_idempotency
    SET processing_status = 'processing',
        processing_started_at = CURRENT_TIMESTAMP,
        lease_expires_at = CURRENT_TIMESTAMP
            + make_interval(secs => p_lease_seconds),
        completed_at = NULL,
        last_error = NULL,
        attempt_count = attempt_count + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE organization_id = v_organization_id
      AND message_id = p_message_id
      AND consumer_name = BTRIM(p_consumer_name)
    RETURNING attempt_count INTO v_attempt_count;

    RETURN QUERY
    SELECT TRUE, 'processing'::TEXT, v_attempt_count;
END;
$$;

CREATE OR REPLACE FUNCTION rabbitmq_messaging.complete_message(
    p_message_id UUID,
    p_consumer_name TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_organization_id UUID;
BEGIN
    v_organization_id := app.require_organization_context();

    UPDATE rabbitmq_messaging.consumer_idempotency
    SET processing_status = 'completed',
        completed_at = CURRENT_TIMESTAMP,
        lease_expires_at = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE organization_id = v_organization_id
      AND message_id = p_message_id
      AND consumer_name = BTRIM(p_consumer_name)
      AND processing_status = 'processing';

    RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION rabbitmq_messaging.fail_message(
    p_message_id UUID,
    p_consumer_name TEXT,
    p_error TEXT DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_organization_id UUID;
BEGIN
    v_organization_id := app.require_organization_context();

    UPDATE rabbitmq_messaging.consumer_idempotency
    SET processing_status = 'failed',
        completed_at = NULL,
        lease_expires_at = NULL,
        last_error = p_error,
        updated_at = CURRENT_TIMESTAMP
    WHERE organization_id = v_organization_id
      AND message_id = p_message_id
      AND consumer_name = BTRIM(p_consumer_name)
      AND processing_status = 'processing';

    RETURN FOUND;
END;
$$;

-- ================================================================
-- 6. DELIVERY HALT CONTROL FUNCTIONS
-- ================================================================

CREATE OR REPLACE FUNCTION rabbitmq_messaging.start_delivery_halt(
    p_reason TEXT DEFAULT NULL,
    p_requested_by UUID DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_organization_id UUID;
    v_id UUID;
BEGIN
    v_organization_id := app.require_organization_context();

    INSERT INTO rabbitmq_messaging.delivery_halt_control (
        organization_id,
        halt_requested_at,
        halt_deadline_at,
        status,
        requested_by,
        reason
    )
    VALUES (
        v_organization_id,
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP + INTERVAL '30 seconds',
        'requested',
        p_requested_by,
        p_reason
    )
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION rabbitmq_messaging.activate_delivery_halt(
    p_halt_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_organization_id UUID;
BEGIN
    v_organization_id := app.require_organization_context();

    UPDATE rabbitmq_messaging.delivery_halt_control
    SET status = 'active'
    WHERE id = p_halt_id
      AND organization_id = v_organization_id
      AND status = 'requested';

    RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION rabbitmq_messaging.complete_delivery_halt(
    p_halt_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_organization_id UUID;
BEGIN
    v_organization_id := app.require_organization_context();

    UPDATE rabbitmq_messaging.delivery_halt_control
    SET status = 'completed',
        completed_at = CURRENT_TIMESTAMP
    WHERE id = p_halt_id
      AND organization_id = v_organization_id
      AND status IN ('requested', 'active')
      AND completed_at IS NULL
      AND released_at IS NULL;

    RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION rabbitmq_messaging.release_delivery_halt(
    p_halt_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_organization_id UUID;
BEGIN
    v_organization_id := app.require_organization_context();

    UPDATE rabbitmq_messaging.delivery_halt_control
    SET status = 'released',
        released_at = CURRENT_TIMESTAMP
    WHERE id = p_halt_id
      AND organization_id = v_organization_id
      AND status = 'completed'
      AND completed_at IS NOT NULL
      AND released_at IS NULL;

    RETURN FOUND;
END;
$$;

-- ================================================================
-- 7. OPERATIONAL VIEW
-- ================================================================

CREATE OR REPLACE VIEW rabbitmq_messaging.active_delivery_halt
WITH (security_invoker = true)
AS
SELECT
    h.id,
    h.organization_id,
    h.halt_requested_at,
    h.halt_deadline_at,
    h.status,
    h.requested_by,
    h.completed_at,
    h.released_at,
    h.reason,
    (
        CURRENT_TIMESTAMP >= h.halt_deadline_at
        AND h.status IN ('requested', 'active')
    ) AS halt_deadline_reached
FROM rabbitmq_messaging.delivery_halt_control h
WHERE h.status IN ('requested', 'active');

-- ================================================================
-- END DB-014
-- ================================================================
