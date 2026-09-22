/* ============================================================================
   FILE:
       bitemporal_transfer_atomicity_cache.sql

   TASK:
       HIER-11, HIER-12

   TITLE:
       Bitemporal Transfer Atomicity & Cache-Invalidation Triggers

   PURPOSE:
       1. Execute a hierarchy-node transfer atomically.
       2. Close the old parent assignment interval.
       3. Open the new parent assignment interval.
       4. Recompute derived authorization state.
       5. Invalidate authorization-cache state transactionally.
       6. Write an audit event.
       7. Prevent partial transfer application.
       8. Ensure stale authorization can be detected immediately after commit.

   SOURCE MODEL:
       hierarchy_bitemporal_model_v2

   IMPORTANT V2 RULES PRESERVED:
       - valid_from is inclusive.
       - valid_to is exclusive.
       - node_assignments uses node_id + parent_node_id.
       - single-parent overlap is enforced by the existing GiST exclusion
         constraint.
       - cycle prevention remains enforced by the existing deferred trigger.

   TRANSFER SEMANTICS:

       Before:

           child_node
               |
               +---- old_parent

           [valid_from, NULL)

       After:

           child_node
               |
               +---- old_parent
               [valid_from, transfer_time)

           child_node
               |
               +---- new_parent
               [transfer_time, NULL)

   HIER-11:
       All state changes occur in the same PostgreSQL transaction.

   HIER-12:
       Authorization cache state is invalidated transactionally by advancing
       the organization authorization-cache version.

       Consumers MUST compare their cached version with the current version
       before accepting cached authorization.

   NOTE:
       PostgreSQL cannot itself flush an external Redis/application cache.
       Therefore this script uses a transactional cache-version/invalidation
       model. The application/cache layer must honor this version before
       accepting cached authorization.

   ============================================================================ */


/* ============================================================================
   0. REQUIRED EXTENSION
   ============================================================================ */

CREATE EXTENSION IF NOT EXISTS pgcrypto;


/* ============================================================================
   1. TRANSFERS
   ============================================================================

   The older hierarchy_bitemporal_model.transfers table cannot be reused
   directly because V2 node_assignments does not contain transfer_id and
   uses parent_node_id rather than the older user-assignment structure.

   This V2 transfer table represents a hierarchy-node parent transfer.
   ============================================================================ */

CREATE TABLE IF NOT EXISTS hierarchy_bitemporal_model_v2.transfers
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    -- Node whose parent is changing.
    node_id UUID NOT NULL,

    -- Parent before transfer.
    from_parent_node_id UUID NOT NULL,

    -- Parent after transfer.
    to_parent_node_id UUID NOT NULL,

    -- Actor executing/authorizing the transfer.
    ordered_by UUID NOT NULL,

    -- Effective business time of the transfer.
    effective_at TIMESTAMPTZ NOT NULL,

    stated_reason TEXT NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'pending',

    committed_at TIMESTAMPTZ NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT transfers_pk
        PRIMARY KEY (id),

    /*
     * Transfer belongs to an existing organization.
     */
    CONSTRAINT transfers_organization_fk
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    /*
     * Actor must be an existing user.
     */
    CONSTRAINT transfers_ordered_by_fk
        FOREIGN KEY (ordered_by)
        REFERENCES identity_authentication_sessions.users(id),

    /*
     * Child node must belong to the same organization.
     */
    CONSTRAINT transfers_node_fk
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

    /*
     * Old parent must belong to the same organization.
     */
    CONSTRAINT transfers_from_parent_fk
        FOREIGN KEY
        (
            organization_id,
            from_parent_node_id
        )
        REFERENCES hierarchy_bitemporal_model_v2.nodes
        (
            organization_id,
            id
        ),

    /*
     * New parent must belong to the same organization.
     */
    CONSTRAINT transfers_to_parent_fk
        FOREIGN KEY
        (
            organization_id,
            to_parent_node_id
        )
        REFERENCES hierarchy_bitemporal_model_v2.nodes
        (
            organization_id,
            id
        ),

    /*
     * Child cannot be transferred to itself.
     */
    CONSTRAINT transfers_node_not_old_parent_chk
        CHECK (node_id <> from_parent_node_id),

    CONSTRAINT transfers_node_not_new_parent_chk
        CHECK (node_id <> to_parent_node_id),

    /*
     * Actual transfer requires a different parent.
     */
    CONSTRAINT transfers_different_parent_chk
        CHECK (from_parent_node_id <> to_parent_node_id),

    /*
     * Reason cannot be empty.
     */
    CONSTRAINT transfers_reason_chk
        CHECK (length(trim(stated_reason)) > 0),

    /*
     * Transfer state machine.
     */
    CONSTRAINT transfers_status_chk
        CHECK
        (
            status IN
            (
                'pending',
                'committed',
                'rolled_back'
            )
        )
);


