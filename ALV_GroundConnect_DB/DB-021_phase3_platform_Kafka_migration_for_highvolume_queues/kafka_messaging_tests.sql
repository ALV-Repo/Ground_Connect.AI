-- ============================================================
-- DB-021 | KAFKA MIGRATION FOR HIGH-VOLUME QUEUES
-- PostgreSQL verification tests
-- Requirement: NFR-06
-- ============================================================

DO $$
DECLARE
    v_count INTEGER;
BEGIN

    -- Schema
    SELECT COUNT(*) INTO v_count
    FROM information_schema.schemata
    WHERE schema_name = 'kafka_messaging';

    IF v_count <> 1 THEN
        RAISE EXCEPTION 'DB-021 test failed: kafka_messaging schema missing';
    END IF;

    -- Required tables
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'kafka_messaging'
      AND table_name IN (
          'streams',
          'topic_partitions',
          'stream_migrations',
          'consumer_groups',
          'migration_checkpoints',
          'consumer_idempotency',
          'migration_events'
      );

    IF v_count <> 7 THEN
        RAISE EXCEPTION
            'DB-021 test failed: required Kafka control tables missing';
    END IF;

    -- NFR-06 default migration threshold
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'kafka_messaging'
          AND table_name = 'streams'
          AND column_name = 'migration_threshold_messages_per_day'
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: 500k/day migration threshold field missing';
    END IF;

    -- RabbitMQ -> Kafka migration state
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'kafka_messaging'
          AND indexname = 'uq_kafka_stream_migrations_active'
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: active migration uniqueness missing';
    END IF;

    -- Checkpoint uniqueness
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_kafka_checkpoint'
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: Kafka checkpoint uniqueness missing';
    END IF;

    -- Consumer idempotency uniqueness
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_kafka_consumer_event'
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: Kafka consumer idempotency constraint missing';
    END IF;

    -- Migration lifecycle states
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_kafka_migration_status'
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: migration lifecycle constraint missing';
    END IF;

    -- Task and notification streams remain RabbitMQ-only.
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_kafka_streams_type'
          AND pg_get_constraintdef(oid) ILIKE '%notification_event%'
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: notification stream type missing';
    END IF;

    -- RabbitMQ remains source transport for migration
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_kafka_migration_source'
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: RabbitMQ source boundary missing';
    END IF;

    -- Kafka is target transport
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_kafka_migration_target'
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: Kafka target boundary missing';
    END IF;

    -- Migration events must be immutable.
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_kafka_migration_event_immutable'
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: immutable migration event trigger missing';
    END IF;

    -- Operational view
    SELECT COUNT(*) INTO v_count
    FROM information_schema.views
    WHERE table_schema = 'kafka_messaging'
      AND table_name = 'active_stream_migrations';

    IF v_count <> 1 THEN
        RAISE EXCEPTION
            'DB-021 test failed: active migration view missing';
    END IF;

    -- Review-fix tables
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'kafka_messaging'
      AND table_name IN (
          'dual_publish_metrics',
          'ordering_validation',
          'load_test_evidence'
      );

    IF v_count <> 3 THEN
        RAISE EXCEPTION
            'DB-021 test failed: validation/evidence tables missing';
    END IF;

    -- Burst/load evidence must record sustained and peak rates.
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'kafka_messaging'
          AND table_name = 'load_test_evidence'
          AND column_name IN (
              'sustained_messages_per_second',
              'peak_messages_per_second',
              'burst_multiplier'
          )
        GROUP BY table_schema, table_name
        HAVING COUNT(*) = 3
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: NFR-06 burst evidence fields missing';
    END IF;

    -- Dual-publish validation must capture both sides and mismatches.
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'kafka_messaging'
          AND table_name = 'dual_publish_metrics'
          AND column_name IN (
              'rabbitmq_published_count',
              'kafka_published_count',
              'missing_in_kafka_count',
              'missing_in_rabbitmq_count',
              'duplicate_event_count'
          )
        GROUP BY table_schema, table_name
        HAVING COUNT(*) = 5
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: dual-publish validation metrics incomplete';
    END IF;

    -- Ordering validation must be per partition.
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'kafka_messaging'
          AND table_name = 'ordering_validation'
          AND column_name IN (
              'topic_name',
              'partition_number',
              'first_sequence',
              'last_sequence',
              'ordering_violations'
          )
        GROUP BY table_schema, table_name
        HAVING COUNT(*) = 5
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: ordering validation fields missing';
    END IF;

    -- Burst threshold enforcement trigger.
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_kafka_migration_threshold'
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: burst/daily threshold enforcement missing';
    END IF;

    -- RabbitMQ-only task enforcement.
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_kafka_rabbitmq_only_migration'
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: RabbitMQ-only queue enforcement missing';
    END IF;

    -- Cutover validation guard.
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_kafka_cutover_validation'
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: Kafka cutover validation guard missing';
    END IF;

    -- RLS/FORCE RLS on all tenant-owned tables.
    SELECT COUNT(*) INTO v_count
    FROM pg_class c
    JOIN pg_namespace n
      ON n.oid = c.relnamespace
    WHERE n.nspname = 'kafka_messaging'
      AND c.relname IN (
          'streams',
          'topic_partitions',
          'stream_migrations',
          'consumer_groups',
          'migration_checkpoints',
          'consumer_idempotency',
          'migration_events'
      )
      AND c.relrowsecurity
      AND c.relforcerowsecurity;

    IF v_count <> 10 THEN
        RAISE EXCEPTION
            'DB-021 test failed: RLS/FORCE RLS missing on tenant tables';
    END IF;

    -- No plaintext Kafka credentials in the control plane.
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'kafka_messaging'
          AND column_name IN (
              'password',
              'kafka_password',
              'secret_value',
              'private_key',
              'sasl_password'
          )
    ) THEN
        RAISE EXCEPTION
            'DB-021 test failed: plaintext credential column detected';
    END IF;

    RAISE NOTICE 'DB-021 PostgreSQL tests passed.';
END;
$$;

-- ============================================================
-- IMPORTANT:
-- These SQL tests verify the PostgreSQL control plane only.
--
-- Real Kafka integration tests are required separately for:
--   * broker/topic creation
--   * producer delivery
--   * consumer groups
--   * partition ordering
--   * offset commits
--   * replay/retry
--   * dual-publish correctness
--   * cutover without message loss
--   * duplicate-event handling
--   * sustained 500,000 messages/day
--   * order-of-magnitude burst testing required by NFR-06
-- ============================================================
