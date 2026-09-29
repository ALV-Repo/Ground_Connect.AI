-- ============================================================
-- DB-022 | Query performance tuning for Phase-3 scale
-- ============================================================
-- Purpose:
--   1. Add Phase-3 hierarchy indexes without changing existing tables.
--   2. Define staged two-level partitioning targets for audit_events,
--      messaging.messages and citizen_issues.canonical_issues.
--   3. Provide read-replica routing/control-plane metadata.
--   4. Provide NFR-06 / HIER-06 load-test evidence storage.
--
-- IMPORTANT:
-- Native PostgreSQL partitioning by date + organization_id cannot be
-- applied in-place to the current tables while preserving their current
-- UUID-only primary keys and existing FK shape. PostgreSQL requires
-- partition-key columns in UNIQUE/PRIMARY KEY constraints on a
-- partitioned table. Therefore this file deliberately does NOT rename,
-- drop, or repartition the authoritative tables automatically.
-- The partition targets are staging targets for a controlled V003/
-- maintenance-window migration after dependent FKs are redesigned.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS phase3_performance;

-- ============================================================
-- 1. HIERARCHY INDEX REVIEW / 200K-NODE ACCESS PATHS
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_nodes_org_parent_id
    ON hierarchy_bitemporal_model.nodes (organization_id, parent_id, id);

CREATE INDEX IF NOT EXISTS idx_nodes_org_status_parent
    ON hierarchy_bitemporal_model.nodes (organization_id, status, parent_id, id);

CREATE INDEX IF NOT EXISTS idx_node_assignments_org_node_current
    ON hierarchy_bitemporal_model.node_assignments
       (organization_id, node_id, user_id)
    WHERE valid_to IS NULL;

CREATE INDEX IF NOT EXISTS idx_node_assignments_org_validity
    ON hierarchy_bitemporal_model.node_assignments
       (organization_id, node_id, valid_from, valid_to);

CREATE INDEX IF NOT EXISTS idx_node_assignments_org_user_current
    ON hierarchy_bitemporal_model.node_assignments
       (organization_id, user_id, node_id)
    WHERE valid_to IS NULL;

-- ============================================================
-- 2. LARGE-TABLE PARTITIONING CONTROL PLANE
-- ============================================================

CREATE TABLE IF NOT EXISTS phase3_performance.partition_targets
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    schema_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    date_column TEXT NOT NULL,
    tenant_column TEXT NOT NULL DEFAULT 'organization_id',
    partition_strategy TEXT NOT NULL DEFAULT 'RANGE(date) -> HASH(organization_id)',
    partition_interval TEXT NOT NULL DEFAULT 'monthly',
    status TEXT NOT NULL DEFAULT 'planned',
    target_daily_rows BIGINT NULL,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_partition_targets PRIMARY KEY (id),
    CONSTRAINT uq_partition_target UNIQUE (schema_name, table_name),
    CONSTRAINT chk_partition_target_status
        CHECK (status IN ('planned','staging','validated','cutover_ready','active','rolled_back')),
    CONSTRAINT chk_partition_target_strategy
        CHECK (partition_strategy = 'RANGE(date) -> HASH(organization_id)')
);

INSERT INTO phase3_performance.partition_targets
    (schema_name, table_name, date_column, target_daily_rows, notes)
VALUES
    ('audit_trail', 'audit_events', 'created_at', 5000000,
     'NFR-06 audit target; high-write append-only workload.'),
    ('messaging', 'messages', 'created_at', 500000,
     'NFR-06 message target; retain RabbitMQ task/notification queues.'),
    ('citizen_issues', 'canonical_issues', 'created_at', 10000,
     'NFR-06 issue target; tenant/date locality for dashboards and search.')
ON CONFLICT (schema_name, table_name) DO UPDATE
SET target_daily_rows = EXCLUDED.target_daily_rows,
    notes = EXCLUDED.notes,
    updated_at = CURRENT_TIMESTAMP;

-- ============================================================
-- 3. PARTITIONED STAGING TARGETS
-- ============================================================
-- These are intentionally separate from authoritative tables.
-- They prove the target physical design and can be populated during
-- a controlled migration rehearsal.

