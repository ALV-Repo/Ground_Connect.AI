/*
===============================================================================
FILE: point_in_time_queries_and_indexes.sql

PURPOSE
-------
Efficient point-in-time hierarchy queries for:

1. Structure at instant T
2. Ancestors at instant T
3. Descendants at instant T
4. Responsible person at instant T
5. Subtree membership at instant T

PERFORMANCE REQUIREMENT
-----------------------
Authorization decision target:
    <= 10 ms p95
    at 200,000 nodes

IMPORTANT
---------
- Actual column name is organization_id, not org_id.
- valid_from is inclusive.
- valid_to is exclusive.
- NULL valid_to means the assignment is currently open-ended.
- recorded_at is audit/recording time and is NOT used for point-in-time
  hierarchy validity.
- recorded_by is the audit actor and is NOT the responsible person.
- Responsible-person data is reused from the existing
  hierarchy_bitemporal_model.node_assignments table.
- No new responsibility table is created here.
- The 10 ms p95 requirement MUST be verified with a representative
  200,000-node benchmark; indexes alone do not guarantee it.

SOURCE SCHEMA
-------------
hierarchy_bitemporal_model_v2
===============================================================================
*/


/*
===============================================================================
1. REQUIRED INDEX — CHILD/NODE DIRECTION
===============================================================================

Used by:

    Structure at T
    Ancestors at T
    Point-in-time node lookup

Access pattern:

    organization_id
    + node_id
    + validity interval
===============================================================================
*/

CREATE INDEX IF NOT EXISTS idx_na_org_node_validity
ON hierarchy_bitemporal_model_v2.node_assignments
(
    organization_id,
    node_id,
    valid_from,
    valid_to
);


/*
===============================================================================
2. REQUIRED INDEX — PARENT/CHILDREN DIRECTION
===============================================================================

Used by:

    Descendants at T
    Subtree membership at T

Access pattern:

    organization_id
    + parent_node_id
    + validity interval
===============================================================================
*/

CREATE INDEX IF NOT EXISTS idx_na_org_parent_validity
ON hierarchy_bitemporal_model_v2.node_assignments
(
    organization_id,
    parent_node_id,
    valid_from,
    valid_to
);


/*
===============================================================================
3. STRUCTURE AT INSTANT T
===============================================================================

Returns all parent-child relationships that were valid at :at_time.

Validity semantics:

    valid_from <= :at_time
    AND
    (
        valid_to IS NULL
        OR :at_time < valid_to
    )

This implements [valid_from, valid_to).
===============================================================================
*/

CREATE OR REPLACE VIEW hierarchy_bitemporal_model_v2.v_structure_at_t
AS
SELECT
    na.organization_id,
    na.node_id,
    child.name AS node_name,
    na.parent_node_id,
    parent.name AS parent_name,
    na.valid_from,
    na.valid_to
FROM hierarchy_bitemporal_model_v2.node_assignments na

JOIN hierarchy_bitemporal_model_v2.nodes child
  ON child.organization_id = na.organization_id
 AND child.id = na.node_id

JOIN hierarchy_bitemporal_model_v2.nodes parent
  ON parent.organization_id = na.organization_id
 AND parent.id = na.parent_node_id;


/*
NOTE
----
A normal PostgreSQL VIEW cannot receive :at_time as a parameter.

Therefore the reusable view exposes the hierarchy assignment data,
while callers apply the point-in-time predicate:

    SELECT *
    FROM hierarchy_bitemporal_model_v2.v_structure_at_t
    WHERE organization_id = :organization_id
      AND valid_from <= :at_time
      AND (
          valid_to IS NULL
          OR :at_time < valid_to
      );
*/


/*
===============================================================================
4. ANCESTORS AT INSTANT T
===============================================================================

Returns the ancestor chain for a node at a specific point in time.

Traversal:

    node
      ↓
    parent
      ↓
    grandparent
      ↓
    ...
      ↓
    root
===============================================================================
*/