/* ============================================================================
   2. TRANSFER INDEXES
   ============================================================================ */

CREATE INDEX IF NOT EXISTS idx_v2_transfers_org
ON hierarchy_bitemporal_model_v2.transfers
(
    organization_id
);

CREATE INDEX IF NOT EXISTS idx_v2_transfers_node
ON hierarchy_bitemporal_model_v2.transfers
(
    organization_id,
    node_id
);

CREATE INDEX IF NOT EXISTS idx_v2_transfers_status
ON hierarchy_bitemporal_model_v2.transfers
(
    organization_id,
    status
);

CREATE INDEX IF NOT EXISTS idx_v2_transfers_effective_at
ON hierarchy_bitemporal_model_v2.transfers
(
    organization_id,
    effective_at
);


/* ============================================================================
   3. DERIVED AUTHORIZATION PERMISSIONS
   ============================================================================

   V2 node_assignments contains hierarchy structure, but does not contain
   user/role assignment information.

   Therefore this table stores derived authorization relationships separately.

   A permission row means:

       user_id
           has authorization
           for node_id
           from valid_from
           until valid_to.

   The table is deliberately derived state.

   The authoritative hierarchy remains:

       hierarchy_bitemporal_model_v2.node_assignments
   ============================================================================ */

CREATE TABLE IF NOT EXISTS hierarchy_bitemporal_model_v2.derived_permissions
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    user_id UUID NOT NULL,

    node_id UUID NOT NULL,

    permission_scope TEXT NOT NULL DEFAULT 'SUBTREE',

    valid_from TIMESTAMPTZ NOT NULL,

    valid_to TIMESTAMPTZ NULL,

    recomputed_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT derived_permissions_pk
        PRIMARY KEY (id),

    CONSTRAINT derived_permissions_organization_fk
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT derived_permissions_user_fk
        FOREIGN KEY (user_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT derived_permissions_node_fk
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

    CONSTRAINT derived_permissions_validity_chk
        CHECK
        (
            valid_to IS NULL
            OR valid_to > valid_from
        ),

    CONSTRAINT derived_permissions_scope_chk
        CHECK
        (
            permission_scope IN
            (
                'NODE',
                'SUBTREE'
            )
        )
);


/* ============================================================================
   4. DERIVED PERMISSION INDEXES
   ============================================================================ */

CREATE INDEX IF NOT EXISTS idx_v2_derived_permissions_user
ON hierarchy_bitemporal_model_v2.derived_permissions
(
    organization_id,
    user_id,
    valid_from,
    valid_to
);

CREATE INDEX IF NOT EXISTS idx_v2_derived_permissions_node
ON hierarchy_bitemporal_model_v2.derived_permissions
(
    organization_id,
    node_id,
    valid_from,
    valid_to
);


/* ============================================================================
   5. AUTHORIZATION CACHE VERSION

   This is the transactional cache-invalidation mechanism.

   Every authorization cache consumer maintains:

       cached_version

   and compares it against:

       current_version

   If the versions differ, the cached authorization must not be used.

   The version is changed in the SAME transaction as the transfer.

   Therefore after COMMIT:

       old cache version != current version

   immediately.

   There is no background job required for invalidation state.
   ============================================================================ */

CREATE TABLE IF NOT EXISTS hierarchy_bitemporal_model_v2.auth_cache_versions
(
    organization_id UUID NOT NULL,

    cache_version BIGINT NOT NULL DEFAULT 0,

    invalidated_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    invalidated_by UUID NULL,

    invalidation_reason TEXT NULL,

    CONSTRAINT auth_cache_versions_pk
        PRIMARY KEY (organization_id),

    CONSTRAINT auth_cache_versions_organization_fk
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT auth_cache_versions_version_chk
        CHECK (cache_version >= 0),

    CONSTRAINT auth_cache_versions_invalidated_by_fk
        FOREIGN KEY (invalidated_by)
        REFERENCES identity_authentication_sessions.users(id)
);


/* ============================================================================
   6. CACHE VERSION INDEX
   ============================================================================ */

CREATE INDEX IF NOT EXISTS idx_v2_auth_cache_versions_invalidated_at
ON hierarchy_bitemporal_model_v2.auth_cache_versions
(
    invalidated_at
);


