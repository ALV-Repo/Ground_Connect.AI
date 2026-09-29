-- ============================================================
-- DB-021 | KAFKA MIGRATION FOR HIGH-VOLUME QUEUES
-- PostgreSQL control-plane implementation
-- Requirements: NFR-06
--
-- PostgreSQL stores Kafka migration/control metadata only.
-- Kafka topics, brokers, producers, consumers and partition
-- assignment remain application/infrastructure responsibilities.
--
-- RabbitMQ remains authoritative for task and notification queues.
-- High-volume streams can be migrated selectively to Kafka when
-- the configured scale threshold is reached.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS kafka_messaging;

-- ============================================================
-- 1. STREAM REGISTRY
-- ============================================================
-- One row describes a logical event/message stream.
-- current_transport identifies the currently active broker.
-- RabbitMQ remains supported for task/notification streams.

CREATE TABLE IF NOT EXISTS kafka_messaging.streams
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,

    stream_code TEXT NOT NULL,
    stream_name TEXT NOT NULL,
    description TEXT NULL,

    stream_type TEXT NOT NULL,

    current_transport TEXT NOT NULL DEFAULT 'rabbitmq',

    migration_threshold_messages_per_day BIGINT NOT NULL DEFAULT 500000,

    migration_burst_multiplier NUMERIC(12,4) NOT NULL DEFAULT 10.0,

    migration_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    status TEXT NOT NULL DEFAULT 'active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_kafka_streams
        PRIMARY KEY (id),

    CONSTRAINT fk_kafka_streams_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT uq_kafka_streams_org_code
        UNIQUE (organization_id, stream_code),

    CONSTRAINT chk_kafka_streams_code
        CHECK (BTRIM(stream_code) <> ''),

    CONSTRAINT chk_kafka_streams_name
        CHECK (BTRIM(stream_name) <> ''),

    CONSTRAINT chk_kafka_streams_type
        CHECK (
            stream_type IN (
                'message_event',
                'task_event',
                'notification_event',
                'audit_event',
                'integration_event',
                'custom_event'
            )
        ),

    CONSTRAINT chk_kafka_streams_transport
        CHECK (
            current_transport IN ('rabbitmq', 'kafka')
        ),

    CONSTRAINT chk_kafka_streams_threshold
        CHECK (migration_threshold_messages_per_day > 0),

    CONSTRAINT chk_kafka_streams_burst_multiplier
        CHECK (migration_burst_multiplier >= 10.0),

    CONSTRAINT chk_kafka_streams_status
        CHECK (
            status IN ('active', 'paused', 'retired')
        )
);

CREATE INDEX IF NOT EXISTS idx_kafka_streams_transport_status
    ON kafka_messaging.streams
       (organization_id, current_transport, status);

-- ============================================================
-- 2. KAFKA TOPIC / PARTITION METADATA
-- ============================================================
-- This is metadata, not a replacement for Kafka itself.

CREATE TABLE IF NOT EXISTS kafka_messaging.topic_partitions
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    stream_id UUID NOT NULL,

    topic_name TEXT NOT NULL,
    partition_number INTEGER NOT NULL,

    partition_key_strategy TEXT NOT NULL DEFAULT 'record_id',

    expected_min_partitions INTEGER NOT NULL DEFAULT 1,

    status TEXT NOT NULL DEFAULT 'active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_kafka_topic_partitions
        PRIMARY KEY (id),

    CONSTRAINT fk_kafka_topic_partitions_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_kafka_topic_partitions_stream
        FOREIGN KEY (stream_id)
        REFERENCES kafka_messaging.streams(id),

    CONSTRAINT uq_kafka_topic_partition
        UNIQUE (organization_id, stream_id, topic_name, partition_number),

    CONSTRAINT chk_kafka_topic_partition_name
        CHECK (BTRIM(topic_name) <> ''),

    CONSTRAINT chk_kafka_topic_partition_number
        CHECK (partition_number >= 0),

    CONSTRAINT chk_kafka_topic_partition_strategy
        CHECK (
            partition_key_strategy IN (
                'record_id',
                'organization_id',
                'aggregate_id',
                'custom'
            )
        ),

    CONSTRAINT chk_kafka_topic_partition_min
        CHECK (expected_min_partitions >= 1),

    CONSTRAINT chk_kafka_topic_partition_status
        CHECK (
            status IN ('active', 'retired')
        )
);

CREATE INDEX IF NOT EXISTS idx_kafka_topic_partitions_stream
    ON kafka_messaging.topic_partitions
       (organization_id, stream_id, status);