CREATE OR REPLACE FUNCTION hierarchy_bitemporal_model_v2.get_ancestors_at_t
(
    p_organization_id UUID,
    p_node_id         UUID,
    p_at_time         TIMESTAMPTZ
)
RETURNS TABLE
(
    organization_id UUID,
    node_id         UUID,
    node_name       VARCHAR(200),
    depth           INTEGER
)
LANGUAGE sql
STABLE
AS $$
    WITH RECURSIVE ancestors AS
    (
        /*
        Starting node
        */
        SELECT
            n.organization_id,
            n.id AS node_id,
            n.name AS node_name,
            0 AS depth
        FROM hierarchy_bitemporal_model_v2.nodes n
        WHERE n.organization_id = p_organization_id
          AND n.id = p_node_id

        UNION ALL

        /*
        Move from child to parent
        */
        SELECT
            na.organization_id,
            parent.id AS node_id,
            parent.name AS node_name,
            a.depth + 1
        FROM ancestors a

        JOIN hierarchy_bitemporal_model_v2.node_assignments na
          ON na.organization_id = a.organization_id
         AND na.node_id = a.node_id

        JOIN hierarchy_bitemporal_model_v2.nodes parent
          ON parent.organization_id = na.organization_id
         AND parent.id = na.parent_node_id

        WHERE na.valid_from <= p_at_time
          AND (
              na.valid_to IS NULL
              OR p_at_time < na.valid_to
          )
    )

    SELECT
        organization_id,
        node_id,
        node_name,
        depth
    FROM ancestors
    WHERE depth > 0
    ORDER BY depth;
$$;


/*
===============================================================================
5. DESCENDANTS AT INSTANT T
===============================================================================

Returns the complete subtree rooted at p_root_node_id at p_at_time.

Traversal:

    root
      ↓
    children
      ↓
    grandchildren
      ↓
    ...
===============================================================================
*/

CREATE OR REPLACE FUNCTION hierarchy_bitemporal_model_v2.get_descendants_at_t
(
    p_organization_id UUID,
    p_root_node_id    UUID,
    p_at_time         TIMESTAMPTZ
)
RETURNS TABLE
(
    organization_id UUID,
    node_id         UUID,
    node_name       VARCHAR(200),
    depth           INTEGER
)
LANGUAGE sql
STABLE
AS $$
    WITH RECURSIVE descendants AS
    (
        /*
        Starting/root node
        */
        SELECT
            n.organization_id,
            n.id AS node_id,
            n.name AS node_name,
            0 AS depth
        FROM hierarchy_bitemporal_model_v2.nodes n
        WHERE n.organization_id = p_organization_id
          AND n.id = p_root_node_id

        UNION ALL

        /*
        Find children
        */
        SELECT
            na.organization_id,
            child.id AS node_id,
            child.name AS node_name,
            d.depth + 1
        FROM descendants d

        JOIN hierarchy_bitemporal_model_v2.node_assignments na
          ON na.organization_id = d.organization_id
         AND na.parent_node_id = d.node_id

        JOIN hierarchy_bitemporal_model_v2.nodes child
          ON child.organization_id = na.organization_id
         AND child.id = na.node_id

        WHERE na.valid_from <= p_at_time
          AND (
              na.valid_to IS NULL
              OR p_at_time < na.valid_to
          )
    )

    SELECT
        organization_id,
        node_id,
        node_name,
        depth
    FROM descendants
    ORDER BY depth, node_id;
$$;


/*
===============================================================================
6. SUBTREE MEMBERSHIP AT INSTANT T
===============================================================================

Returns TRUE when p_target_node_id belongs to the subtree rooted at
p_root_node_id at p_at_time.

This is the key query for hierarchy-based authorization.
===============================================================================
*/