CREATE TABLE IF NOT EXISTS phase3_performance.audit_events_partitioned
(
    LIKE audit_trail.audit_events INCLUDING DEFAULTS INCLUDING STORAGE
)
PARTITION BY RANGE (created_at);

CREATE TABLE IF NOT EXISTS phase3_performance.messages_partitioned
(
    LIKE messaging.messages INCLUDING DEFAULTS INCLUDING STORAGE
)
PARTITION BY RANGE (created_at);

CREATE TABLE IF NOT EXISTS phase3_performance.issues_partitioned
(
    LIKE citizen_issues.canonical_issues INCLUDING DEFAULTS INCLUDING STORAGE
)
PARTITION BY RANGE (created_at);

-- ============================================================
-- 4. PARTITION CREATION HELPER
-- ============================================================

CREATE OR REPLACE FUNCTION phase3_performance.create_month_partitions
(
    p_start_month DATE,
    p_month_count INTEGER DEFAULT 12,
    p_hash_partitions INTEGER DEFAULT 8
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_i INTEGER;
    v_h INTEGER;
    v_month_start DATE;
    v_next_month DATE;
    v_range_name TEXT;
    v_child_name TEXT;
BEGIN
    IF p_month_count < 1 OR p_month_count > 60 THEN
        RAISE EXCEPTION 'p_month_count must be between 1 and 60';
    END IF;

    IF p_hash_partitions < 2 OR p_hash_partitions > 64 THEN
        RAISE EXCEPTION 'p_hash_partitions must be between 2 and 64';
    END IF;

    FOR v_i IN 0..p_month_count - 1 LOOP
        v_month_start := (p_start_month + make_interval(months => v_i))::date;
        v_next_month := (v_month_start + INTERVAL '1 month')::date;

        v_range_name := format('p_%s', to_char(v_month_start, 'YYYY_MM'));

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS phase3_performance.audit_events_%s
             PARTITION OF phase3_performance.audit_events_partitioned
             FOR VALUES FROM (%L) TO (%L)
             PARTITION BY HASH (organization_id)',
            v_range_name, v_month_start, v_next_month
        );

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS phase3_performance.messages_%s
             PARTITION OF phase3_performance.messages_partitioned
             FOR VALUES FROM (%L) TO (%L)
             PARTITION BY HASH (organization_id)',
            v_range_name, v_month_start, v_next_month
        );

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS phase3_performance.issues_%s
             PARTITION OF phase3_performance.issues_partitioned
             FOR VALUES FROM (%L) TO (%L)
             PARTITION BY HASH (organization_id)',
            v_range_name, v_month_start, v_next_month
        );

        FOR v_h IN 0..p_hash_partitions - 1 LOOP
            v_child_name := format('%s_h%s', v_range_name, v_h);

            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS phase3_performance.audit_events_%s
                 PARTITION OF phase3_performance.audit_events_%s
                 FOR VALUES WITH (MODULUS %s, REMAINDER %s)',
                v_child_name, v_range_name, p_hash_partitions, v_h
            );

            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS phase3_performance.messages_%s
                 PARTITION OF phase3_performance.messages_%s
                 FOR VALUES WITH (MODULUS %s, REMAINDER %s)',
                v_child_name, v_range_name, p_hash_partitions, v_h
            );

            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS phase3_performance.issues_%s
                 PARTITION OF phase3_performance.issues_%s
                 FOR VALUES WITH (MODULUS %s, REMAINDER %s)',
                v_child_name, v_range_name, p_hash_partitions, v_h
            );
        END LOOP;
    END LOOP;
END;
$$;

-- Example maintenance-window preparation:
-- SELECT phase3_performance.create_month_partitions('2026-01-01', 24, 8);

-- ============================================================
-- 5. PARTITION MIGRATION VALIDATION
-- ============================================================

CREATE OR REPLACE VIEW phase3_performance.partition_target_status AS
SELECT
    pt.schema_name,
    pt.table_name,
    pt.date_column,
    pt.tenant_column,
    pt.partition_strategy,
    pt.partition_interval,
    pt.status,
    pt.target_daily_rows,
    CASE
        WHEN pt.schema_name = 'audit_trail'
         AND pt.table_name = 'audit_events'
            THEN 5000000::BIGINT
        WHEN pt.schema_name = 'messaging'
         AND pt.table_name = 'messages'
            THEN 500000::BIGINT
        WHEN pt.schema_name = 'citizen_issues'
         AND pt.table_name = 'canonical_issues'
            THEN 10000::BIGINT
    END AS nfr06_daily_target