/* ============================================================================
   7. TRANSFER VALIDATION FUNCTION
   ============================================================================

   Validates that the transfer request corresponds to the currently open
   assignment.

   It also locks the relevant current assignment row.

   FOR UPDATE prevents two concurrent transfers from modifying the same
   hierarchy relationship simultaneously.
   ============================================================================ */

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.validate_transfer(
    p_transfer_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS
$$
DECLARE
    v_transfer
        hierarchy_bitemporal_model_v2.transfers%ROWTYPE;

    v_assignment_id UUID;

BEGIN

    SELECT *
    INTO v_transfer
    FROM hierarchy_bitemporal_model_v2.transfers
    WHERE id = p_transfer_id
    FOR UPDATE;

    IF NOT FOUND THEN

        RAISE EXCEPTION
            'Transfer % does not exist',
            p_transfer_id
            USING ERRCODE = 'P0002';

    END IF;


    IF v_transfer.status <> 'pending' THEN

        RAISE EXCEPTION
            'Transfer % is not pending; current status is %',
            p_transfer_id,
            v_transfer.status
            USING ERRCODE = '55000';

    END IF;


    /*
     * Lock the current open assignment for the node.
     */
    SELECT na.id
    INTO v_assignment_id
    FROM hierarchy_bitemporal_model_v2.node_assignments na
    WHERE na.organization_id = v_transfer.organization_id
      AND na.node_id = v_transfer.node_id
      AND na.valid_to IS NULL
    ORDER BY na.valid_from DESC
    LIMIT 1
    FOR UPDATE;


    IF NOT FOUND THEN

        RAISE EXCEPTION
            'No current hierarchy assignment exists for node %',
            v_transfer.node_id
            USING ERRCODE = 'P0002';

    END IF;


    /*
     * The currently active parent must match the transfer's
     * declared old parent.
     */
    IF NOT EXISTS
    (
        SELECT 1
        FROM hierarchy_bitemporal_model_v2.node_assignments na
        WHERE na.id = v_assignment_id
          AND na.parent_node_id = v_transfer.from_parent_node_id
    )
    THEN

        RAISE EXCEPTION
            'Transfer % is stale: current parent does not match from_parent_node_id',
            p_transfer_id
            USING ERRCODE = '40001';

    END IF;


END;
$$;


/* ============================================================================
   8. DERIVED PERMISSION RECOMPUTATION FUNCTION
   ============================================================================

   Important:

   The supplied V2 hierarchy schema contains no user-to-node assignment
   relationship.

   Therefore this function does NOT invent user permissions from hierarchy
   nodes.

   It invalidates/rebuilds derived permission state only for permissions
   already associated with the transferred branch.

   Existing permission rows are closed/recomputed according to the transfer
   boundary.

   Application-specific user-to-node permission population can be layered
   onto this function once that authoritative assignment source is defined.
   ============================================================================ */

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.recompute_derived_permissions_for_transfer(
    p_organization_id UUID,
    p_node_id UUID,
    p_effective_at TIMESTAMPTZ
)
RETURNS VOID
LANGUAGE plpgsql
AS
$$
BEGIN

    /*
     * Close permissions whose validity extends through the transfer point.

     * Only derived state is changed here.
     */
    UPDATE hierarchy_bitemporal_model_v2.derived_permissions dp
    SET
        valid_to = p_effective_at,
        recomputed_at = CURRENT_TIMESTAMP
    WHERE dp.organization_id = p_organization_id
      AND dp.node_id = p_node_id
      AND dp.valid_from < p_effective_at
      AND (
            dp.valid_to IS NULL
            OR dp.valid_to > p_effective_at
          );


    /*
     * Do not fabricate a new user permission assignment here.

     * The V2 source schema has no authoritative user->node assignment table.

     * The transfer therefore leaves new derived user permissions to the
     * existing authorization materialization process, while the cache
     * version guarantees that stale permissions cannot be accepted.
     */

END;
$$;


/* ============================================================================
   9. AUTHORIZATION CACHE INVALIDATION FUNCTION
   ============================================================================

   This operation MUST happen inside the transfer transaction.

   It uses an UPSERT with row locking so concurrent transfers for the same
   organization serialize their cache-version changes.
   ============================================================================ */

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.invalidate_auth_cache(
    p_organization_id UUID,
    p_invalidated_by UUID,
    p_reason TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS
$$
DECLARE
    v_new_version BIGINT;

BEGIN

    INSERT INTO hierarchy_bitemporal_model_v2.auth_cache_versions
    (
        organization_id,
        cache_version,
        invalidated_at,
        invalidated_by,
        invalidation_reason
    )
    VALUES
    (
        p_organization_id,
        1,
        CURRENT_TIMESTAMP,
        p_invalidated_by,
        p_reason
    )
    ON CONFLICT (organization_id)
    DO UPDATE
    SET
        cache_version =
            hierarchy_bitemporal_model_v2.auth_cache_versions.cache_version + 1,

        invalidated_at = CURRENT_TIMESTAMP,

        invalidated_by = EXCLUDED.invalidated_by,

        invalidation_reason = EXCLUDED.invalidation_reason

    RETURNING cache_version
    INTO v_new_version;


    RETURN v_new_version;

END;
$$;


/* ============================================================================
   10. CURRENT AUTHORIZATION CACHE VERSION FUNCTION
   ============================================================================ */

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.get_auth_cache_version(
    p_organization_id UUID
)
RETURNS BIGINT
LANGUAGE sql
STABLE
AS
$$
    SELECT COALESCE(
        (
            SELECT cache_version
            FROM hierarchy_bitemporal_model_v2.auth_cache_versions
            WHERE organization_id = p_organization_id
        ),
        0
    );
$$;


/* ============================================================================
   11. TRANSFER AUDIT FUNCTION
   ============================================================================

   Uses the existing audit_trail.audit_events table.

   A transaction-scoped advisory lock serializes audit-chain construction
   within an organization.

   The audit record is inserted in the SAME transaction as the transfer.
   If transfer execution rolls back, the audit record also rolls back.
   ============================================================================ */

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.write_transfer_audit(
    p_transfer_id UUID,
    p_organization_id UUID,
    p_actor_id UUID,
    p_node_id UUID,
    p_from_parent_node_id UUID,
    p_to_parent_node_id UUID,
    p_effective_at TIMESTAMPTZ
)
RETURNS UUID
LANGUAGE plpgsql
AS
$$
DECLARE
    v_prev_hash TEXT;
    v_hash TEXT;
    v_audit_id UUID;
    v_payload JSONB;
BEGIN

    /*
     * Serialize audit-chain creation for this organization.
     */
    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            p_organization_id::TEXT,
            0
        )
    );


    SELECT ae.hash
    INTO v_prev_hash
    FROM audit_trail.audit_events ae
    WHERE ae.organization_id = p_organization_id
    ORDER BY ae.seq DESC
    LIMIT 1;


    v_prev_hash := COALESCE(v_prev_hash, 'GENESIS');


    v_payload :=
        jsonb_build_object(
            'transfer_id', p_transfer_id,
            'node_id', p_node_id,
            'from_parent_node_id', p_from_parent_node_id,
            'to_parent_node_id', p_to_parent_node_id,
            'effective_at', p_effective_at,
            'event', 'HIERARCHY_NODE_TRANSFER',
            'atomicity', 'transactional',
            'cache_invalidation', 'transactional_version_bump'
        );


    v_hash :=
        encode(
            digest(
                v_prev_hash
                || '|'
                || p_organization_id::TEXT
                || '|'
                || p_actor_id::TEXT
                || '|'
                || 'HIERARCHY_NODE_TRANSFER'
                || '|'
                || COALESCE(v_payload::TEXT, ''),
                'sha256'
            ),
            'hex'
        );


    INSERT INTO audit_trail.audit_events
    (
        organization_id,
        prev_hash,
        hash,
        actor_id,
        action_type,
        resource_type,
        resource_id,
        payload
    )
    VALUES
    (
        p_organization_id,
        v_prev_hash,
        v_hash,
        p_actor_id,
        'HIERARCHY_NODE_TRANSFER',
        'hierarchy_bitemporal_model_v2.node',
        p_node_id,
        v_payload
    )
    RETURNING id
    INTO v_audit_id;


    RETURN v_audit_id;