-- ============================================================
-- 3. MIGRATION / CUTOVER CONTROL
-- ============================================================
-- Controlled lifecycle:
--
-- planned
--   -> dual_publish
--   -> validating
--   -> kafka_active
--   -> rabbitmq_draining
--   -> completed
--
-- Rollback is allowed before final completion.

CREATE TABLE IF NOT EXISTS kafka_messaging.stream_migrations
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    stream_id UUID NOT NULL,

    source_transport TEXT NOT NULL DEFAULT 'rabbitmq',
    target_transport TEXT NOT NULL DEFAULT 'kafka',

    status TEXT NOT NULL DEFAULT 'planned',

    threshold_messages_per_day BIGINT NOT NULL,

    observed_messages_last_24h BIGINT NULL,

    burst_messages_per_minute BIGINT NULL,

    migration_reason TEXT NULL,

    planned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dual_publish_started_at TIMESTAMPTZ NULL,
    validation_started_at TIMESTAMPTZ NULL,
    kafka_activated_at TIMESTAMPTZ NULL,
    rabbitmq_draining_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    rolled_back_at TIMESTAMPTZ NULL,

    rollback_reason TEXT NULL,

    created_by UUID NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_kafka_stream_migrations
        PRIMARY KEY (id),

    CONSTRAINT fk_kafka_stream_migrations_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_kafka_stream_migrations_stream
        FOREIGN KEY (stream_id)
        REFERENCES kafka_messaging.streams(id),

    CONSTRAINT chk_kafka_migration_source
        CHECK (source_transport = 'rabbitmq'),

    CONSTRAINT chk_kafka_migration_target
        CHECK (target_transport = 'kafka'),

    CONSTRAINT chk_kafka_migration_threshold
        CHECK (threshold_messages_per_day > 0),

    CONSTRAINT chk_kafka_migration_observed
        CHECK (
            observed_messages_last_24h IS NULL
            OR observed_messages_last_24h >= 0
        ),

    CONSTRAINT chk_kafka_migration_burst
        CHECK (
            burst_messages_per_minute IS NULL
            OR burst_messages_per_minute >= 0
        ),

    CONSTRAINT chk_kafka_migration_status
        CHECK (
            status IN (
                'planned',
                'dual_publish',
                'validating',
                'kafka_active',
                'rabbitmq_draining',
                'completed',
                'failed',
                'rolled_back'
            )
        ),

    CONSTRAINT chk_kafka_migration_dates
        CHECK (
            completed_at IS NULL
            OR completed_at >= planned_at
        )
);

CREATE INDEX IF NOT EXISTS idx_kafka_stream_migrations_stream_status
    ON kafka_messaging.stream_migrations
       (organization_id, stream_id, status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_kafka_stream_migrations_active
    ON kafka_messaging.stream_migrations
       (organization_id, stream_id)
    WHERE status IN (
        'planned',
        'dual_publish',
        'validating',
        'kafka_active',
        'rabbitmq_draining'
    );

-- ============================================================
-- 4. CONSUMER GROUP REGISTRY
-- ============================================================

CREATE TABLE IF NOT EXISTS kafka_messaging.consumer_groups
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    stream_id UUID NOT NULL,

    consumer_group_name TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_kafka_consumer_groups
        PRIMARY KEY (id),

    CONSTRAINT fk_kafka_consumer_groups_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_kafka_consumer_groups_stream
        FOREIGN KEY (stream_id)
        REFERENCES kafka_messaging.streams(id),

    CONSTRAINT uq_kafka_consumer_group
        UNIQUE (
            organization_id,
            stream_id,
            consumer_group_name
        ),

    CONSTRAINT chk_kafka_consumer_group_name
        CHECK (BTRIM(consumer_group_name) <> ''),

    CONSTRAINT chk_kafka_consumer_group_status
        CHECK (
            status IN ('active', 'paused', 'retired')
        )
);

CREATE INDEX IF NOT EXISTS idx_kafka_consumer_groups_stream
    ON kafka_messaging.consumer_groups
       (organization_id, stream_id, status);

-- ============================================================
-- 5. MIGRATION CHECKPOINTS
-- ============================================================
-- Checkpoints allow consumers to resume after disconnects,
-- consumer restart or migration interruption.
--
-- PostgreSQL records the last successfully checkpointed Kafka
-- offset. The Kafka consumer remains responsible for committing
-- its broker offset.