FROM phase3_performance.partition_targets pt;

-- ============================================================
-- 6. READ-REPLICA ROUTING CONTROL PLANE
-- ============================================================

CREATE TABLE IF NOT EXISTS phase3_performance.read_endpoints
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    endpoint_name TEXT NOT NULL,
    endpoint_role TEXT NOT NULL,
    connection_secret_ref TEXT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    max_replica_lag_seconds INTEGER NOT NULL DEFAULT 5,
    priority INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_read_endpoints PRIMARY KEY (id),
    CONSTRAINT uq_read_endpoint_name UNIQUE (endpoint_name),
    CONSTRAINT chk_read_endpoint_role
        CHECK (endpoint_role IN ('primary','read_replica')),
    CONSTRAINT chk_read_endpoint_lag
        CHECK (max_replica_lag_seconds >= 0),
    CONSTRAINT chk_read_endpoint_priority
        CHECK (priority > 0)
);

CREATE TABLE IF NOT EXISTS phase3_performance.read_workloads
(
    workload_code TEXT PRIMARY KEY,
    route_class TEXT NOT NULL,
    allow_replica BOOLEAN NOT NULL,
    require_fresh_primary BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT NOT NULL,

    CONSTRAINT chk_read_workload_route
        CHECK (route_class IN ('dashboard','search','transactional','audit_export','migration')),
    CONSTRAINT chk_read_workload_flags
        CHECK (NOT (allow_replica AND require_fresh_primary))
);

INSERT INTO phase3_performance.read_workloads
    (workload_code, route_class, allow_replica, require_fresh_primary, description)
VALUES
    ('dashboard', 'dashboard', TRUE, FALSE, 'Read-heavy dashboards and aggregates.'),
    ('search', 'search', TRUE, FALSE, 'Search/listing workloads where bounded replica lag is acceptable.'),
    ('transactional', 'transactional', FALSE, TRUE, 'User-facing reads requiring current primary state.'),
    ('audit_export', 'audit_export', FALSE, TRUE, 'Authoritative audit export/read path.'),
    ('migration', 'migration', FALSE, TRUE, 'Migration and control-plane validation.')
ON CONFLICT (workload_code) DO UPDATE
SET route_class = EXCLUDED.route_class,
    allow_replica = EXCLUDED.allow_replica,
    require_fresh_primary = EXCLUDED.require_fresh_primary,
    description = EXCLUDED.description;

INSERT INTO phase3_performance.read_endpoints
    (endpoint_name, endpoint_role, connection_secret_ref, enabled, max_replica_lag_seconds, priority)
VALUES
    ('primary', 'primary', NULL, TRUE, 0, 1),
    ('read_replica_01', 'read_replica', NULL, TRUE, 5, 10)
ON CONFLICT (endpoint_name) DO UPDATE
SET endpoint_role = EXCLUDED.endpoint_role,
    enabled = EXCLUDED.enabled,
    max_replica_lag_seconds = EXCLUDED.max_replica_lag_seconds,
    priority = EXCLUDED.priority;

CREATE OR REPLACE FUNCTION phase3_performance.choose_read_endpoint
(
    p_workload_code TEXT,
    p_replica_lag_seconds INTEGER DEFAULT NULL
)
RETURNS TEXT
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_allow_replica BOOLEAN;
    v_require_primary BOOLEAN;
BEGIN
    SELECT allow_replica, require_fresh_primary
      INTO v_allow_replica, v_require_primary
      FROM phase3_performance.read_workloads
     WHERE workload_code = p_workload_code;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown read workload: %', p_workload_code;
    END IF;

    IF v_require_primary OR NOT v_allow_replica THEN
        RETURN 'primary';
    END IF;

    IF p_replica_lag_seconds IS NULL THEN
        RETURN 'read_replica';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM phase3_performance.read_endpoints
        WHERE endpoint_role = 'read_replica'
          AND enabled = TRUE
          AND max_replica_lag_seconds >= p_replica_lag_seconds
        ORDER BY priority
        LIMIT 1
    ) THEN
        RETURN 'read_replica';
    END IF;

    RETURN 'primary';
