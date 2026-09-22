/*
===============================================================================
FILE
----
09_10_backdated_future_dated_assignment_support.sql

REQUIREMENTS
------------
HIER-09
Support valid_from in the past or future while the assignment is recorded
today, without rewriting or deleting prior assignment history.

HIER-10
Permanently attribute an action to the assignment that was valid when the
action occurred, so later hierarchy transfers do not change that attribution.

DEPENDENCIES
------------
Existing objects:

    hierarchy_bitemporal_model_v2.nodes
    hierarchy_bitemporal_model_v2.node_assignments

The existing point-in-time file remains responsible for:

    - ancestors at T
    - descendants at T
    - subtree membership at T
    - responsible person at T

This file does NOT recreate those objects.

IMPORTANT
---------
The node_assignments table remains the source of hierarchy validity.

An action's historical attribution is permanently captured by storing the
assignment_id that was valid at action time in the attribution table.

Later transfers create/close assignment intervals but do not modify the
captured assignment_id in an attribution record.

===============================================================================
*/


/*
===============================================================================
1. DEPENDENCY VALIDATION
===============================================================================
*/

DO
$$
BEGIN

    IF to_regclass(
        'hierarchy_bitemporal_model_v2.nodes'
    ) IS NULL THEN
        RAISE EXCEPTION
            'Required table hierarchy_bitemporal_model_v2.nodes does not exist';
    END IF;

    IF to_regclass(
        'hierarchy_bitemporal_model_v2.node_assignments'
    ) IS NULL THEN
        RAISE EXCEPTION
            'Required table hierarchy_bitemporal_model_v2.node_assignments does not exist';
    END IF;

END
$$;


/*
===============================================================================
2. BACKDATED ASSIGNMENT VALIDATION VIEW
===============================================================================

A backdated assignment is recorded at one time but becomes valid earlier.

Example:

    recorded_at = 2026-09-22
    valid_from  = 2026-08-01

No historical row needs to be rewritten to represent this.
===============================================================================
*/

CREATE OR REPLACE VIEW
hierarchy_bitemporal_model_v2.v_backdated_assignments
AS
SELECT
    na.id AS assignment_id,
    na.organization_id,
    na.node_id,
    na.parent_node_id,
    na.valid_from,
    na.valid_to,
    na.recorded_at,
    na.recorded_by
FROM hierarchy_bitemporal_model_v2.node_assignments AS na
WHERE na.valid_from < na.recorded_at;


/*
===============================================================================
3. FUTURE-DATED ASSIGNMENT VALIDATION VIEW
===============================================================================

A future-dated assignment is recorded now but becomes valid later.

Example:

    recorded_at = 2026-09-22
    valid_from  = 2026-10-01
===============================================================================
*/

CREATE OR REPLACE VIEW
hierarchy_bitemporal_model_v2.v_future_dated_assignments
AS
SELECT
    na.id AS assignment_id,
    na.organization_id,
    na.node_id,
    na.parent_node_id,
    na.valid_from,
    na.valid_to,
    na.recorded_at,
    na.recorded_by
FROM hierarchy_bitemporal_model_v2.node_assignments AS na
WHERE na.valid_from > na.recorded_at;


/*
===============================================================================
4. PERMANENT ACTION-TO-ASSIGNMENT ATTRIBUTION
===============================================================================

This table stores the assignment that was valid when an action occurred.

The assignment_id is captured permanently.

Later hierarchy transfers do not change this value.

action_id
---------
Identifier of the business action/event.

organization_id
---------------
Organization containing the action.

node_id
-------
Node on which/under which the action occurred.

assignment_id
-------------
The exact node_assignments record that was valid at action_at.

action_at
---------
Timestamp when the business action occurred.

attributed_at
-------------
Timestamp when the historical attribution was recorded.

attributed_by
-------------
Actor/process that recorded the attribution.

The table deliberately does NOT contain valid_from/valid_to copied as
independent mutable values. The assignment_id is the immutable historical
reference.
===============================================================================
*/

CREATE TABLE IF NOT EXISTS
hierarchy_bitemporal_model_v2.action_assignment_attributions
(
    action_id UUID NOT NULL,

    organization_id UUID NOT NULL,

    node_id UUID NOT NULL,

    assignment_id UUID NOT NULL,

    action_at TIMESTAMPTZ NOT NULL,

    attributed_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    attributed_by UUID NOT NULL,

    CONSTRAINT action_assignment_attributions_pk
        PRIMARY KEY (action_id),

    CONSTRAINT action_assignment_attributions_node_fk
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

    CONSTRAINT action_assignment_attributions_assignment_fk
        FOREIGN KEY
        (
            assignment_id
        )
        REFERENCES hierarchy_bitemporal_model_v2.node_assignments
        (
            id
        )
);