END;
$$;


/* ============================================================================
   12. ATOMIC TRANSFER EXECUTION
   ============================================================================

   THIS IS THE MAIN HIER-11 FUNCTION.

   All operations occur in the caller's PostgreSQL transaction.

   The function:

       1. Locks transfer.
       2. Locks current assignment.
       3. Validates source parent.
       4. Closes old assignment.
       5. Opens new assignment.
       6. Recomputes derived permissions.
       7. Invalidates auth cache.
       8. Writes audit.
       9. Marks transfer committed.

   Any exception causes the PostgreSQL transaction to fail.

   Consequently, partial application cannot be committed.
   ============================================================================ */

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.execute_transfer(
    p_transfer_id UUID
)
RETURNS TABLE
(
    transfer_id UUID,
    status TEXT,
    cache_version BIGINT,
    audit_event_id UUID,
    committed_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS
$$
DECLARE

    v_transfer
        hierarchy_bitemporal_model_v2.transfers%ROWTYPE;

    v_current_assignment_id UUID;

    v_cache_version BIGINT;

    v_audit_event_id UUID;

    v_committed_at TIMESTAMPTZ;

BEGIN

    /* ------------------------------------------------------------
       1. Lock and load transfer.
       ------------------------------------------------------------ */

    SELECT *
    INTO v_transfer
    FROM hierarchy_bitemporal_model_v2.transfers
    WHERE id = p_transfer_id
    FOR UPDATE;


    IF NOT FOUND THEN

        RAISE EXCEPTION
            'Transfer % does not exist',
            p_transfer_id
            USING ERRCODE = 'P0002';

    END IF;


    IF v_transfer.status <> 'pending' THEN

        RAISE EXCEPTION
            'Transfer % is not pending; status is %',
            p_transfer_id,
            v_transfer.status
            USING ERRCODE = '55000';

    END IF;


    /* ------------------------------------------------------------
       2. Lock current assignment.

       The current assignment is the open-ended interval.
       ------------------------------------------------------------ */

    SELECT na.id
    INTO v_current_assignment_id
    FROM hierarchy_bitemporal_model_v2.node_assignments na
    WHERE na.organization_id = v_transfer.organization_id
      AND na.node_id = v_transfer.node_id
      AND na.valid_to IS NULL
    ORDER BY na.valid_from DESC
    LIMIT 1
    FOR UPDATE;


    IF NOT FOUND THEN

        RAISE EXCEPTION
            'No current assignment exists for node %',
            v_transfer.node_id
            USING ERRCODE = 'P0002';

    END IF;


    /* ------------------------------------------------------------
       3. Verify that the current parent is the expected old parent.
       ------------------------------------------------------------ */

    IF NOT EXISTS
    (
        SELECT 1
        FROM hierarchy_bitemporal_model_v2.node_assignments na
        WHERE na.id = v_current_assignment_id
          AND na.parent_node_id = v_transfer.from_parent_node_id
    )
    THEN

        RAISE EXCEPTION
            'Transfer % rejected because current parent does not match source parent',
            p_transfer_id
            USING ERRCODE = '40001';

    END IF;


    /* ------------------------------------------------------------
       4. Effective date validation.

       Transfer cannot close an assignment before it begins.
       ------------------------------------------------------------ */

    IF v_transfer.effective_at
       <=
       (
           SELECT valid_from
           FROM hierarchy_bitemporal_model_v2.node_assignments
           WHERE id = v_current_assignment_id
       )
    THEN

        RAISE EXCEPTION
            'Transfer % effective_at must be after the current assignment valid_from',
            p_transfer_id
            USING ERRCODE = '22023';

    END IF;


    /* ------------------------------------------------------------
       5. Close old interval.
       ------------------------------------------------------------ */

    UPDATE hierarchy_bitemporal_model_v2.node_assignments
    SET
        valid_to = v_transfer.effective_at
    WHERE id = v_current_assignment_id;


    IF NOT FOUND THEN

        RAISE EXCEPTION
            'Failed to close current assignment for transfer %',
            p_transfer_id
            USING ERRCODE = 'P0001';

    END IF;


    /* ------------------------------------------------------------
       6. Open new parent assignment.

       The existing single-parent exclusion constraint and deferred
       cycle-prevention trigger remain active.

       If either rejects this assignment, the entire transaction fails.
       ------------------------------------------------------------ */

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
    VALUES
    (
        gen_random_uuid(),
        v_transfer.organization_id,
        v_transfer.node_id,
        v_transfer.to_parent_node_id,
        v_transfer.effective_at,
        NULL,
        CURRENT_TIMESTAMP,
        v_transfer.ordered_by
    );


    /* ------------------------------------------------------------
       7. Recompute derived permissions.
       ------------------------------------------------------------ */

    PERFORM
        hierarchy_bitemporal_model_v2
        .recompute_derived_permissions_for_transfer(
            v_transfer.organization_id,
            v_transfer.node_id,
            v_transfer.effective_at
        );


    /* ------------------------------------------------------------
       8. Invalidate authorization cache.

       This is part of the SAME transaction.
       ------------------------------------------------------------ */

    v_cache_version :=
        hierarchy_bitemporal_model_v2.invalidate_auth_cache(
            v_transfer.organization_id,
            v_transfer.ordered_by,
            'HIER-12 hierarchy transfer'
        );


    /* ------------------------------------------------------------
       9. Write audit record.

       This is also part of the SAME transaction.
       ------------------------------------------------------------ */

    v_audit_event_id :=
        hierarchy_bitemporal_model_v2.write_transfer_audit(
            v_transfer.id,
            v_transfer.organization_id,
            v_transfer.ordered_by,
            v_transfer.node_id,
            v_transfer.from_parent_node_id,
            v_transfer.to_parent_node_id,
            v_transfer.effective_at
        );


    /* ------------------------------------------------------------
       10. Mark transfer committed.
       ------------------------------------------------------------ */

    v_committed_at := CURRENT_TIMESTAMP;


    UPDATE hierarchy_bitemporal_model_v2.transfers
    SET
        status = 'committed',
        committed_at = v_committed_at
    WHERE id = v_transfer.id;


    /* ------------------------------------------------------------
       11. Return transaction result.
       ------------------------------------------------------------ */

    transfer_id := v_transfer.id;
    status := 'committed';
    cache_version := v_cache_version;
    audit_event_id := v_audit_event_id;
    committed_at := v_committed_at;

    RETURN NEXT;

END;
$$;


/* ============================================================================
   13. AUTHORIZATION CACHE VALIDATION HELPER
   ============================================================================

   Application authorization code should call this before trusting a cached
   authorization result.

   Example:

       SELECT hierarchy_bitemporal_model_v2.is_cache_version_current(
           :organization_id,
           :cached_version
       );

   TRUE:
       cached authorization version is current.

   FALSE:
       cache is stale and MUST NOT be used.
   ============================================================================ */

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.is_cache_version_current(
    p_organization_id UUID,
    p_cached_version BIGINT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS
$$
    SELECT
        COALESCE(
            (
                SELECT cache_version
                FROM hierarchy_bitemporal_model_v2.auth_cache_versions
                WHERE organization_id = p_organization_id
            ),
            0
        ) = p_cached_version;
$$;


/* ============================================================================
   14. CURRENT HIERARCHY AUTHORIZATION CHECK

   This helper deliberately reads the authoritative V2 hierarchy rather than
   trusting a stale derived/cache result.

   A target node is considered inside the transferred branch when it is
   reachable from p_root_node_id at the requested point in time.

   The existing V2 point-in-time functions can also be used by the
   authorization layer.
   ============================================================================ */

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.is_node_currently_reachable(
    p_organization_id UUID,
    p_root_node_id UUID,
    p_target_node_id UUID
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS
$$

    SELECT EXISTS
    (
        WITH RECURSIVE subtree AS
        (
            SELECT
                p_root_node_id AS node_id

            UNION

            SELECT
                na.node_id
            FROM subtree s
            JOIN hierarchy_bitemporal_model_v2.node_assignments na
              ON na.organization_id = p_organization_id
             AND na.parent_node_id = s.node_id
             AND na.valid_from <= CURRENT_TIMESTAMP
             AND (
                    na.valid_to IS NULL
                    OR CURRENT_TIMESTAMP < na.valid_to
                 )
        )
        SELECT 1
        FROM subtree
        WHERE node_id = p_target_node_id
    );

$$;


/* ============================================================================
   15. PERFORMANCE INDEXES REQUIRED BY TRANSFER
   ============================================================================

   The existing V2 point-in-time implementation already defines:

       organization_id + node_id + validity

   and

       organization_id + parent_node_id + validity.

   These are preserved.

   The additional partial index below accelerates retrieval of the current
   open assignment used by the transfer function.
   ============================================================================ */

CREATE INDEX IF NOT EXISTS idx_v2_node_assignments_current_node
ON hierarchy_bitemporal_model_v2.node_assignments
(
    organization_id,
    node_id,
    valid_from DESC
)
WHERE valid_to IS NULL;


/* ============================================================================
   16. CURRENT PARENT LOOKUP INDEX
   ============================================================================ */

CREATE INDEX IF NOT EXISTS idx_v2_node_assignments_current_parent
ON hierarchy_bitemporal_model_v2.node_assignments
(
    organization_id,
    parent_node_id,
    node_id,
    valid_from DESC
)
WHERE valid_to IS NULL;


/* ============================================================================
   17. TRANSFER AUDIT LOOKUP INDEX
   ============================================================================ */

CREATE INDEX IF NOT EXISTS idx_v2_transfers_node_effective
ON hierarchy_bitemporal_model_v2.transfers
(
    organization_id,
    node_id,
    effective_at DESC
);


/* ============================================================================
   18. HIER-12 CACHE INVALIDATION TRIGGER

   The trigger ensures that direct administrative modification of the
   transfer status cannot silently mark a transfer committed without a
   cache-version update.

   Normal transfer execution MUST use execute_transfer().

   This trigger is therefore a defensive control.
   ============================================================================ */

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.prevent_direct_transfer_commit()
RETURNS TRIGGER
LANGUAGE plpgsql
AS
$$
BEGIN

    IF NEW.status = 'committed'
       AND OLD.status <> 'committed'
    THEN

        /*
         * The controlled execution function sets committed_at and performs
         * cache invalidation/audit before this status change.

         * PostgreSQL does not expose a simple function-call identity here,
         * therefore direct SQL commits are prevented by requiring the
         * transaction-local marker.
         */

        IF current_setting(
            'hierarchy_bitemporal_model_v2.transfer_execution',
            TRUE
        ) IS DISTINCT FROM 'allowed'
        THEN

            RAISE EXCEPTION
                'Direct transfer commit is prohibited. Use hierarchy_bitemporal_model_v2.execute_transfer()'
                USING ERRCODE = '42501';

        END IF;

    END IF;


    RETURN NEW;

END;
$$;


/* ============================================================================
   19. TRANSFER COMMIT PROTECTION TRIGGER
   ============================================================================ */

DROP TRIGGER IF EXISTS trg_prevent_direct_transfer_commit
ON hierarchy_bitemporal_model_v2.transfers;


CREATE TRIGGER trg_prevent_direct_transfer_commit

BEFORE UPDATE OF status

ON hierarchy_bitemporal_model_v2.transfers

FOR EACH ROW

EXECUTE FUNCTION
hierarchy_bitemporal_model_v2.prevent_direct_transfer_commit();


/* ============================================================================
   20. REPLACE EXECUTE_TRANSFER WITH CONTROLLED TRANSACTION MARKER

   PostgreSQL functions execute inside the caller's transaction.

   The marker exists only for the duration of the function transaction.

   NOTE:
       set_config(..., true) makes the setting LOCAL to the current
       transaction.
   ============================================================================ */

CREATE OR REPLACE FUNCTION
hierarchy_bitemporal_model_v2.execute_transfer(
    p_transfer_id UUID
)
RETURNS TABLE
(
    transfer_id UUID,
    status TEXT,
    cache_version BIGINT,
    audit_event_id UUID,
    committed_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS
$$
DECLARE

    v_transfer
        hierarchy_bitemporal_model_v2.transfers%ROWTYPE;

    v_current_assignment_id UUID;

    v_cache_version BIGINT;

    v_audit_event_id UUID;

    v_committed_at TIMESTAMPTZ;

BEGIN

    /*
     * Mark this transaction as the controlled transfer execution context.
     */
    PERFORM set_config(
        'hierarchy_bitemporal_model_v2.transfer_execution',
        'allowed',
        TRUE
    );


    /* ------------------------------------------------------------
       LOCK TRANSFER
       ------------------------------------------------------------ */

    SELECT *
    INTO v_transfer
    FROM hierarchy_bitemporal_model_v2.transfers
    WHERE id = p_transfer_id
    FOR UPDATE;


    IF NOT FOUND THEN

        RAISE EXCEPTION
            'Transfer % does not exist',
            p_transfer_id
            USING ERRCODE = 'P0002';

    END IF;


    IF v_transfer.status <> 'pending' THEN

        RAISE EXCEPTION
            'Transfer % is not pending; current status is %',
            p_transfer_id,
            v_transfer.status
            USING ERRCODE = '55000';

    END IF;


    /* ------------------------------------------------------------
       LOCK CURRENT ASSIGNMENT
       ------------------------------------------------------------ */

    SELECT na.id
    INTO v_current_assignment_id
    FROM hierarchy_bitemporal_model_v2.node_assignments na
    WHERE na.organization_id = v_transfer.organization_id
      AND na.node_id = v_transfer.node_id
      AND na.valid_to IS NULL
    ORDER BY na.valid_from DESC
    LIMIT 1
    FOR UPDATE;


    IF NOT FOUND THEN

        RAISE EXCEPTION
            'No current assignment exists for node %',
            v_transfer.node_id
            USING ERRCODE = 'P0002';

    END IF;


    /* ------------------------------------------------------------
       VERIFY SOURCE PARENT
       ------------------------------------------------------------ */

    IF NOT EXISTS
    (
        SELECT 1
        FROM hierarchy_bitemporal_model_v2.node_assignments na
        WHERE na.id = v_current_assignment_id
          AND na.parent_node_id = v_transfer.from_parent_node_id
    )
    THEN

        RAISE EXCEPTION
            'Transfer % rejected: source parent does not match current hierarchy',
            p_transfer_id
            USING ERRCODE = '40001';

    END IF;


    /* ------------------------------------------------------------
       VALIDATE EFFECTIVE TIME
       ------------------------------------------------------------ */

    IF v_transfer.effective_at
       <=
       (
           SELECT valid_from
           FROM hierarchy_bitemporal_model_v2.node_assignments
           WHERE id = v_current_assignment_id
       )
    THEN

        RAISE EXCEPTION
            'Transfer % effective_at must be greater than current valid_from',
            p_transfer_id
            USING ERRCODE = '22023';

    END IF;


    /* ------------------------------------------------------------
       CLOSE OLD ASSIGNMENT
       ------------------------------------------------------------ */

    UPDATE hierarchy_bitemporal_model_v2.node_assignments
    SET
        valid_to = v_transfer.effective_at
    WHERE id = v_current_assignment_id;


    /* ------------------------------------------------------------
       OPEN NEW ASSIGNMENT
       ------------------------------------------------------------ */

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
    VALUES
    (
        gen_random_uuid(),
        v_transfer.organization_id,
        v_transfer.node_id,
        v_transfer.to_parent_node_id,
        v_transfer.effective_at,
        NULL,
        CURRENT_TIMESTAMP,
        v_transfer.ordered_by
    );


    /*
     * Because the V2 cycle-prevention trigger is DEFERRABLE INITIALLY
     * DEFERRED, its validation occurs before transaction commit.
     *
     * If a cycle is detected, the transaction cannot commit.
     */


    /* ------------------------------------------------------------
       RECOMPUTE DERIVED PERMISSIONS
       ------------------------------------------------------------ */

    PERFORM
        hierarchy_bitemporal_model_v2
        .recompute_derived_permissions_for_transfer(
            v_transfer.organization_id,
            v_transfer.node_id,
            v_transfer.effective_at
        );


    /* ------------------------------------------------------------
       INVALIDATE AUTHORIZATION CACHE
       ------------------------------------------------------------ */

    v_cache_version :=
        hierarchy_bitemporal_model_v2.invalidate_auth_cache(
            v_transfer.organization_id,
            v_transfer.ordered_by,
            'HIER-12 transfer invalidation'
        );


    /* ------------------------------------------------------------
       WRITE AUDIT
       ------------------------------------------------------------ */

    v_audit_event_id :=
        hierarchy_bitemporal_model_v2.write_transfer_audit(
            v_transfer.id,
            v_transfer.organization_id,
            v_transfer.ordered_by,
            v_transfer.node_id,
            v_transfer.from_parent_node_id,
            v_transfer.to_parent_node_id,
            v_transfer.effective_at
        );


    /* ------------------------------------------------------------
       MARK TRANSFER COMMITTED
       ------------------------------------------------------------ */

    v_committed_at := CURRENT_TIMESTAMP;


    UPDATE hierarchy_bitemporal_model_v2.transfers
    SET
        status = 'committed',
        committed_at = v_committed_at
    WHERE id = v_transfer.id;


    /* ------------------------------------------------------------
       RETURN RESULT
       ------------------------------------------------------------ */

    RETURN QUERY
    SELECT
        v_transfer.id,
        'committed'::TEXT,
        v_cache_version,
        v_audit_event_id,
        v_committed_at;

END;
$$;


/* ============================================================================
   21. TRANSACTIONAL TEST EXAMPLE — SUCCESS
   ============================================================================

   Replace UUID values with actual IDs.

   IMPORTANT:
       The application should invoke execute_transfer() inside its normal
       transaction boundary.

   Example:

       BEGIN;

       SELECT *
       FROM hierarchy_bitemporal_model_v2.execute_transfer(
           'TRANSFER-UUID'
       );

       COMMIT;

   On success, one transaction contains:

       OLD ASSIGNMENT CLOSED
       NEW ASSIGNMENT OPENED
       DERIVED PERMISSIONS UPDATED
       CACHE VERSION ADVANCED
       AUDIT EVENT WRITTEN
       TRANSFER MARKED COMMITTED


   ============================================================================ */


/* ============================================================================
   22. TRANSACTIONAL TEST EXAMPLE — FAILURE / ROLLBACK
   ============================================================================

       BEGIN;

       SELECT *
       FROM hierarchy_bitemporal_model_v2.execute_transfer(
           'TRANSFER-UUID'
       );

       -- If any constraint/function raises an exception:

       ROLLBACK;


   Expected result:

       old assignment remains unchanged
       new assignment is not committed
       cache version is not advanced
       audit event is not committed
       transfer remains pending

   This is the HIER-11 atomicity requirement.
   ============================================================================ */


/* ============================================================================
   23. HIER-12 CACHE VERSION TEST
   ============================================================================

   Application/cache layer:

       1. Read current cache version.
       2. Cache authorization together with that version.
       3. After transfer, read current version.
       4. Compare versions.
       5. If different, reject stale cache and recompute authorization.

   Example:

       SELECT
           hierarchy_bitemporal_model_v2.get_auth_cache_version(
               'ORGANIZATION-UUID'
           );

   Then:

       SELECT
           hierarchy_bitemporal_model_v2.is_cache_version_current(
               'ORGANIZATION-UUID',
               :cached_version
           );

   Expected after a committed transfer:

       FALSE

   for the pre-transfer cached version.
   ============================================================================ */


/* ============================================================================
   24. HIER-12 AUTHORIZATION SAFETY RULE
   ============================================================================

   The application authorization path MUST follow:

       cached authorization
               |
               v
       compare cache_version
               |
          +----+----+
          |         |
        SAME     DIFFERENT
          |         |
          v         v
        usable   DISCARD
                    |
                    v
              recompute/read
              authoritative
              hierarchy

   A stale cache entry MUST NEVER be accepted solely because its TTL has
   not expired.

   This is necessary to satisfy the security intent of HIER-12.
   ============================================================================ */


/* ============================================================================
   25. PERFORMANCE / VERIFICATION
   ============================================================================

   Existing V2 point-in-time requirements specify:

       authorization decision <= 10 ms p95
       approximately 200,000 nodes

   Run representative tests with:

       EXPLAIN (ANALYZE, BUFFERS)

   against:

       - current parent lookup
       - descendants
       - subtree membership
       - authorization lookup

   HIER-12 latency measurement should additionally record:

       transfer COMMIT timestamp
       first authorization request that observes new cache_version

   Acceptance:

       stale former-branch authorization MUST NOT be accepted after the
       committed cache-version change.

   The database alone cannot prove an external Redis/application cache
   physically purged within one second. The external cache implementation
   must honor the transactional version check.
   ============================================================================ */


/* ============================================================================
   END OF HIER-11 / HIER-12
   ============================================================================ */