/*
===============================================================================
FILE:
    01_point_in_time_200k_benchmark.sql

PURPOSE:
    Validate point-in-time hierarchy performance at 200,000 nodes.

REQUIREMENT:
    Authorization decision <= 10 ms p95 at 200,000 nodes.

TESTS:
    1. Structure at T
    2. Ancestors at T
    3. Descendants at T
    4. Subtree membership at T
    5. Responsible-person lookup

IMPORTANT:
    - Benchmark organization is isolated.
    - Benchmark data is rolled back at the end.
    - Production data is not modified permanently.
    - This benchmark measures database execution time.
    - Final acceptance requires p95 <= 10 ms for the authorization path.
===============================================================================
*/


BEGIN;


/*
===============================================================================
1. BENCHMARK PARAMETERS
===============================================================================
*/

DROP TABLE IF EXISTS pg_temp.benchmark_parameters;

CREATE TEMP TABLE benchmark_parameters
(
    organization_id UUID NOT NULL,
    at_time         TIMESTAMPTZ NOT NULL,

    root_node_id    UUID,
    level1_node_id  UUID,
    level2_node_id  UUID,
    level3_node_id  UUID,
    target_node_id  UUID
);

INSERT INTO benchmark_parameters
(
    organization_id,
    at_time
)
VALUES
(
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    '2026-09-15 12:00:00+05:30'
);


/*
===============================================================================
2. BENCHMARK ORGANIZATION
===============================================================================

200,000 nodes arranged approximately as:

Root
├── 10 Level-1 nodes
│
├── 100 Level-2 nodes
│
├── 1,000 Level-3 nodes
│
└── 198,889 Level-4 nodes

Total = 200,000 nodes

This gives:
    - hierarchy depth = 4
    - substantial branching
    - realistic descendant traversal
    - deep ancestor traversal
===============================================================================
*/


/*
===============================================================================
3. GENERATE 200,000 NODES
===============================================================================
*/

INSERT INTO hierarchy_bitemporal_model_v2.nodes
(
    id,
    organization_id,
    level_id,
    code,
    name,
    status,
    created_at,
    updated_at
)
SELECT
    (
        md5(
            'benchmark-node-' ||
            gs::text
        ) ||
        md5(
            'benchmark-node-second-' ||
            gs::text
        )
    )::uuid AS id,

    bp.organization_id,

    (
        md5(
            'benchmark-level-' ||
            CASE
                WHEN gs = 1 THEN 0
                WHEN gs BETWEEN 2 AND 11 THEN 1
                WHEN gs BETWEEN 12 AND 111 THEN 2
                WHEN gs BETWEEN 112 AND 1111 THEN 3
                ELSE 4
            END
        ) ||
        md5(
            'benchmark-level-second-' ||
            CASE
                WHEN gs = 1 THEN 0
                WHEN gs BETWEEN 2 AND 11 THEN 1
                WHEN gs BETWEEN 12 AND 111 THEN 2
                WHEN gs BETWEEN 112 AND 1111 THEN 3
                ELSE 4
            END
        )
    )::uuid AS level_id,

    'BENCH-' || LPAD(gs::text, 6, '0'),

    CASE
        WHEN gs = 1
            THEN 'Benchmark Root'

        WHEN gs BETWEEN 2 AND 11
            THEN 'Level 1 - ' || (gs - 1)::text

        WHEN gs BETWEEN 12 AND 111
            THEN 'Level 2 - ' || (gs - 11)::text

        WHEN gs BETWEEN 112 AND 1111
            THEN 'Level 3 - ' || (gs - 111)::text

        ELSE
            'Level 4 - ' || (gs - 1111)::text
    END,

    'ACTIVE',

    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP

FROM generate_series(1, 200000) gs
CROSS JOIN benchmark_parameters bp;


/*
===============================================================================
4. VERIFY NODE COUNT
===============================================================================
*/

SELECT
    COUNT(*) AS benchmark_node_count
FROM hierarchy_bitemporal_model_v2.nodes
WHERE organization_id =
      'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';


/*
Expected:

    200000
*/


/*
===============================================================================
5. CREATE PARENT ASSIGNMENTS
===============================================================================

Root:
    1

Level 1:
    2 - 11
    parent = root

Level 2:
    12 - 111
    10 children per Level-1

Level 3:
    112 - 1111
    10 children per Level-2

Level 4:
    1112 - 200000
    distributed across Level-3 nodes
===============================================================================
*/