/*
===============================================================================
5. INDEX FOR HISTORICAL ATTRIBUTION LOOKUP
===============================================================================
*/

CREATE INDEX IF NOT EXISTS
idx_aaa_org_node_action_at
ON hierarchy_bitemporal_model_v2.action_assignment_attributions
(
    organization_id,
    node_id,
    action_at
);


/*
===============================================================================
6. VERIFY THAT THE ASSIGNMENT BELONGS TO THE SAME ORGANIZATION/NODE
===============================================================================

The FK above protects assignment_id existence.

This trigger additionally guarantees that the captured assignment belongs to
the organization and node supplied for the action.
===============================================================================
*/

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.validate_action_assignment_attribution()
RETURNS TRIGGER
LANGUAGE plpgsql
AS
$$
DECLARE
    v_assignment_org UUID;
    v_assignment_node UUID;
BEGIN

    SELECT
        na.organization_id,
        na.node_id
    INTO
        v_assignment_org,
        v_assignment_node
    FROM hierarchy_bitemporal_model_v2.node_assignments AS na
    WHERE na.id = NEW.assignment_id;

    IF v_assignment_org IS NULL THEN
        RAISE EXCEPTION
            'Assignment % does not exist',
            NEW.assignment_id;
    END IF;

    IF v_assignment_org <> NEW.organization_id
       OR v_assignment_node <> NEW.node_id THEN

        RAISE EXCEPTION
            'Assignment % does not belong to organization % and node %',
            NEW.assignment_id,
            NEW.organization_id,
            NEW.node_id;

    END IF;

    /*
     * The assignment must have been valid when the action occurred.
     */
    IF NOT EXISTS
    (
        SELECT 1
        FROM hierarchy_bitemporal_model_v2.node_assignments AS na
        WHERE na.id = NEW.assignment_id
          AND na.valid_from <= NEW.action_at
          AND
          (
              na.valid_to IS NULL
              OR NEW.action_at < na.valid_to
          )
    ) THEN

        RAISE EXCEPTION
            'Assignment % was not valid at action time %',
            NEW.assignment_id,
            NEW.action_at;

    END IF;

    RETURN NEW;

END;
$$;


DROP TRIGGER IF EXISTS
trg_validate_action_assignment_attribution
ON hierarchy_bitemporal_model_v2.action_assignment_attributions;


CREATE TRIGGER
trg_validate_action_assignment_attribution
BEFORE INSERT
ON hierarchy_bitemporal_model_v2.action_assignment_attributions
FOR EACH ROW
EXECUTE FUNCTION
hierarchy_bitemporal_model_v2.validate_action_assignment_attribution();


/*
===============================================================================
7. PERMANENT / IMMUTABLE ATTRIBUTION PROTECTION
===============================================================================

Once an action has been attributed to an assignment, the attribution must
not be changed by a later hierarchy transfer.

The safest application model is INSERT-only.

This trigger rejects UPDATE and DELETE attempts through normal SQL DML.
===============================================================================
*/

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.prevent_action_assignment_attribution_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS
$$
BEGIN

    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION
            'Historical action attribution cannot be updated';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'Historical action attribution cannot be deleted';
    END IF;

    RETURN NULL;

END;
$$;


DROP TRIGGER IF EXISTS
trg_prevent_action_assignment_attribution_change
ON hierarchy_bitemporal_model_v2.action_assignment_attributions;


CREATE TRIGGER
trg_prevent_action_assignment_attribution_change
BEFORE UPDATE OR DELETE
ON hierarchy_bitemporal_model_v2.action_assignment_attributions
FOR EACH ROW
EXECUTE FUNCTION
hierarchy_bitemporal_model_v2.prevent_action_assignment_attribution_change();


