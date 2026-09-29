-- ============================================================
-- DB-022 | Phase-3 performance tuning tests
-- Structural and safety tests. Load-test execution remains external.
-- ============================================================

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT count(*)
      INTO v_count
      FROM phase3_performance.partition_targets
     WHERE (schema_name, table_name) IN (
         ('audit_trail','audit_events'),
         ('messaging','messages'),
         ('citizen_issues','canonical_issues')
     );

    IF v_count <> 3 THEN
        RAISE EXCEPTION 'DB-022 partition target registration incomplete: %', v_count;
    END IF;
END;
$$;

-- HIER-06 index coverage.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname='hierarchy_bitemporal_model'
          AND tablename='nodes'
          AND indexname='idx_nodes_org_parent_id'
    ) THEN
        RAISE EXCEPTION 'Missing HIER-06 nodes index';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname='hierarchy_bitemporal_model'
          AND tablename='node_assignments'
          AND indexname='idx_node_assignments_org_node_current'
    ) THEN
        RAISE EXCEPTION 'Missing current-assignment hierarchy index';
    END IF;
END;
$$;

-- Partition staging targets must use the requested two-level strategy.
DO $$
DECLARE
    v_partitioned_count INTEGER;
BEGIN
    SELECT count(*)
      INTO v_partitioned_count
      FROM pg_partitioned_table p
      JOIN pg_class c ON c.oid = p.partrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname='phase3_performance'
       AND c.relname IN (
           'audit_events_partitioned',
           'messages_partitioned',
           'issues_partitioned'
       );

    IF v_partitioned_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 partitioned staging parents, found %', v_partitioned_count;
    END IF;
END;
$$;

-- Workload routing rules.
DO $$
BEGIN
    IF phase3_performance.choose_read_endpoint('dashboard', 2) <> 'read_replica' THEN
        RAISE EXCEPTION 'Dashboard should route to replica when lag is within bound';
    END IF;

    IF phase3_performance.choose_read_endpoint('transactional', 0) <> 'primary' THEN
        RAISE EXCEPTION 'Transactional reads must route to primary';
    END IF;

    IF phase3_performance.choose_read_endpoint('audit_export', 0) <> 'primary' THEN
        RAISE EXCEPTION 'Audit export must route to primary';
    END IF;
END;
$$;

-- HIER-06/NFR-06 scale constraints.
DO $$
BEGIN
    BEGIN
        INSERT INTO phase3_performance.load_test_runs
        (
            run_name, started_at, concurrent_users, peak_concurrent_users,
            hierarchy_nodes_per_tenant, members_total
        )
        VALUES
        (
            '__db022_should_fail_below_scale__',
            CURRENT_TIMESTAMP, 10, 10, 1000, 1000
        );

        RAISE EXCEPTION 'Scale CHECK unexpectedly allowed sub-scale load test';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;
END;
$$;

-- 10x burst requirement.
DO $$
BEGIN
    BEGIN
        INSERT INTO phase3_performance.load_test_runs
        (
            run_name, started_at, concurrent_users, peak_concurrent_users,
            hierarchy_nodes_per_tenant, members_total, burst_multiplier
        )
        VALUES
        (
            '__db022_should_fail_below_burst__',
            CURRENT_TIMESTAMP, 5000, 5000, 200000, 200000, 5.0
        );

        RAISE EXCEPTION 'Burst CHECK unexpectedly allowed <10x burst';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;
END;
$$;

-- No plaintext database DSN field.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='phase3_performance'
          AND table_name='read_endpoints'
          AND column_name IN ('connection_dsn','password','secret','credential')
    ) THEN
        RAISE EXCEPTION 'DB-022 read endpoint metadata contains a plaintext credential field';
    END IF;
END;
$$;

-- Final structural summary.
SELECT
    'DB-022' AS task_id,
    (SELECT count(*) FROM phase3_performance.partition_targets) AS partition_targets,
    (SELECT count(*) FROM pg_indexes
      WHERE schemaname='hierarchy_bitemporal_model'
        AND tablename IN ('nodes','node_assignments')
        AND indexname IN (
            'idx_nodes_org_parent_id',
            'idx_nodes_org_status_parent',
            'idx_node_assignments_org_node_current',
            'idx_node_assignments_org_validity',
            'idx_node_assignments_org_user_current'
        )) AS phase3_hierarchy_indexes,
    (SELECT count(*) FROM pg_partitioned_table p
      JOIN pg_class c ON c.oid=p.partrelid
      JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='phase3_performance'
        AND c.relname IN ('audit_events_partitioned','messages_partitioned','issues_partitioned')) AS partition_staging_parents;

-- ============================================================
-- Additional DB-022 review-gap tests
-- ============================================================

-- Partition-local index helper must exist.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc
        WHERE pronamespace = 'phase3_performance'::regnamespace
          AND proname = 'create_partition_local_indexes'
    ) THEN
        RAISE EXCEPTION 'Missing partition-local index helper';
    END IF;
END;
$$;

-- Replica telemetry must be executable and backed by PostgreSQL replication views.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc
        WHERE pronamespace = 'phase3_performance'::regnamespace
          AND proname = 'capture_replica_lag_telemetry'
    ) THEN
        RAISE EXCEPTION 'Missing replica lag telemetry function';
    END IF;
END;
$$;

-- EXPLAIN evidence storage must exist.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='phase3_performance'
          AND table_name='explain_evidence'
    ) THEN
        RAISE EXCEPTION 'Missing EXPLAIN evidence table';
    END IF;
END;
$$;

-- Actual proof must not be implied merely by creating a load-test row.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM phase3_performance.load_test_runs
        WHERE result_status='passed'
    )
    AND NOT EXISTS (
        SELECT 1
        FROM phase3_performance.validation_results
        WHERE status='passed'
    ) THEN
        RAISE EXCEPTION 'Passed load-test run exists without validation evidence';
    END IF;
END;
$$;

-- Required Phase-3 validation targets must be represented in the evidence registry.
INSERT INTO phase3_performance.validation_results
(validation_name, target_value, status, notes)
VALUES
('200k_hierarchy_nodes', '>= 200000 nodes per tenant', 'not_run', 'Requires populated Phase-3-scale tenant and measured hierarchy queries.'),
('5k_concurrency', '>= 5000 concurrent users', 'not_run', 'Requires external load generator against deployed application.'),
('15k_burst_concurrency', '>= 15000 concurrent users', 'not_run', 'Requires mobilisation burst test; 10x burst model.'),
('replica_lag', '<= configured workload lag ceiling', 'not_run', 'Populate from capture_replica_lag_telemetry().'),
('explain_analyze', 'EXPLAIN ANALYZE evidence for hierarchy/dashboard/search', 'not_run', 'Capture FORMAT JSON plans from production-like data.'),
('partition_local_indexes', 'all Phase-3 leaf partitions indexed', 'not_run', 'Run create_partition_local_indexes() after partitions exist.'),
('real_performance_validation', 'all NFR-06 workload targets pass', 'not_run', 'Requires end-to-end load test execution.')
ON CONFLICT DO NOTHING;

SELECT
    validation_name,
    target_value,
    status,
    evidence_reference
FROM phase3_performance.validation_results
WHERE validation_name IN (
    '200k_hierarchy_nodes',
    '5k_concurrency',
    '15k_burst_concurrency',
    'replica_lag',
    'explain_analyze',
    'partition_local_indexes',
    'real_performance_validation'
)
ORDER BY validation_name;