END;
$$;

-- The application must use a read-only transaction on the selected replica.
-- PostgreSQL cannot route an existing connection to another server; routing
-- belongs in the connection/pool layer.

-- ============================================================
-- 7. NFR-06 / HIER-06 LOAD-TEST EVIDENCE
-- ============================================================

CREATE TABLE IF NOT EXISTS phase3_performance.load_test_runs
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    run_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL,
    concurrent_users INTEGER NOT NULL,
    peak_concurrent_users INTEGER NOT NULL,
    hierarchy_nodes_per_tenant INTEGER NOT NULL,
    members_total INTEGER NOT NULL,
    messages_per_day_target BIGINT NOT NULL DEFAULT 500000,
    issues_per_day_target BIGINT NOT NULL DEFAULT 10000,
    media_uploads_per_day_target BIGINT NOT NULL DEFAULT 50000,
    audit_events_per_day_target BIGINT NOT NULL DEFAULT 5000000,
    burst_multiplier NUMERIC(8,2) NOT NULL DEFAULT 10.0,
    result_status TEXT NOT NULL DEFAULT 'planned',
    evidence_reference TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT pk_load_test_runs PRIMARY KEY (id),
    CONSTRAINT uq_load_test_run_name UNIQUE (run_name),
    CONSTRAINT chk_load_test_status
        CHECK (result_status IN ('planned','running','passed','failed','blocked')),
    CONSTRAINT chk_load_test_users
        CHECK (concurrent_users > 0 AND peak_concurrent_users >= concurrent_users),
    CONSTRAINT chk_load_test_scale
        CHECK (
            hierarchy_nodes_per_tenant >= 200000
            AND members_total >= 200000
            AND messages_per_day_target >= 500000
            AND issues_per_day_target >= 10000
            AND media_uploads_per_day_target >= 50000
            AND audit_events_per_day_target >= 5000000
        ),
    CONSTRAINT chk_load_test_burst
        CHECK (burst_multiplier >= 10.0)
);

CREATE TABLE IF NOT EXISTS phase3_performance.load_test_metrics
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,
    workload_name TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL,
    requests_total BIGINT NOT NULL,
    requests_failed BIGINT NOT NULL DEFAULT 0,
    throughput_per_second NUMERIC(18,4) NOT NULL,
    p50_ms NUMERIC(12,3) NULL,
    p95_ms NUMERIC(12,3) NULL,
    p99_ms NUMERIC(12,3) NULL,
    max_replica_lag_seconds NUMERIC(12,3) NULL,
    max_hierarchy_query_ms NUMERIC(12,3) NULL,
    max_dashboard_query_ms NUMERIC(12,3) NULL,
    max_search_query_ms NUMERIC(12,3) NULL,
    burst_peak_per_second NUMERIC(18,4) NULL,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT pk_load_test_metrics PRIMARY KEY (id),
    CONSTRAINT fk_load_test_metrics_run
        FOREIGN KEY (run_id)
        REFERENCES phase3_performance.load_test_runs(id)
        ON DELETE CASCADE,
    CONSTRAINT chk_load_test_metrics_values
        CHECK (
            duration_seconds > 0
            AND requests_total >= 0
            AND requests_failed >= 0
            AND requests_failed <= requests_total
            AND throughput_per_second >= 0
            AND (p95_ms IS NULL OR p95_ms >= 0)
            AND (p99_ms IS NULL OR p99_ms >= 0)
            AND (max_replica_lag_seconds IS NULL OR max_replica_lag_seconds >= 0)
            AND (max_hierarchy_query_ms IS NULL OR max_hierarchy_query_ms >= 0)
        )
);

CREATE INDEX IF NOT EXISTS idx_load_test_metrics_run_workload
    ON phase3_performance.load_test_metrics (run_id, workload_name, measured_at DESC);

-- ============================================================
-- 8. HIERARCHY PERFORMANCE CHECK QUERIES
-- ============================================================
-- These are intentionally views/helpers, not benchmark claims.

CREATE OR REPLACE VIEW phase3_performance.hierarchy_index_inventory AS
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'hierarchy_bitemporal_model'
  AND tablename IN ('nodes','node_assignments');