/*
===============================================================================
8. RECORD HISTORICAL ACTION ATTRIBUTION
===============================================================================

Call this function when the business action is created.

The function:

    1. Finds the assignment valid at action_at.
    2. Stores its assignment_id permanently.
    3. Does not copy the current/latest assignment.
    4. Rejects the action if no assignment was valid at action_at.

Example:

    SELECT hierarchy_bitemporal_model_v2.record_action_assignment_attribution(
        :action_id,
        :organization_id,
        :node_id,
        :action_at,
        :attributed_by
    );

The function returns the captured assignment_id.
===============================================================================
*/

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.record_action_assignment_attribution
(
    p_action_id      UUID,
    p_organization_id UUID,
    p_node_id         UUID,
    p_action_at       TIMESTAMPTZ,
    p_attributed_by   UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS
$$
DECLARE
    v_assignment_id UUID;
BEGIN

    SELECT na.id
    INTO v_assignment_id
    FROM hierarchy_bitemporal_model_v2.node_assignments AS na
    WHERE na.organization_id = p_organization_id
      AND na.node_id = p_node_id
      AND na.valid_from <= p_action_at
      AND
      (
          na.valid_to IS NULL
          OR p_action_at < na.valid_to
      )
    ORDER BY na.valid_from DESC
    LIMIT 1;

    IF v_assignment_id IS NULL THEN
        RAISE EXCEPTION
            'No assignment was valid for organization %, node %, at action time %',
            p_organization_id,
            p_node_id,
            p_action_at;
    END IF;

    INSERT INTO
    hierarchy_bitemporal_model_v2.action_assignment_attributions
    (
        action_id,
        organization_id,
        node_id,
        assignment_id,
        action_at,
        attributed_at,
        attributed_by
    )
    VALUES
    (
        p_action_id,
        p_organization_id,
        p_node_id,
        v_assignment_id,
        p_action_at,
        CURRENT_TIMESTAMP,
        p_attributed_by
    );

    RETURN v_assignment_id;

END;
$$;


/*
===============================================================================
9. HISTORICAL ATTRIBUTION LOOKUP
===============================================================================

Returns the permanently captured assignment for an action.

This query does NOT recalculate attribution from the current hierarchy.

Therefore later transfers do not change the result.
===============================================================================
*/

CREATE OR REPLACE VIEW
hierarchy_bitemporal_model_v2.v_action_assignment_attributions
AS
SELECT
    aaa.action_id,
    aaa.organization_id,
    aaa.node_id,
    aaa.assignment_id,
    aaa.action_at,
    aaa.attributed_at,
    aaa.attributed_by,

    na.parent_node_id,
    na.valid_from AS assignment_valid_from,
    na.valid_to   AS assignment_valid_to,
    na.recorded_at AS assignment_recorded_at,
    na.recorded_by AS assignment_recorded_by

FROM hierarchy_bitemporal_model_v2.action_assignment_attributions AS aaa

JOIN hierarchy_bitemporal_model_v2.node_assignments AS na
  ON na.id = aaa.assignment_id;


/*
===============================================================================
10. VALIDATION QUERIES
===============================================================================
*/


/*
Backdated assignments
---------------------
*/
-- SELECT *
-- FROM hierarchy_bitemporal_model_v2.v_backdated_assignments
-- ORDER BY valid_from;


/*
Future-dated assignments
------------------------
*/
-- SELECT *
-- FROM hierarchy_bitemporal_model_v2.v_future_dated_assignments
-- ORDER BY valid_from;


/*
Permanent action attribution
----------------------------
*/
-- SELECT *
-- FROM hierarchy_bitemporal_model_v2.v_action_assignment_attributions
-- WHERE action_id = :action_id;


/*
===============================================================================
11. IMPORTANT TRANSACTION BEHAVIOR
===============================================================================

The business action and attribution should be recorded in the SAME
transaction.

Example application flow:

    BEGIN;

    SELECT hierarchy_bitemporal_model_v2.record_action_assignment_attribution(
        :action_id,
        :organization_id,
        :node_id,
        :action_at,
        :attributed_by
    );

    -- Insert the actual business action here.

    COMMIT;

If the transaction fails, the attribution is rolled back together with
the business action.

After COMMIT, later hierarchy transfers do not update the attribution row.

===============================================================================
*/


/*
===============================================================================
12. IMPLEMENTATION GUARANTEE
===============================================================================

HIER-09
-------
The existing node_assignments model permits:

    valid_from < recorded_at

and:

    valid_from > recorded_at

while retaining the assignment as a separate historical record.

HIER-10
-------
At action creation time, the system captures:

    action_id
    assignment_id
    action_at

The captured assignment_id is immutable.

Therefore:

    ACTION
       |
       +---- assignment_id
                    |
                    +---- historical node_assignments row

A later transfer creates a new assignment interval. It does not change the
assignment_id stored for the previous action.

The point-in-time file remains responsible for reconstructing hierarchy state
at arbitrary timestamps. This file adds the permanent action-to-assignment
attribution required by HIER-10.

===============================================================================
*/