INSERT INTO hierarchy_bitemporal_model_v2.node_assignments
(
    id,
    organization_id,
    node_id,
    parent_node_id,
    valid_from,
    valid_to,
    recorded_at,
    recorded_by
)
SELECT
    (
        md5(
            'benchmark-assignment-' ||
            gs::text
        ) ||
        md5(
            'benchmark-assignment-second-' ||
            gs::text
        )
    )::uuid AS id,

    bp.organization_id,

    child.id,

    parent.id,

    '2026-01-01 00:00:00+05:30',

    NULL,

    CURRENT_TIMESTAMP,

    (
        md5('benchmark-recorded-by') ||
        md5('benchmark-recorded-by-second')
    )::uuid

FROM generate_series(2, 200000) gs

CROSS JOIN benchmark_parameters bp

JOIN hierarchy_bitemporal_model_v2.nodes child
  ON child.organization_id = bp.organization_id
 AND child.code =
     'BENCH-' || LPAD(gs::text, 6, '0')

JOIN hierarchy_bitemporal_model_v2.nodes parent
  ON parent.organization_id = bp.organization_id

 AND parent.code =
 CASE

     /*
     Level 1 → Root
     */
     WHEN gs BETWEEN 2 AND 11
         THEN 'BENCH-000001'

     /*
     Level 2 → Level 1
     */
     WHEN gs BETWEEN 12 AND 111
         THEN
             'BENCH-' ||
             LPAD(
                 (
                     2 +
                     ((gs - 12) / 10)
                 )::text,
                 6,
                 '0'
             )

     /*
     Level 3 → Level 2
     */
     WHEN gs BETWEEN 112 AND 1111
         THEN
             'BENCH-' ||
             LPAD(
                 (
                     12 +
                     ((gs - 112) / 10)
                 )::text,
                 6,
                 '0'
             )

     /*
     Level 4 → Level 3

     Distribute the 198,889 Level-4 nodes across the
     1,000 Level-3 nodes.
     */
     ELSE
         'BENCH-' ||
         LPAD(
             (
                 112 +
                 ((gs - 1112) % 1000)
             )::text,
             6,
             '0'
         )

 END;


/*
===============================================================================
6. VERIFY ASSIGNMENT COUNT
===============================================================================
*/

SELECT
    COUNT(*) AS benchmark_assignment_count
FROM hierarchy_bitemporal_model_v2.node_assignments
WHERE organization_id =
      'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';


/*
Expected:

    199999
*/


/*
===============================================================================
7. STORE TEST NODE IDS
===============================================================================
*/

UPDATE benchmark_parameters
SET
    root_node_id =
    (
        SELECT id
        FROM hierarchy_bitemporal_model_v2.nodes
        WHERE organization_id = benchmark_parameters.organization_id
          AND code = 'BENCH-000001'
    ),

    level1_node_id =
    (
        SELECT id
        FROM hierarchy_bitemporal_model_v2.nodes
        WHERE organization_id = benchmark_parameters.organization_id
          AND code = 'BENCH-000002'
    ),

    level2_node_id =
    (
        SELECT id
        FROM hierarchy_bitemporal_model_v2.nodes
        WHERE organization_id = benchmark_parameters.organization_id
          AND code = 'BENCH-000012'
    ),

    level3_node_id =
    (
        SELECT id
        FROM hierarchy_bitemporal_model_v2.nodes
        WHERE organization_id = benchmark_parameters.organization_id
          AND code = 'BENCH-000112'
    ),

    target_node_id =
    (
        SELECT id
        FROM hierarchy_bitemporal_model_v2.nodes
        WHERE organization_id = benchmark_parameters.organization_id
          AND code = 'BENCH-200000'
    );


/*
===============================================================================
8. SHOW TEST PARAMETERS
===============================================================================
*/

SELECT *
FROM benchmark_parameters;


/*
===============================================================================
9. REFRESH STATISTICS
===============================================================================
*/

ANALYZE hierarchy_bitemporal_model_v2.nodes;

ANALYZE hierarchy_bitemporal_model_v2.node_assignments;


/*
===============================================================================
10. VERIFY REQUIRED INDEXES
===============================================================================
*/

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname =
      'hierarchy_bitemporal_model_v2'
  AND tablename =
      'node_assignments'
ORDER BY indexname;


/*
===============================================================================
11. TEST 1 — STRUCTURE AT T
===============================================================================
*/

EXPLAIN (ANALYZE, BUFFERS, TIMING)
SELECT
    na.organization_id,
    na.node_id,
    na.parent_node_id
