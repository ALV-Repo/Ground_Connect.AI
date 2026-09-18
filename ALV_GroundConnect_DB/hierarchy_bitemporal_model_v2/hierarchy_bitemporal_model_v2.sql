/* ============================================================
   hierarchy_bitemporal_model_v2.sql
   Hierarchy Nodes + Bitemporal Parent Assignments
   ============================================================ */

CREATE SCHEMA IF NOT EXISTS hierarchy_bitemporal_model_v2;

CREATE EXTENSION IF NOT EXISTS btree_gist;


/* ============================================================
   1. NODES
   ============================================================ */

CREATE TABLE hierarchy_bitemporal_model_v2.nodes
(
    id UUID NOT NULL,

    organization_id UUID NOT NULL,

    level_id UUID NOT NULL,

    code VARCHAR(100) NOT NULL,

    name VARCHAR(200) NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT nodes_pk
        PRIMARY KEY (id),

    /*
     * Required for organization-scoped composite foreign keys.
     */
    CONSTRAINT nodes_organization_id_id_uk
        UNIQUE (organization_id, id),

    /*
     * Node code must be unique within an organization.
     */
    CONSTRAINT nodes_organization_code_uk
        UNIQUE (organization_id, code),

    CONSTRAINT nodes_name_chk
        CHECK (length(trim(name)) > 0),

    CONSTRAINT nodes_status_chk
        CHECK (status IN ('ACTIVE', 'INACTIVE'))
);


/* ============================================================
   2. NODE ASSIGNMENTS
   ============================================================ */

CREATE TABLE hierarchy_bitemporal_model_v2.node_assignments
(
    id UUID NOT NULL,

    organization_id UUID NOT NULL,
    
     -- * Child node.
     
    node_id UUID NOT NULL,

     -- * Parent node.

    parent_node_id UUID NOT NULL,

     -- * Business validity period.

    valid_from TIMESTAMPTZ NOT NULL,

    valid_to TIMESTAMPTZ,

     -- * Audit / recording information.

    recorded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    recorded_by UUID NOT NULL,

    CONSTRAINT node_assignments_pk
        PRIMARY KEY (id),


     -- * Validity interval must be valid.
     -- * NULL valid_to means open-ended/current.

    CONSTRAINT node_assignments_validity_chk
        CHECK
        (
            valid_to IS NULL
            OR valid_to > valid_from
        ),


     -- * A node cannot be its own parent.

    CONSTRAINT node_assignments_no_self_parent_chk
        CHECK
        (
            node_id <> parent_node_id
        ),
 
     -- * Child must belong to the same organization.
 
    CONSTRAINT node_assignments_node_fk
        FOREIGN KEY
        (
            organization_id,
            node_id
        )
        REFERENCES hierarchy_bitemporal_model_v2.nodes
        (
            organization_id,
            id
        ),

     -- * Parent must belong to the same organization.

    CONSTRAINT node_assignments_parent_node_fk
        FOREIGN KEY
        (
            organization_id,
            parent_node_id
        )
        REFERENCES hierarchy_bitemporal_model_v2.nodes
        (
            organization_id,
            id
        )
);


/* ============================================================
   3. SINGLE PARENT PER VALIDITY INTERVAL
   ============================================================

   Prevents a child node from having two different parents
   during overlapping validity intervals.

   Example REJECTED:

       B -> A   [2026-01-01, 2026-06-01)
       B -> C   [2026-03-01, 2026-09-01)

   Example ALLOWED:

       B -> A   [2026-01-01, 2026-04-01)
       B -> C   [2026-04-01, 2026-09-01)

   '[)' means:
       valid_from = inclusive
       valid_to   = exclusive
   ============================================================ */

ALTER TABLE hierarchy_bitemporal_model_v2.node_assignments

ADD CONSTRAINT node_assignments_single_parent_per_validity

EXCLUDE USING GIST
(
    organization_id WITH =,
    node_id         WITH =,
    tstzrange(
        valid_from,
        valid_to,
        '[)'
    ) WITH &&
);


/* ============================================================
   4. CYCLE PREVENTION FUNCTION
   ============================================================

   Prevents hierarchy cycles such as:

       A -> B
       B -> C
       C -> A

   Cycle detection is performed at DATABASE level.
   ============================================================ */

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.prevent_hierarchy_cycle()
RETURNS TRIGGER
LANGUAGE plpgsql
AS
$$
DECLARE
    cycle_found BOOLEAN;
BEGIN

    /*
     * Starting from the proposed parent, walk upward through
     * the existing hierarchy.
     *
     * If the proposed child is reached, a cycle exists.
     */
    WITH RECURSIVE hierarchy_path AS
    (
        /*
         * First relationship:
         *
         * NEW.node_id -> NEW.parent_node_id
         */
        SELECT
            NEW.parent_node_id AS current_node_id,

            NEW.valid_from AS path_valid_from,

            NEW.valid_to AS path_valid_to,

            ARRAY[
                NEW.node_id,
                NEW.parent_node_id
            ]::UUID[] AS path

        UNION ALL

        /*
         * Continue walking:
         *
         * current parent -> its parent
         */
        SELECT
            na.parent_node_id,

            GREATEST(
                hp.path_valid_from,
                na.valid_from
            ),

            CASE
                WHEN hp.path_valid_to IS NULL
                    THEN na.valid_to

                WHEN na.valid_to IS NULL
                    THEN hp.path_valid_to

                ELSE LEAST(
                    hp.path_valid_to,
                    na.valid_to
                )
            END,

            hp.path || na.parent_node_id

        FROM hierarchy_path hp

        JOIN hierarchy_bitemporal_model_v2.node_assignments na
          ON na.organization_id = NEW.organization_id
         AND na.node_id = hp.current_node_id

        /*
         * Only traverse relationships whose validity period
         * overlaps with the validity period being checked.
         */
        WHERE tstzrange(
                  hp.path_valid_from,
                  hp.path_valid_to,
                  '[)'
              )
              &&
              tstzrange(
                  na.valid_from,
                  na.valid_to,
                  '[)'
              )

        /*
         * Prevent recursive traversal from repeatedly
         * following a node already visited in this path.
         */
        AND NOT na.parent_node_id = ANY(hp.path)
    )

    SELECT EXISTS
    (
        SELECT 1
        FROM hierarchy_path
        WHERE current_node_id = NEW.node_id
    )
    INTO cycle_found;


    IF cycle_found THEN

        RAISE EXCEPTION
            'Hierarchy cycle detected: node % cannot be assigned under parent % for the specified validity interval',
            NEW.node_id,
            NEW.parent_node_id
            USING ERRCODE = '23514';

    END IF;


    RETURN NEW;

END;
$$;


/* ============================================================
   5. DATABASE-LEVEL CYCLE PREVENTION TRIGGER
   ============================================================ */

CREATE CONSTRAINT TRIGGER trg_prevent_hierarchy_cycle

AFTER INSERT OR UPDATE OF
    organization_id,
    node_id,
    parent_node_id,
    valid_from,
    valid_to

ON hierarchy_bitemporal_model_v2.node_assignments

DEFERRABLE INITIALLY DEFERRED

FOR EACH ROW

EXECUTE FUNCTION
hierarchy_bitemporal_model_v2.prevent_hierarchy_cycle();


/* ============================================================
   END
   ============================================================ */