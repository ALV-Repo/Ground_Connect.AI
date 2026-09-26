-- ================================================================
-- FILE: rabbitmq_messaging_tests.sql
-- DB-014 PostgreSQL control-plane tests
--
-- Run after rabbitmq_messaging.sql.
-- Set a valid tenant context before running:
--
--   BEGIN;
--   SET LOCAL app.organization_id = '<tenant-uuid>';
--   \i rabbitmq_messaging_tests.sql
--
-- The test transaction rolls back at the end.
-- ================================================================

BEGIN;

DO $$
DECLARE
    v_org UUID;
    v_halt UUID;
    v_msg UUID := gen_random_uuid();
    v_msg_retry UUID := gen_random_uuid();
    v_claimed BOOLEAN;
    v_status TEXT;
    v_attempt INTEGER;
    v_bad_halt UUID;
BEGIN
    v_org := app.require_organization_context();

    IF to_regclass('rabbitmq_messaging.consumer_idempotency') IS NULL THEN
        RAISE EXCEPTION 'consumer_idempotency table is missing';
    END IF;

    IF to_regclass('rabbitmq_messaging.delivery_events') IS NULL THEN
        RAISE EXCEPTION 'delivery_events table is missing';
    END IF;

    IF to_regclass('rabbitmq_messaging.delivery_halt_control') IS NULL THEN
        RAISE EXCEPTION 'delivery_halt_control table is missing';
    END IF;

    -- ------------------------------------------------------------
    -- 1. Atomic claim: first claim succeeds.
    -- ------------------------------------------------------------
    SELECT claimed, processing_status, attempt_count
    INTO v_claimed, v_status, v_attempt
    FROM rabbitmq_messaging.claim_message(
        v_msg,
        'db014-test-consumer',
        60
    );

    IF NOT v_claimed OR v_status <> 'processing' OR v_attempt <> 1 THEN
        RAISE EXCEPTION 'Initial idempotency claim failed';
    END IF;

    -- Second claim while lease is active must not duplicate processing.
    SELECT claimed, processing_status, attempt_count
    INTO v_claimed, v_status, v_attempt
    FROM rabbitmq_messaging.claim_message(
        v_msg,
        'db014-test-consumer',
        60
    );

    IF v_claimed OR v_status <> 'processing' OR v_attempt <> 1 THEN
        RAISE EXCEPTION 'Active idempotency lease was incorrectly re-claimed';
    END IF;

    IF NOT rabbitmq_messaging.complete_message(
        v_msg,
        'db014-test-consumer'
    ) THEN
        RAISE EXCEPTION 'Message could not be completed';
    END IF;

    -- Completed message must never be claimed again.
    SELECT claimed, processing_status, attempt_count
    INTO v_claimed, v_status, v_attempt
    FROM rabbitmq_messaging.claim_message(
        v_msg,
        'db014-test-consumer',
        60
    );

    IF v_claimed OR v_status <> 'completed' THEN
        RAISE EXCEPTION 'Completed message was incorrectly re-claimed';
    END IF;

    -- ------------------------------------------------------------
    -- 2. Failed processing can be retried and increments attempt.
    -- ------------------------------------------------------------
    SELECT claimed, processing_status, attempt_count
    INTO v_claimed, v_status, v_attempt
    FROM rabbitmq_messaging.claim_message(
        v_msg_retry,
        'db014-test-consumer',
        60
    );

    IF NOT v_claimed OR v_attempt <> 1 THEN
        RAISE EXCEPTION 'Initial retry-test claim failed';
    END IF;

    IF NOT rabbitmq_messaging.fail_message(
        v_msg_retry,
        'db014-test-consumer',
        'DB-014 simulated failure'
    ) THEN
        RAISE EXCEPTION 'Failed message was not marked failed';
    END IF;

    SELECT claimed, processing_status, attempt_count
    INTO v_claimed, v_status, v_attempt
    FROM rabbitmq_messaging.claim_message(
        v_msg_retry,
        'db014-test-consumer',
        60
    );

    IF NOT v_claimed OR v_status <> 'processing' OR v_attempt <> 2 THEN
        RAISE EXCEPTION 'Failed message was not re-claimed as attempt 2';
    END IF;

    -- ------------------------------------------------------------
    -- 3. Delivery event recording.
    -- ------------------------------------------------------------
    INSERT INTO rabbitmq_messaging.delivery_events (
        organization_id,
        message_id,
        source_type,
        source_id,
        queue_name,
        routing_key,
        event_type,
        attempt_number
    )
    VALUES (
        v_org,
        v_msg,
        'message',
        v_msg,
        'db014-test-queue',
        'test.message',
        'published',
        1
    );

    IF NOT EXISTS (
        SELECT 1
        FROM rabbitmq_messaging.delivery_events
        WHERE organization_id = v_org
          AND message_id = v_msg
          AND event_type = 'published'
    ) THEN
        RAISE EXCEPTION 'Delivery event was not created';
    END IF;

    -- ------------------------------------------------------------
    -- 4. 30-second staged halt lifecycle.
    -- ------------------------------------------------------------
    v_halt := rabbitmq_messaging.start_delivery_halt(
        'DB-014 test halt',
        NULL
    );

    IF NOT EXISTS (
        SELECT 1
        FROM rabbitmq_messaging.delivery_halt_control
        WHERE id = v_halt
          AND status = 'requested'
          AND completed_at IS NULL
          AND released_at IS NULL
          AND halt_deadline_at =
              halt_requested_at + INTERVAL '30 seconds'
    ) THEN
        RAISE EXCEPTION '30-second halt request was not recorded correctly';
    END IF;

    IF NOT rabbitmq_messaging.activate_delivery_halt(v_halt) THEN
        RAISE EXCEPTION 'Delivery halt could not be activated';
    END IF;

    IF NOT rabbitmq_messaging.complete_delivery_halt(v_halt) THEN
        RAISE EXCEPTION 'Delivery halt could not be completed';
    END IF;

    IF NOT rabbitmq_messaging.release_delivery_halt(v_halt) THEN
        RAISE EXCEPTION 'Completed delivery halt could not be released';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM rabbitmq_messaging.delivery_halt_control
        WHERE id = v_halt
          AND status = 'released'
          AND completed_at IS NOT NULL
          AND released_at IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'Released halt state was not recorded';
    END IF;

    -- A second active/requested halt for the same tenant is rejected.
    v_halt := rabbitmq_messaging.start_delivery_halt('DB-014 uniqueness test');

    BEGIN
        PERFORM rabbitmq_messaging.start_delivery_halt('DB-014 duplicate halt');
        RAISE EXCEPTION 'Multiple active delivery halts were accepted';
    EXCEPTION
        WHEN unique_violation THEN
            NULL;
    END;

    -- Invalid 31-second deadline must be rejected by the table constraint.
    BEGIN
        INSERT INTO rabbitmq_messaging.delivery_halt_control (
            organization_id,
            halt_requested_at,
            halt_deadline_at,
            status
        )
        VALUES (
            v_org,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP + INTERVAL '31 seconds',
            'requested'
        );
        RAISE EXCEPTION 'Invalid 31-second halt deadline was accepted';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    -- ------------------------------------------------------------
    -- 5. Tenant context is mandatory.
    -- ------------------------------------------------------------
    -- No cross-tenant access is asserted by inventing a tenant row here;
    -- FORCE RLS plus the app context is the security boundary.
    IF app.current_organization_id() <> v_org THEN
        RAISE EXCEPTION 'Unexpected organization context changed during tests';
    END IF;

    RAISE NOTICE 'DB-014 PostgreSQL control-plane tests passed for tenant %', v_org;
END;
$$;

ROLLBACK;

-- These tests validate PostgreSQL control-plane behavior only.
-- They do NOT prove RabbitMQ queue durability, persistent messages,
-- ACK/NACK behavior, retry/requeue behavior at the broker, or actual
-- consumer shutdown within 30 seconds. Those require RabbitMQ
-- integration tests with a real broker and at least two consumer
-- execution contexts for concurrency/duplicate-delivery coverage.