FROM hierarchy_bitemporal_model_v2.node_assignments na

CROSS JOIN benchmark_parameters bp

WHERE na.organization_id =
      bp.organization_id

  AND na.valid_from <=
      bp.at_time

  AND (
      na.valid_to IS NULL
      OR bp.at_time < na.valid_to
  );


/*
===============================================================================
12. TEST 2 — ANCESTORS AT T
===============================================================================
*/

EXPLAIN (ANALYZE, BUFFERS, TIMING)
SELECT *
FROM hierarchy_bitemporal_model_v2.get_ancestors_at_t(
    (
        SELECT organization_id
        FROM benchmark_parameters
    ),
    (
        SELECT target_node_id
        FROM benchmark_parameters
    ),
    (
        SELECT at_time
        FROM benchmark_parameters
    )
);


/*
===============================================================================
13. TEST 3 — DESCENDANTS AT T
===============================================================================
*/

EXPLAIN (ANALYZE, BUFFERS, TIMING)
SELECT *
FROM hierarchy_bitemporal_model_v2.get_descendants_at_t(
    (
        SELECT organization_id
        FROM benchmark_parameters
    ),
    (
        SELECT level3_node_id
        FROM benchmark_parameters
    ),
    (
        SELECT at_time
        FROM benchmark_parameters
    )
);


/*
===============================================================================
14. TEST 4 — SUBTREE MEMBERSHIP AT T
===============================================================================
*/

EXPLAIN (ANALYZE, BUFFERS, TIMING)
SELECT hierarchy_bitemporal_model_v2.is_in_subtree_at_t(
    (
        SELECT organization_id
        FROM benchmark_parameters
    ),
    (
        SELECT level3_node_id
        FROM benchmark_parameters
    ),
    (
        SELECT target_node_id
        FROM benchmark_parameters
    ),
    (
        SELECT at_time
        FROM benchmark_parameters
    )
);


/*
===============================================================================
15. REPEATED PERFORMANCE TEST
===============================================================================

Run each operation 1,000 times.

The results are stored in a temporary table.

This allows us to calculate:

    p50
    p95
    p99
===============================================================================
*/

DROP TABLE IF EXISTS pg_temp.benchmark_results;

CREATE TEMP TABLE benchmark_results
(
    test_name    TEXT NOT NULL,
    execution_ms DOUBLE PRECISION NOT NULL
);


/*
===============================================================================
16. PARENT LOOKUP — 1,000 EXECUTIONS
===============================================================================
*/

DO $$
DECLARE
    i          INTEGER;
    started_at TIMESTAMPTZ;
    finished_at TIMESTAMPTZ;
BEGIN

    FOR i IN 1..1000 LOOP

        started_at := clock_timestamp();

        PERFORM
            na.parent_node_id

        FROM hierarchy_bitemporal_model_v2.node_assignments na

        CROSS JOIN benchmark_parameters bp

        WHERE na.organization_id =
              bp.organization_id

          AND na.node_id =
              bp.target_node_id

          AND na.valid_from <=
              bp.at_time

          AND (
              na.valid_to IS NULL
              OR bp.at_time < na.valid_to
          );

        finished_at := clock_timestamp();

        INSERT INTO benchmark_results
        VALUES
        (
            'parent_lookup_at_t',

            EXTRACT(
                EPOCH
                FROM (finished_at - started_at)
            ) * 1000
        );

    END LOOP;

END $$;


/*
===============================================================================
17. ANCESTOR QUERY — 1,000 EXECUTIONS
===============================================================================
*/

DO $$
DECLARE
    i          INTEGER;
    started_at TIMESTAMPTZ;
    finished_at TIMESTAMPTZ;
BEGIN

    FOR i IN 1..1000 LOOP

        started_at := clock_timestamp();

        PERFORM *
        FROM hierarchy_bitemporal_model_v2.get_ancestors_at_t(
            (
                SELECT organization_id
                FROM benchmark_parameters
            ),
            (
                SELECT target_node_id
                FROM benchmark_parameters
            ),
            (
                SELECT at_time
                FROM benchmark_parameters
            )
        );

        finished_at := clock_timestamp();

        INSERT INTO benchmark_results
        VALUES
        (
            'ancestors_at_t',

            EXTRACT(
                EPOCH
                FROM (finished_at - started_at)
            ) * 1000
        );

    END LOOP;

END $$;


/*
===============================================================================
18. DESCENDANT QUERY — 1,000 EXECUTIONS
===============================================================================
*/