COMMENT ON SCHEMA phase3_performance IS
'DB-022 Phase-3 performance controls: partitioning staging, hierarchy indexes, read-replica routing, and NFR-06/HIER-06 load evidence.';

COMMENT ON TABLE phase3_performance.partition_targets IS
'Staged physical-design targets. Authoritative table cutover requires FK/PK redesign and maintenance-window migration.';

COMMENT ON FUNCTION phase3_performance.choose_read_endpoint(TEXT, INTEGER) IS
'Returns primary or read_replica based on workload freshness requirements and configured replica lag ceiling.';

COMMENT ON TABLE phase3_performance.load_test_runs IS
'Evidence registry for NFR-06 Phase-3 scale tests, including 200k members/nodes and 10x burst requirements.';

-- ============================================================
-- 9. PARTITION-LOCAL INDEXES
-- ============================================================
-- PostgreSQL creates indexes on partitioned parents, but DB-022 requires
-- explicit verification that every leaf partition has the required local
-- access paths. This helper applies indexes to every existing leaf.

CREATE OR REPLACE FUNCTION phase3_performance.create_partition_local_indexes()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
    v_count INTEGER := 0;
    v_table TEXT;
BEGIN
    FOR r IN
        SELECT n.nspname, c.relname
        FROM (
            SELECT relid
            FROM pg_partition_tree('phase3_performance.audit_events_partitioned'::regclass)
            WHERE isleaf
            UNION
            SELECT relid
            FROM pg_partition_tree('phase3_performance.messages_partitioned'::regclass)
            WHERE isleaf
            UNION
            SELECT relid
            FROM pg_partition_tree('phase3_performance.issues_partitioned'::regclass)
            WHERE isleaf
        ) leaves
        JOIN pg_class c ON c.oid = leaves.relid
        JOIN pg_namespace n ON n.oid = c.relnamespace
    LOOP
        v_table := format('%I.%I', r.nspname, r.relname);

        IF r.relname LIKE 'audit_events_%' THEN
            EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %s (organization_id, created_at DESC)',
                           'idx_' || r.relname || '_org_created', v_table);
            EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %s (organization_id, seq DESC)',
                           'idx_' || r.relname || '_org_seq', v_table);
        ELSIF r.relname LIKE 'messages_%' THEN
            EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %s (organization_id, created_at DESC)',
                           'idx_' || r.relname || '_org_created', v_table);
            EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %s (organization_id, status, created_at DESC)',
                           'idx_' || r.relname || '_org_status_created', v_table);
        ELSIF r.relname LIKE 'issues_%' THEN
            EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %s (organization_id, created_at DESC)',
                           'idx_' || r.relname || '_org_created', v_table);
            EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %s (organization_id, status, sla_resolution_deadline)',
                           'idx_' || r.relname || '_org_status_sla', v_table);
        END IF;
        v_count := v_count + 1;
    END LOOP;

    RETURN v_count;
END;
$$;

-- ============================================================
-- 10. REPLICA LAG TELEMETRY
-- ============================================================

CREATE TABLE IF NOT EXISTS phase3_performance.replica_lag_telemetry
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    endpoint_name TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lag_bytes BIGINT NULL,
    lag_seconds NUMERIC(18,6) NULL,
    replay_lsn PG_LSN NULL,
    primary_lsn PG_LSN NULL,
    is_replay_paused BOOLEAN NULL,
    source TEXT NOT NULL DEFAULT 'pg_stat_replication',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT pk_replica_lag_telemetry PRIMARY KEY (id),
    CONSTRAINT chk_replica_lag_values CHECK (
        (lag_bytes IS NULL OR lag_bytes >= 0)
        AND (lag_seconds IS NULL OR lag_seconds >= 0)
    )
);

CREATE INDEX IF NOT EXISTS idx_replica_lag_telemetry_endpoint_time
    ON phase3_performance.replica_lag_telemetry (endpoint_name, captured_at DESC);

CREATE OR REPLACE FUNCTION phase3_performance.capture_replica_lag_telemetry()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
    v_count INTEGER := 0;
    v_lag_seconds NUMERIC(18,6);
    v_lag_bytes BIGINT;