CREATE OR REPLACE FUNCTION hierarchy_bitemporal_model_v2.is_in_subtree_at_t
(
    p_organization_id UUID,
    p_root_node_id    UUID,
    p_target_node_id  UUID,
    p_at_time         TIMESTAMPTZ
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    WITH RECURSIVE subtree AS
    (
        /*
        Root node
        */
        SELECT
            n.organization_id,
            n.id AS node_id
        FROM hierarchy_bitemporal_model_v2.nodes n
        WHERE n.organization_id = p_organization_id
          AND n.id = p_root_node_id

        UNION ALL

        /*
        Traverse to children
        */
        SELECT
            na.organization_id,
            na.node_id
        FROM subtree s

        JOIN hierarchy_bitemporal_model_v2.node_assignments na
          ON na.organization_id = s.organization_id
         AND na.parent_node_id = s.node_id

        WHERE na.valid_from <= p_at_time
          AND (
              na.valid_to IS NULL
              OR p_at_time < na.valid_to
          )
    )

    SELECT EXISTS
    (
        SELECT 1
        FROM subtree
        WHERE node_id = p_target_node_id
    );
$$;


/*
===============================================================================
7. RESPONSIBLE PERSON AT INSTANT T
===============================================================================

IMPORTANT
---------
Responsible-person assignments already exist in:

    hierarchy_bitemporal_model.node_assignments

Do NOT use:

    hierarchy_bitemporal_model_v2.node_assignments.recorded_by

recorded_by is audit information.

The responsible user is identified by:

    user_id
    is_responsible_person = TRUE

The user record is in:

    identity_authentication_sessions.users
===============================================================================
*/

CREATE OR REPLACE FUNCTION hierarchy_bitemporal_model_v2.get_responsible_person_at_t
(
    p_organization_id UUID,
    p_node_id         UUID,
    p_at_time         TIMESTAMPTZ
)
RETURNS TABLE
(
    organization_id UUID,
    node_id         UUID,
    user_id         UUID,
    role            TEXT,
    valid_from      TIMESTAMPTZ,
    valid_to        TIMESTAMPTZ
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        na.organization_id,
        na.node_id,
        na.user_id,
        na.role,
        na.valid_from,
        na.valid_to
    FROM hierarchy_bitemporal_model.node_assignments na

    /*
    Confirm that the user exists.
    We intentionally do not return encrypted personal fields.
    */
    JOIN identity_authentication_sessions.users u
      ON u.id = na.user_id

    WHERE na.organization_id = p_organization_id
      AND na.node_id = p_node_id
      AND na.is_responsible_person = TRUE
      AND na.valid_from <= p_at_time
      AND (
          na.valid_to IS NULL
          OR p_at_time < na.valid_to
      );
$$;


/*
===============================================================================
8. PERFORMANCE STATISTICS
===============================================================================

Refresh optimizer statistics after deployment or significant data changes.
===============================================================================
*/

ANALYZE hierarchy_bitemporal_model_v2.nodes;

ANALYZE hierarchy_bitemporal_model_v2.node_assignments;

ANALYZE hierarchy_bitemporal_model.node_assignments;

ANALYZE identity_authentication_sessions.users;


/*
===============================================================================
9. INDEX VERIFICATION
===============================================================================
*/

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'hierarchy_bitemporal_model_v2'
  AND tablename = 'node_assignments'
ORDER BY indexname;


/*
===============================================================================
10. EXAMPLE — STRUCTURE AT T
===============================================================================

Replace the UUID and timestamp with application parameters.
===============================================================================
*/

-- SELECT *
-- FROM hierarchy_bitemporal_model_v2.v_structure_at_t
-- WHERE organization_id = :organization_id
--   AND valid_from <= :at_time
--   AND (
--       valid_to IS NULL
--       OR :at_time < valid_to
--   );


/*
===============================================================================
11. EXAMPLE — ANCESTORS AT T
===============================================================================

SELECT *
FROM hierarchy_bitemporal_model_v2.get_ancestors_at_t(
    :organization_id,
    :node_id,
    :at_time
);


===============================================================================
12. EXAMPLE — DESCENDANTS AT T
===============================================================================

SELECT *
FROM hierarchy_bitemporal_model_v2.get_descendants_at_t(
    :organization_id,
    :root_node_id,
    :at_time
);


===============================================================================
13. EXAMPLE — SUBTREE MEMBERSHIP AT T
===============================================================================

SELECT hierarchy_bitemporal_model_v2.is_in_subtree_at_t(
    :organization_id,
    :root_node_id,
    :target_node_id,
    :at_time
);


===============================================================================
14. EXAMPLE — RESPONSIBLE PERSON AT T
===============================================================================

SELECT *
FROM hierarchy_bitemporal_model_v2.get_responsible_person_at_t(
    :organization_id,
    :node_id,
    :at_time
);


===============================================================================
15. PERFORMANCE VALIDATION
===============================================================================

The following tests MUST be performed against a representative
200,000-node dataset.

Do NOT consider the 10 ms p95 requirement satisfied merely because
the indexes exist.

Recommended:

    EXPLAIN (ANALYZE, BUFFERS)

for:

    - structure at T
    - ancestors at T
    - descendants at T
    - subtree membership at T
    - responsible person at T

The final authorization benchmark should use repeated executions and
calculate:

    p50
    p95
    p99

The acceptance target is:

    authorization decision p95 <= 10 ms

at approximately:

    200,000 nodes

with representative hierarchy depth, branching factor, and subtree sizes.
===============================================================================
*/