DO $$
DECLARE
    i          INTEGER;
    started_at TIMESTAMPTZ;
    finished_at TIMESTAMPTZ;
BEGIN

    FOR i IN 1..1000 LOOP

        started_at := clock_timestamp();

        PERFORM *
        FROM hierarchy_bitemporal_model_v2.get_descendants_at_t(
            (
                SELECT organization_id
                FROM benchmark_parameters
            ),
            (
                SELECT level3_node_id
                FROM benchmark_parameters
            ),
            (
                SELECT at_time
                FROM benchmark_parameters
            )
        );

        finished_at := clock_timestamp();

        INSERT INTO benchmark_results
        VALUES
        (
            'descendants_at_t',

            EXTRACT(
                EPOCH
                FROM (finished_at - started_at)
            ) * 1000
        );

    END LOOP;

END $$;


/*
===============================================================================
19. SUBTREE MEMBERSHIP — 1,000 EXECUTIONS
===============================================================================
*/

DO $$
DECLARE
    i          INTEGER;
    started_at TIMESTAMPTZ;
    finished_at TIMESTAMPTZ;
    result     BOOLEAN;
BEGIN

    FOR i IN 1..1000 LOOP

        started_at := clock_timestamp();

        SELECT hierarchy_bitemporal_model_v2.is_in_subtree_at_t(
            (
                SELECT organization_id
                FROM benchmark_parameters
            ),
            (
                SELECT level3_node_id
                FROM benchmark_parameters
            ),
            (
                SELECT target_node_id
                FROM benchmark_parameters
            ),
            (
                SELECT at_time
                FROM benchmark_parameters
            )
        )
        INTO result;

        finished_at := clock_timestamp();

        INSERT INTO benchmark_results
        VALUES
        (
            'subtree_membership_at_t',

            EXTRACT(
                EPOCH
                FROM (finished_at - started_at)
            ) * 1000
        );

    END LOOP;

END $$;


/*
===============================================================================
20. PERFORMANCE SUMMARY
===============================================================================

P50  = percentile_cont(0.50)
P95  = percentile_cont(0.95)
P99  = percentile_cont(0.99)
===============================================================================
*/

SELECT
    test_name,

    COUNT(*) AS executions,

    ROUND(
        (
            percentile_cont(0.50)
            WITHIN GROUP (ORDER BY execution_ms)
        )::numeric,
        3
    ) AS p50_ms,

    ROUND(
        (
            percentile_cont(0.95)
            WITHIN GROUP (ORDER BY execution_ms)
        )::numeric,
        3
    ) AS p95_ms,

    ROUND(
        (
            percentile_cont(0.99)
            WITHIN GROUP (ORDER BY execution_ms)
        )::numeric,
        3
    ) AS p99_ms,

    ROUND(
        AVG(execution_ms)::numeric,
        3
    ) AS avg_ms,

    ROUND(
        MIN(execution_ms)::numeric,
        3
    ) AS min_ms,

    ROUND(
        MAX(execution_ms)::numeric,
        3
    ) AS max_ms

FROM benchmark_results

GROUP BY test_name

ORDER BY test_name;


/*
===============================================================================
21. AUTHORIZATION ACCEPTANCE TEST
===============================================================================

For the authorization-related subtree membership operation:

    p95 <= 10 ms

This reports PASS/FAIL based on the measured result.

NOTE:
    This is a database-query benchmark.

    If the application authorization decision includes additional work
    outside PostgreSQL, that application-layer latency must be measured
    separately.
===============================================================================
*/

SELECT
    test_name,

    ROUND(
        (
            percentile_cont(0.95)
            WITHIN GROUP (ORDER BY execution_ms)
        )::numeric,
        3
    ) AS p95_ms,

    CASE
        WHEN percentile_cont(0.95)
             WITHIN GROUP (ORDER BY execution_ms) <= 10
        THEN 'PASS'
        ELSE 'FAIL'
    END AS acceptance_status

FROM benchmark_results

WHERE test_name =
      'subtree_membership_at_t'

GROUP BY test_name;


/*
===============================================================================
22. ROLLBACK BENCHMARK DATA
===============================================================================

IMPORTANT:

The benchmark is intentionally rolled back.

This removes:

    - 200,000 benchmark nodes
    - 199,999 benchmark assignments

Production data remains unchanged.

===============================================================================
*/

ROLLBACK;


/*
===============================================================================
END
===============================================================================
*/