BEGIN
    FOR r IN
        SELECT application_name,
               write_lag,
               flush_lag,
               replay_lag,
               replay_lsn,
               pg_current_wal_lsn() AS primary_lsn,
               pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)::BIGINT AS lag_bytes
        FROM pg_stat_replication
    LOOP
        v_lag_seconds := EXTRACT(EPOCH FROM COALESCE(r.replay_lag, r.flush_lag, r.write_lag));
        v_lag_bytes := GREATEST(COALESCE(r.lag_bytes, 0), 0);

        INSERT INTO phase3_performance.replica_lag_telemetry
        (endpoint_name, lag_bytes, lag_seconds, replay_lsn, primary_lsn, metadata)
        VALUES
        (COALESCE(NULLIF(r.application_name, ''), 'unnamed_replica'),
         v_lag_bytes, v_lag_seconds, r.replay_lsn, r.primary_lsn,
         jsonb_build_object('captured_from', 'pg_stat_replication'));
        v_count := v_count + 1;
    END LOOP;
    RETURN v_count;
END;
$$;

-- ============================================================
-- 11. EXPLAIN ANALYZE EVIDENCE
-- ============================================================

CREATE TABLE IF NOT EXISTS phase3_performance.explain_evidence
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    test_run_id UUID NULL,
    workload_name TEXT NOT NULL,
    query_name TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms NUMERIC(18,3) NULL,
    planning_time_ms NUMERIC(18,3) NULL,
    plan_json JSONB NOT NULL,
    notes TEXT NULL,
    CONSTRAINT pk_explain_evidence PRIMARY KEY (id),
    CONSTRAINT fk_explain_evidence_run FOREIGN KEY (test_run_id)
        REFERENCES phase3_performance.load_test_runs(id) ON DELETE SET NULL,
    CONSTRAINT chk_explain_evidence_times CHECK (
        (execution_time_ms IS NULL OR execution_time_ms >= 0)
        AND (planning_time_ms IS NULL OR planning_time_ms >= 0)
    )
);

CREATE INDEX IF NOT EXISTS idx_explain_evidence_workload_time
    ON phase3_performance.explain_evidence (workload_name, captured_at DESC);

CREATE OR REPLACE FUNCTION phase3_performance.record_explain_evidence(
    p_test_run_id UUID,
    p_workload_name TEXT,
    p_query_name TEXT,
    p_plan JSONB,
    p_execution_time_ms NUMERIC DEFAULT NULL,
    p_planning_time_ms NUMERIC DEFAULT NULL,
    p_notes TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO phase3_performance.explain_evidence
    (test_run_id, workload_name, query_name, plan_json,
     execution_time_ms, planning_time_ms, notes)
    VALUES
    (p_test_run_id, p_workload_name, p_query_name, p_plan,
     p_execution_time_ms, p_planning_time_ms, p_notes)
    RETURNING id INTO v_id;
    RETURN v_id;
END;
$$;

-- ============================================================
-- 12. EXECUTABLE PHASE-3 VALIDATION REGISTRY
-- ============================================================

CREATE TABLE IF NOT EXISTS phase3_performance.validation_results
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    test_run_id UUID NULL,
    validation_name TEXT NOT NULL,
    target_value TEXT NOT NULL,
    observed_value TEXT NULL,
    status TEXT NOT NULL,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    evidence_reference TEXT NULL,
    notes TEXT NULL,
    CONSTRAINT pk_validation_results PRIMARY KEY (id),
    CONSTRAINT fk_validation_results_run FOREIGN KEY (test_run_id)
        REFERENCES phase3_performance.load_test_runs(id) ON DELETE SET NULL,
    CONSTRAINT chk_validation_status CHECK (status IN ('passed','failed','blocked','not_run'))
);

CREATE INDEX IF NOT EXISTS idx_validation_results_run_status
    ON phase3_performance.validation_results (test_run_id, status, measured_at DESC);

COMMENT ON TABLE phase3_performance.replica_lag_telemetry IS
'Actual PostgreSQL replica lag observations captured from pg_stat_replication; not a configuration claim.';

COMMENT ON TABLE phase3_performance.explain_evidence IS
'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) evidence captured from a real database execution.';

COMMENT ON TABLE phase3_performance.validation_results IS
'Executable DB-022 validation outcomes. A registered target is not considered proof until a passed result is recorded.';