CREATE TABLE IF NOT EXISTS kafka_messaging.migration_checkpoints
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,

    stream_id UUID NOT NULL,
    consumer_group_id UUID NOT NULL,

    topic_name TEXT NOT NULL,
    partition_number INTEGER NOT NULL,

    kafka_offset BIGINT NOT NULL,

    checkpoint_type TEXT NOT NULL DEFAULT 'processed',

    checkpointed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_kafka_migration_checkpoints
        PRIMARY KEY (id),

    CONSTRAINT fk_kafka_checkpoints_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_kafka_checkpoints_stream
        FOREIGN KEY (stream_id)
        REFERENCES kafka_messaging.streams(id),

    CONSTRAINT fk_kafka_checkpoints_group
        FOREIGN KEY (consumer_group_id)
        REFERENCES kafka_messaging.consumer_groups(id),

    CONSTRAINT uq_kafka_checkpoint
        UNIQUE (
            organization_id,
            consumer_group_id,
            topic_name,
            partition_number
        ),

    CONSTRAINT chk_kafka_checkpoint_topic
        CHECK (BTRIM(topic_name) <> ''),

    CONSTRAINT chk_kafka_checkpoint_partition
        CHECK (partition_number >= 0),

    CONSTRAINT chk_kafka_checkpoint_offset
        CHECK (kafka_offset >= 0),

    CONSTRAINT chk_kafka_checkpoint_type
        CHECK (
            checkpoint_type IN (
                'received',
                'processed',
                'committed'
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_kafka_checkpoints_stream
    ON kafka_messaging.migration_checkpoints
       (organization_id, stream_id, checkpointed_at DESC);

-- ============================================================
-- 6. CONSUMER IDEMPOTENCY
-- ============================================================
-- Prevents duplicate business processing when Kafka retries,
-- consumers restart or a message is replayed.

CREATE TABLE IF NOT EXISTS kafka_messaging.consumer_idempotency
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,

    consumer_group_id UUID NOT NULL,

    event_id UUID NOT NULL,

    processing_status TEXT NOT NULL DEFAULT 'processing',

    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processing_started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,

    attempt_count INTEGER NOT NULL DEFAULT 1,

    last_error TEXT NULL,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_kafka_consumer_idempotency
        PRIMARY KEY (id),

    CONSTRAINT fk_kafka_consumer_idempotency_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_kafka_consumer_idempotency_group
        FOREIGN KEY (consumer_group_id)
        REFERENCES kafka_messaging.consumer_groups(id),

    CONSTRAINT uq_kafka_consumer_event
        UNIQUE (
            organization_id,
            consumer_group_id,
            event_id
        ),

    CONSTRAINT chk_kafka_consumer_idempotency_status
        CHECK (
            processing_status IN (
                'processing',
                'completed',
                'failed'
            )
        ),

    CONSTRAINT chk_kafka_consumer_idempotency_attempt
        CHECK (attempt_count >= 1),

    CONSTRAINT chk_kafka_consumer_idempotency_state
        CHECK (
            (
                processing_status = 'processing'
                AND completed_at IS NULL
                AND processing_started_at IS NOT NULL
            )
            OR
            (
                processing_status = 'completed'
                AND completed_at IS NOT NULL
            )
            OR
            (
                processing_status = 'failed'
                AND completed_at IS NULL
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_kafka_consumer_idempotency_status
    ON kafka_messaging.consumer_idempotency
       (organization_id, consumer_group_id, processing_status);

-- ============================================================
-- 7. DUAL-PUBLISH VALIDATION METRICS
-- ============================================================
-- Captures RabbitMQ/Kafka publication counts during dual-publish.
-- Cutover must not be marked validated while the observed counts
-- or event-id sets are inconsistent.

CREATE TABLE IF NOT EXISTS kafka_messaging.dual_publish_metrics
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    migration_id UUID NOT NULL,

    measured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    rabbitmq_published_count BIGINT NOT NULL DEFAULT 0,
    kafka_published_count BIGINT NOT NULL DEFAULT 0,
    matched_event_count BIGINT NOT NULL DEFAULT 0,
    missing_in_kafka_count BIGINT NOT NULL DEFAULT 0,
    missing_in_rabbitmq_count BIGINT NOT NULL DEFAULT 0,
    duplicate_event_count BIGINT NOT NULL DEFAULT 0,

    validation_status TEXT NOT NULL DEFAULT 'pending',

    validation_error TEXT NULL,

    CONSTRAINT pk_kafka_dual_publish_metrics PRIMARY KEY (id),

    CONSTRAINT fk_kafka_dual_publish_metrics_org
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_kafka_dual_publish_metrics_migration
        FOREIGN KEY (migration_id)
        REFERENCES kafka_messaging.stream_migrations(id),

    CONSTRAINT chk_kafka_dual_publish_counts
        CHECK (
            rabbitmq_published_count >= 0
            AND kafka_published_count >= 0
            AND matched_event_count >= 0
            AND missing_in_kafka_count >= 0
            AND missing_in_rabbitmq_count >= 0
            AND duplicate_event_count >= 0
        ),

    CONSTRAINT chk_kafka_dual_publish_status
        CHECK (
            validation_status IN ('pending', 'passed', 'failed')
        ),

    CONSTRAINT chk_kafka_dual_publish_pass
        CHECK (
            validation_status <> 'passed'
            OR (
                missing_in_kafka_count = 0
                AND missing_in_rabbitmq_count = 0
                AND duplicate_event_count = 0
                AND rabbitmq_published_count = kafka_published_count
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_kafka_dual_publish_metrics_migration
    ON kafka_messaging.dual_publish_metrics
       (organization_id, migration_id, measured_at DESC);


-- ============================================================
-- 8. ORDERING VALIDATION
-- ============================================================
-- Records per-partition ordering validation. The application/Kafka
-- integration supplies the observed sequence values.

CREATE TABLE IF NOT EXISTS kafka_messaging.ordering_validation
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    migration_id UUID NOT NULL,

    topic_name TEXT NOT NULL,
    partition_number INTEGER NOT NULL,

    first_sequence BIGINT NOT NULL,
    last_sequence BIGINT NOT NULL,
    events_checked BIGINT NOT NULL,

    ordering_violations BIGINT NOT NULL DEFAULT 0,

    validation_status TEXT NOT NULL DEFAULT 'pending',

    validated_at TIMESTAMPTZ NULL,

    validation_details JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT pk_kafka_ordering_validation PRIMARY KEY (id),

    CONSTRAINT fk_kafka_ordering_validation_org
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_kafka_ordering_validation_migration
        FOREIGN KEY (migration_id)
        REFERENCES kafka_messaging.stream_migrations(id),

    CONSTRAINT chk_kafka_ordering_partition
        CHECK (partition_number >= 0),

    CONSTRAINT chk_kafka_ordering_sequence
        CHECK (
            first_sequence >= 0
            AND last_sequence >= first_sequence
        ),

    CONSTRAINT chk_kafka_ordering_events
        CHECK (events_checked >= 0),

    CONSTRAINT chk_kafka_ordering_violations
        CHECK (ordering_violations >= 0),

    CONSTRAINT chk_kafka_ordering_status
        CHECK (
            validation_status IN ('pending', 'passed', 'failed')
        ),

    CONSTRAINT chk_kafka_ordering_pass
        CHECK (
            validation_status <> 'passed'
            OR ordering_violations = 0
        ),

    CONSTRAINT chk_kafka_ordering_details
        CHECK (jsonb_typeof(validation_details) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_kafka_ordering_validation_migration
    ON kafka_messaging.ordering_validation
       (organization_id, migration_id, topic_name, partition_number);


-- ============================================================
-- 9. NFR-06 LOAD-TEST EVIDENCE
-- ============================================================
-- Stores evidence produced by an external load-test harness.
-- PostgreSQL does not pretend to execute the Kafka load test itself.

CREATE TABLE IF NOT EXISTS kafka_messaging.load_test_evidence
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,

    test_run_id TEXT NOT NULL,

    target_messages_per_day BIGINT NOT NULL DEFAULT 500000,
    sustained_messages_per_second NUMERIC(20,4) NOT NULL,
    peak_messages_per_second NUMERIC(20,4) NOT NULL,

    burst_multiplier NUMERIC(12,4) NULL,

    duration_seconds INTEGER NOT NULL,

    messages_produced BIGINT NOT NULL DEFAULT 0,
    messages_consumed BIGINT NOT NULL DEFAULT 0,
    duplicate_messages BIGINT NOT NULL DEFAULT 0,
    lost_messages BIGINT NOT NULL DEFAULT 0,

    max_consumer_lag BIGINT NULL,

    result_status TEXT NOT NULL DEFAULT 'pending',

    evidence_reference TEXT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    test_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT pk_kafka_load_test_evidence PRIMARY KEY (id),

    CONSTRAINT fk_kafka_load_test_evidence_org
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT uq_kafka_load_test_run
        UNIQUE (organization_id, test_run_id),

    CONSTRAINT chk_kafka_load_test_target
        CHECK (target_messages_per_day >= 500000),

    CONSTRAINT chk_kafka_load_test_sustained
        CHECK (sustained_messages_per_second >= 0),

    CONSTRAINT chk_kafka_load_test_peak
        CHECK (peak_messages_per_second >= sustained_messages_per_second),

    CONSTRAINT chk_kafka_load_test_duration
        CHECK (duration_seconds > 0),

    CONSTRAINT chk_kafka_load_test_counts
        CHECK (
            messages_produced >= 0
            AND messages_consumed >= 0
            AND duplicate_messages >= 0
            AND lost_messages >= 0
        ),

    CONSTRAINT chk_kafka_load_test_result
        CHECK (
            result_status IN ('pending', 'passed', 'failed')
        ),

    CONSTRAINT chk_kafka_load_test_pass
        CHECK (
            result_status <> 'passed'
            OR (
                messages_produced = messages_consumed
                AND duplicate_messages = 0
                AND lost_messages = 0
                AND peak_messages_per_second > 0
            )
        ),

    CONSTRAINT chk_kafka_load_test_metadata
        CHECK (jsonb_typeof(test_metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_kafka_load_test_evidence_time
    ON kafka_messaging.load_test_evidence
       (organization_id, executed_at DESC);


-- ============================================================
-- 10. RABBITMQ-ONLY QUEUE ENFORCEMENT
-- ============================================================
-- Task and notification streams must remain on RabbitMQ.
-- They cannot be migrated to Kafka through this control plane.

CREATE OR REPLACE FUNCTION kafka_messaging.enforce_rabbitmq_only_stream()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_stream_type TEXT;
BEGIN
    SELECT s.stream_type
      INTO v_stream_type
      FROM kafka_messaging.streams s
     WHERE s.id = NEW.stream_id
       AND s.organization_id = NEW.organization_id;

    IF v_stream_type IN ('task_event', 'notification_event') THEN
        RAISE EXCEPTION
            'DB-021: task_event and notification_event streams must remain on RabbitMQ';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_kafka_rabbitmq_only_migration
ON kafka_messaging.stream_migrations;

CREATE TRIGGER trg_kafka_rabbitmq_only_migration
BEFORE INSERT OR UPDATE OF stream_id, source_transport, target_transport
ON kafka_messaging.stream_migrations
FOR EACH ROW
EXECUTE FUNCTION kafka_messaging.enforce_rabbitmq_only_stream();


-- ============================================================
-- 11. BURST THRESHOLD ENFORCEMENT
-- ============================================================
-- A migration cannot enter dual-publish/kafka-active unless the
-- observed sustained daily volume reaches the configured threshold.
--
-- Burst evidence is required before final Kafka activation when
-- NFR-06 burst testing is enabled.

CREATE OR REPLACE FUNCTION kafka_messaging.validate_migration_threshold()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_stream_threshold BIGINT;
    v_stream_type TEXT;
BEGIN
    SELECT
        s.migration_threshold_messages_per_day,
        s.stream_type
    INTO
        v_stream_threshold,
        v_stream_type
    FROM kafka_messaging.streams s
    WHERE s.id = NEW.stream_id
      AND s.organization_id = NEW.organization_id;

    IF v_stream_type IN ('task_event', 'notification_event') THEN
        RAISE EXCEPTION
            'DB-021: task_event and notification_event streams are RabbitMQ-only';
    END IF;

    IF NEW.status IN (
        'dual_publish',
        'validating',
        'kafka_active',
        'rabbitmq_draining',
        'completed'
    )
    AND (
        NEW.observed_messages_last_24h IS NULL
        OR NEW.observed_messages_last_24h < v_stream_threshold
    ) THEN
        RAISE EXCEPTION
            'DB-021: Kafka migration requires sustained daily volume >= configured threshold';
    END IF;

    IF NEW.status IN (
        'kafka_active',
        'rabbitmq_draining',
        'completed'
    )
    AND (
        NEW.burst_messages_per_minute IS NULL
        OR NEW.burst_messages_per_minute <
           (
               (v_stream_threshold::NUMERIC / 1440.0)
               *
               (
                   SELECT migration_burst_multiplier
                   FROM kafka_messaging.streams
                   WHERE id = NEW.stream_id
                     AND organization_id = NEW.organization_id
               )
           )
    ) THEN
        RAISE EXCEPTION
            'DB-021: Kafka activation requires recorded order-of-magnitude burst evidence';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_kafka_migration_threshold
ON kafka_messaging.stream_migrations;

CREATE TRIGGER trg_kafka_migration_threshold
BEFORE INSERT OR UPDATE OF status, observed_messages_last_24h
ON kafka_messaging.stream_migrations
FOR EACH ROW
EXECUTE FUNCTION kafka_messaging.validate_migration_threshold();


-- ============================================================
-- 12. FINAL VALIDATION GUARD
-- ============================================================
-- kafka_active/completed requires:
--   * dual-publish metrics passed
--   * ordering validation passed
--   * load-test evidence passed
-- This prevents PostgreSQL control metadata from declaring a
-- migration validated without recorded evidence.

CREATE OR REPLACE FUNCTION kafka_messaging.validate_kafka_cutover()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_dual_ok BOOLEAN;
    v_order_ok BOOLEAN;
    v_load_ok BOOLEAN;
    v_stream_type TEXT;
BEGIN
    SELECT stream_type
      INTO v_stream_type
      FROM kafka_messaging.streams
     WHERE id = NEW.stream_id
       AND organization_id = NEW.organization_id;

    IF v_stream_type IN ('task_event', 'notification_event') THEN
        RAISE EXCEPTION
            'DB-021: task_event and notification_event streams cannot be activated on Kafka';
    END IF;

    IF NEW.status IN ('kafka_active', 'rabbitmq_draining', 'completed') THEN

        SELECT EXISTS (
            SELECT 1
            FROM kafka_messaging.dual_publish_metrics d
            WHERE d.organization_id = NEW.organization_id
              AND d.migration_id = NEW.id
              AND d.validation_status = 'passed'
        )
        INTO v_dual_ok;

        SELECT EXISTS (
            SELECT 1
            FROM kafka_messaging.ordering_validation o
            WHERE o.organization_id = NEW.organization_id
              AND o.migration_id = NEW.id
              AND o.validation_status = 'passed'
        )
        INTO v_order_ok;

        SELECT EXISTS (
            SELECT 1
            FROM kafka_messaging.load_test_evidence l
            WHERE l.organization_id = NEW.organization_id
              AND l.result_status = 'passed'
        )
        INTO v_load_ok;

        IF NOT v_dual_ok THEN
            RAISE EXCEPTION
                'DB-021: Kafka cutover requires passed dual-publish validation';
        END IF;

        IF NOT v_order_ok THEN
            RAISE EXCEPTION
                'DB-021: Kafka cutover requires passed ordering validation';
        END IF;

        IF NOT v_load_ok THEN
            RAISE EXCEPTION
                'DB-021: Kafka cutover requires passed NFR-06 load-test evidence';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_kafka_cutover_validation
ON kafka_messaging.stream_migrations;

CREATE TRIGGER trg_kafka_cutover_validation
BEFORE INSERT OR UPDATE OF status
ON kafka_messaging.stream_migrations
FOR EACH ROW
EXECUTE FUNCTION kafka_messaging.validate_kafka_cutover();


-- ============================================================
-- 13. RLS FOR REVIEW-FIX TABLES
-- ============================================================

ALTER TABLE kafka_messaging.dual_publish_metrics
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kafka_messaging.dual_publish_metrics
    FORCE ROW LEVEL SECURITY;

ALTER TABLE kafka_messaging.ordering_validation
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kafka_messaging.ordering_validation
    FORCE ROW LEVEL SECURITY;

ALTER TABLE kafka_messaging.load_test_evidence
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kafka_messaging.load_test_evidence
    FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS kafka_dual_publish_metrics_tenant_isolation
ON kafka_messaging.dual_publish_metrics;

CREATE POLICY kafka_dual_publish_metrics_tenant_isolation
ON kafka_messaging.dual_publish_metrics
USING (organization_id = app.require_organization_context())
WITH CHECK (organization_id = app.require_organization_context());

DROP POLICY IF EXISTS kafka_ordering_validation_tenant_isolation
ON kafka_messaging.ordering_validation;

CREATE POLICY kafka_ordering_validation_tenant_isolation
ON kafka_messaging.ordering_validation
USING (organization_id = app.require_organization_context())
WITH CHECK (organization_id = app.require_organization_context());

DROP POLICY IF EXISTS kafka_load_test_evidence_tenant_isolation
ON kafka_messaging.load_test_evidence;

CREATE POLICY kafka_load_test_evidence_tenant_isolation
ON kafka_messaging.load_test_evidence
USING (organization_id = app.require_organization_context())
WITH CHECK (organization_id = app.require_organization_context());


-- ============================================================
-- 14. COMMENTS
-- ============================================================

COMMENT ON TABLE kafka_messaging.dual_publish_metrics IS
    'DB-021 evidence comparing RabbitMQ and Kafka publication during dual-publish.';

COMMENT ON TABLE kafka_messaging.ordering_validation IS
    'DB-021 per-topic/per-partition ordering validation evidence.';

COMMENT ON TABLE kafka_messaging.load_test_evidence IS
    'DB-021 NFR-06 sustained and burst load-test evidence supplied by the external integration/load-test harness.';

COMMENT ON FUNCTION kafka_messaging.enforce_rabbitmq_only_stream() IS
    'DB-021 prevents task-event streams from being migrated to Kafka.';

COMMENT ON FUNCTION kafka_messaging.validate_migration_threshold() IS
    'DB-021 enforces the configured sustained daily-volume threshold before Kafka migration activation.';

COMMENT ON FUNCTION kafka_messaging.validate_kafka_cutover() IS
    'DB-021 requires dual-publish, ordering and NFR-06 load-test evidence before Kafka activation.';

-- ============================================================
-- 7. IMMUTABLE MIGRATION EVENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS kafka_messaging.migration_events
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,

    stream_id UUID NOT NULL,
    migration_id UUID NULL,

    event_type TEXT NOT NULL,

    previous_status TEXT NULL,
    new_status TEXT NULL,

    observed_messages_per_day BIGINT NULL,
    observed_burst_messages_per_minute BIGINT NULL,

    event_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    actor_id UUID NULL,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_kafka_migration_events
        PRIMARY KEY (id),

    CONSTRAINT fk_kafka_migration_events_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_kafka_migration_events_stream
        FOREIGN KEY (stream_id)
        REFERENCES kafka_messaging.streams(id),

    CONSTRAINT fk_kafka_migration_events_migration
        FOREIGN KEY (migration_id)
        REFERENCES kafka_messaging.stream_migrations(id),

    CONSTRAINT chk_kafka_migration_event_type
        CHECK (
            event_type IN (
                'MIGRATION_PLANNED',
                'DUAL_PUBLISH_STARTED',
                'VALIDATION_STARTED',
                'KAFKA_VALIDATED',
                'CUTOVER_STARTED',
                'KAFKA_ACTIVATED',
                'RABBITMQ_DRAINING',
                'MIGRATION_COMPLETED',
                'MIGRATION_FAILED',
                'MIGRATION_ROLLED_BACK'
            )
        ),

    CONSTRAINT chk_kafka_migration_event_metadata
        CHECK (jsonb_typeof(event_metadata) = 'object'),

    CONSTRAINT chk_kafka_migration_event_metrics
        CHECK (
            (observed_messages_per_day IS NULL
             OR observed_messages_per_day >= 0)
            AND
            (observed_burst_messages_per_minute IS NULL
             OR observed_burst_messages_per_minute >= 0)
        )
);

CREATE INDEX IF NOT EXISTS idx_kafka_migration_events_stream_time
    ON kafka_messaging.migration_events
       (organization_id, stream_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_kafka_migration_events_migration_time
    ON kafka_messaging.migration_events
       (organization_id, migration_id, occurred_at DESC);

-- ============================================================
-- 8. IMMUTABLE MIGRATION EVENT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION
kafka_messaging.prevent_migration_event_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'DB-021: Kafka migration events are append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_kafka_migration_event_immutable
ON kafka_messaging.migration_events;

CREATE TRIGGER trg_kafka_migration_event_immutable
BEFORE UPDATE OR DELETE
ON kafka_messaging.migration_events
FOR EACH ROW
EXECUTE FUNCTION
kafka_messaging.prevent_migration_event_mutation();

-- ============================================================
-- 9. RLS
-- ============================================================

ALTER TABLE kafka_messaging.streams
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kafka_messaging.streams
    FORCE ROW LEVEL SECURITY;

ALTER TABLE kafka_messaging.topic_partitions
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kafka_messaging.topic_partitions
    FORCE ROW LEVEL SECURITY;

ALTER TABLE kafka_messaging.stream_migrations
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kafka_messaging.stream_migrations
    FORCE ROW LEVEL SECURITY;

ALTER TABLE kafka_messaging.consumer_groups
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kafka_messaging.consumer_groups
    FORCE ROW LEVEL SECURITY;

ALTER TABLE kafka_messaging.migration_checkpoints
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kafka_messaging.migration_checkpoints
    FORCE ROW LEVEL SECURITY;

ALTER TABLE kafka_messaging.consumer_idempotency
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kafka_messaging.consumer_idempotency
    FORCE ROW LEVEL SECURITY;

ALTER TABLE kafka_messaging.migration_events
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kafka_messaging.migration_events
    FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS kafka_streams_tenant_isolation
ON kafka_messaging.streams;

CREATE POLICY kafka_streams_tenant_isolation
ON kafka_messaging.streams
USING (organization_id = app.require_organization_context())
WITH CHECK (organization_id = app.require_organization_context());

DROP POLICY IF EXISTS kafka_topic_partitions_tenant_isolation
ON kafka_messaging.topic_partitions;

CREATE POLICY kafka_topic_partitions_tenant_isolation
ON kafka_messaging.topic_partitions
USING (organization_id = app.require_organization_context())
WITH CHECK (organization_id = app.require_organization_context());

DROP POLICY IF EXISTS kafka_stream_migrations_tenant_isolation
ON kafka_messaging.stream_migrations;

CREATE POLICY kafka_stream_migrations_tenant_isolation
ON kafka_messaging.stream_migrations
USING (organization_id = app.require_organization_context())
WITH CHECK (organization_id = app.require_organization_context());

DROP POLICY IF EXISTS kafka_consumer_groups_tenant_isolation
ON kafka_messaging.consumer_groups;

CREATE POLICY kafka_consumer_groups_tenant_isolation
ON kafka_messaging.consumer_groups
USING (organization_id = app.require_organization_context())
WITH CHECK (organization_id = app.require_organization_context());

DROP POLICY IF EXISTS kafka_migration_checkpoints_tenant_isolation
ON kafka_messaging.migration_checkpoints;

CREATE POLICY kafka_migration_checkpoints_tenant_isolation
ON kafka_messaging.migration_checkpoints
USING (organization_id = app.require_organization_context())
WITH CHECK (organization_id = app.require_organization_context());

DROP POLICY IF EXISTS kafka_consumer_idempotency_tenant_isolation
ON kafka_messaging.consumer_idempotency;

CREATE POLICY kafka_consumer_idempotency_tenant_isolation
ON kafka_messaging.consumer_idempotency
USING (organization_id = app.require_organization_context())
WITH CHECK (organization_id = app.require_organization_context());

DROP POLICY IF EXISTS kafka_migration_events_tenant_isolation
ON kafka_messaging.migration_events;

CREATE POLICY kafka_migration_events_tenant_isolation
ON kafka_messaging.migration_events
USING (organization_id = app.require_organization_context())
WITH CHECK (organization_id = app.require_organization_context());

-- ============================================================
-- 10. OPERATIONAL VIEW
-- ============================================================

CREATE OR REPLACE VIEW kafka_messaging.active_stream_migrations
WITH (security_invoker = true)
AS
SELECT
    m.id AS migration_id,
    m.organization_id,
    m.stream_id,
    s.stream_code,
    s.stream_name,
    m.source_transport,
    m.target_transport,
    m.status,
    m.threshold_messages_per_day,
    m.observed_messages_last_24h,
    m.burst_messages_per_minute,
    m.planned_at,
    m.dual_publish_started_at,
    m.validation_started_at,
    m.kafka_activated_at,
    m.rabbitmq_draining_at,
    (
        COALESCE(m.observed_messages_last_24h, 0)
        >= m.threshold_messages_per_day
    ) AS daily_threshold_reached
FROM kafka_messaging.stream_migrations m
JOIN kafka_messaging.streams s
  ON s.id = m.stream_id
 AND s.organization_id = m.organization_id
WHERE m.status IN (
    'planned',
    'dual_publish',
    'validating',
    'kafka_active',
    'rabbitmq_draining'
);

-- ============================================================
-- 11. DOCUMENTED RABBITMQ BOUNDARY
-- ============================================================

COMMENT ON SCHEMA kafka_messaging IS
    'DB-021 PostgreSQL control plane for selective Kafka migration of high-volume streams. Kafka brokers/topics and RabbitMQ queues remain infrastructure responsibilities.';

COMMENT ON TABLE kafka_messaging.streams IS
    'Logical stream registry. RabbitMQ remains supported for task and notification queues; Kafka is selected for high-volume streams.';

COMMENT ON TABLE kafka_messaging.topic_partitions IS
    'Kafka topic/partition metadata used by the migration control plane. Does not create or manage Kafka broker objects.';

COMMENT ON TABLE kafka_messaging.stream_migrations IS
    'Controlled RabbitMQ-to-Kafka migration and cutover lifecycle.';

COMMENT ON TABLE kafka_messaging.migration_checkpoints IS
    'Durable PostgreSQL checkpoints for resumable Kafka consumers and migration recovery.';

COMMENT ON TABLE kafka_messaging.consumer_idempotency IS
    'Tenant-scoped Kafka event idempotency records preventing duplicate business processing.';

COMMENT ON TABLE kafka_messaging.migration_events IS
    'Immutable audit history for Kafka migration and cutover operations.';

COMMENT ON VIEW kafka_messaging.active_stream_migrations IS
    'Operational view of migrations that have not reached a final state.';

COMMIT;
