-- ============================================================================
-- DB-015: CITIZEN ISSUES, CLUSTERING & CORROBORATION
-- ============================================================================
-- Incremental extension of the existing citizen_issues schema.
--
-- CIT-07: category + geographic proximity + semantic similarity clustering.
-- CIT-08: distinct-citizen corroboration counting.
-- CIT-09: system suggestion, human confirmation, reversible split/merge history.
-- CIT-10: individual corroborating-citizen notification/closure tracking.
--
-- Existing authoritative tables are reused; they are NOT recreated.
-- ============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS citizen_issues;

-- ============================================================================
-- 1. EXTEND EXISTING CANONICAL ISSUES WITH CLUSTERING METADATA
-- ============================================================================

ALTER TABLE citizen_issues.canonical_issues
    ADD COLUMN IF NOT EXISTS clustering_status TEXT NOT NULL DEFAULT 'confirmed',
    ADD COLUMN IF NOT EXISTS clustering_method TEXT NULL,
    ADD COLUMN IF NOT EXISTS geo_proximity_meters NUMERIC(12,2) NULL,
    ADD COLUMN IF NOT EXISTS semantic_similarity_score NUMERIC(5,4) NULL,
    ADD COLUMN IF NOT EXISTS clustering_suggested_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS clustering_suggested_by UUID NULL,
    ADD COLUMN IF NOT EXISTS clustering_confirmed_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS clustering_confirmed_by UUID NULL;

ALTER TABLE citizen_issues.canonical_issues
    DROP CONSTRAINT IF EXISTS chk_canonical_issues_clustering_status;

ALTER TABLE citizen_issues.canonical_issues
    ADD CONSTRAINT chk_canonical_issues_clustering_status
    CHECK (clustering_status IN ('suggested','confirmed','rejected','split','merged'));

ALTER TABLE citizen_issues.canonical_issues
    DROP CONSTRAINT IF EXISTS chk_canonical_issues_geo_proximity;

ALTER TABLE citizen_issues.canonical_issues
    ADD CONSTRAINT chk_canonical_issues_geo_proximity
    CHECK (geo_proximity_meters IS NULL OR geo_proximity_meters >= 0);

ALTER TABLE citizen_issues.canonical_issues
    DROP CONSTRAINT IF EXISTS chk_canonical_issues_semantic_similarity;

ALTER TABLE citizen_issues.canonical_issues
    ADD CONSTRAINT chk_canonical_issues_semantic_similarity
    CHECK (semantic_similarity_score IS NULL OR semantic_similarity_score BETWEEN 0 AND 1);

ALTER TABLE citizen_issues.canonical_issues
    DROP CONSTRAINT IF EXISTS chk_canonical_issues_clustering_suggestion_actor;

ALTER TABLE citizen_issues.canonical_issues
    ADD CONSTRAINT chk_canonical_issues_clustering_suggestion_actor
    CHECK (clustering_suggested_at IS NULL OR clustering_suggested_by IS NOT NULL);

ALTER TABLE citizen_issues.canonical_issues
    DROP CONSTRAINT IF EXISTS chk_canonical_issues_clustering_confirmation_actor;

ALTER TABLE citizen_issues.canonical_issues
    ADD CONSTRAINT chk_canonical_issues_clustering_confirmation_actor
    CHECK (clustering_confirmed_at IS NULL OR clustering_confirmed_by IS NOT NULL);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'citizen_issues.canonical_issues'::regclass
          AND conname = 'fk_canonical_issues_clustering_suggested_by'
    ) THEN
        ALTER TABLE citizen_issues.canonical_issues
            ADD CONSTRAINT fk_canonical_issues_clustering_suggested_by
            FOREIGN KEY (clustering_suggested_by)
            REFERENCES identity_authentication_sessions.users(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'citizen_issues.canonical_issues'::regclass
          AND conname = 'fk_canonical_issues_clustering_confirmed_by'
    ) THEN
        ALTER TABLE citizen_issues.canonical_issues
            ADD CONSTRAINT fk_canonical_issues_clustering_confirmed_by
            FOREIGN KEY (clustering_confirmed_by)
            REFERENCES identity_authentication_sessions.users(id);
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_canonical_issues_clustering_status
    ON citizen_issues.canonical_issues (organization_id, clustering_status);

CREATE INDEX IF NOT EXISTS idx_canonical_issues_semantic_similarity
    ON citizen_issues.canonical_issues (organization_id, semantic_similarity_score)
    WHERE semantic_similarity_score IS NOT NULL;

-- Tenant-integrity support for the new composite foreign keys.
-- These indexes ensure an object referenced by a DB-015 row belongs to the
-- same organization as the DB-015 row itself.
CREATE UNIQUE INDEX IF NOT EXISTS uq_canonical_issues_organization_id_id
    ON citizen_issues.canonical_issues (organization_id, id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_organization_id_id
    ON identity_authentication_sessions.users (organization_id, id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_citizen_submissions_organization_id_id
    ON citizen_issues.citizen_submissions (organization_id, id);

-- ============================================================================
-- 2. CORROBORATIONS
-- ============================================================================
-- One active row represents one distinct citizen's corroboration of one
-- canonical issue. Repeated reports by the same citizen do not create
-- another active corroboration row.

CREATE TABLE IF NOT EXISTS citizen_issues.corroborations
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    canonical_issue_id UUID NOT NULL,
    citizen_user_id UUID NULL,
    citizen_handle TEXT NULL,
    source_submission_id UUID NULL,

    status TEXT NOT NULL DEFAULT 'active',
    notification_status TEXT NOT NULL DEFAULT 'pending',
    last_notified_at TIMESTAMPTZ NULL,
    closure_confirmation_status TEXT NOT NULL DEFAULT 'pending',
    closure_confirmed_at TIMESTAMPTZ NULL,

    corroborated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_corroborations PRIMARY KEY (id),

    CONSTRAINT fk_corroborations_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_corroborations_canonical_issue
        FOREIGN KEY (organization_id, canonical_issue_id)
        REFERENCES citizen_issues.canonical_issues(organization_id, id),

    CONSTRAINT fk_corroborations_citizen_user
        FOREIGN KEY (organization_id, citizen_user_id)
        REFERENCES identity_authentication_sessions.users(organization_id, id),

    CONSTRAINT fk_corroborations_source_submission
        FOREIGN KEY (organization_id, source_submission_id)
        REFERENCES citizen_issues.citizen_submissions(organization_id, id),

    CONSTRAINT chk_corroborations_identity
        CHECK (
            (citizen_user_id IS NOT NULL AND citizen_handle IS NULL)
            OR
            (citizen_user_id IS NULL
             AND citizen_handle IS NOT NULL
             AND length(trim(citizen_handle)) > 0)
        ),

    CONSTRAINT chk_corroborations_status
        CHECK (status IN ('active','withdrawn')),

    CONSTRAINT chk_corroborations_notification_status
        CHECK (notification_status IN ('pending','sent','failed','suppressed')),

    CONSTRAINT chk_corroborations_closure_confirmation_status
        CHECK (
            closure_confirmation_status IN
            ('pending','confirmed','disputed','not_required')
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_corroborations_registered_citizen
    ON citizen_issues.corroborations
        (organization_id, canonical_issue_id, citizen_user_id)
    WHERE citizen_user_id IS NOT NULL
      AND status = 'active';

CREATE UNIQUE INDEX IF NOT EXISTS uq_corroborations_handle
    ON citizen_issues.corroborations
        (organization_id, canonical_issue_id, citizen_handle)
    WHERE citizen_user_id IS NULL
      AND citizen_handle IS NOT NULL
      AND status = 'active';

CREATE INDEX IF NOT EXISTS idx_corroborations_issue
    ON citizen_issues.corroborations (organization_id, canonical_issue_id);

CREATE INDEX IF NOT EXISTS idx_corroborations_citizen
    ON citizen_issues.corroborations (organization_id, citizen_user_id)
    WHERE citizen_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_corroborations_notification
    ON citizen_issues.corroborations (organization_id, notification_status)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_corroborations_closure
    ON citizen_issues.corroborations (organization_id, closure_confirmation_status)
    WHERE status = 'active';

-- ============================================================================
-- 3. CLUSTERING OPERATIONS: SUGGEST / CONFIRM / REJECT / MERGE / SPLIT / REVERSE
-- ============================================================================
-- Separate from issue_history:
--   issue_history = canonical issue state-machine history.
--   clustering_operations = cluster decision and split/merge history.

CREATE TABLE IF NOT EXISTS citizen_issues.clustering_operations
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    operation_type TEXT NOT NULL,

    source_canonical_issue_id UUID NULL,
    target_canonical_issue_id UUID NULL,
    operation_group_id UUID NOT NULL DEFAULT gen_random_uuid(),

    category_match BOOLEAN NULL,
    geo_distance_meters NUMERIC(12,2) NULL,
    semantic_similarity_score NUMERIC(5,4) NULL,

    suggested_by UUID NULL,
    confirmed_by UUID NULL,
    suggested_at TIMESTAMPTZ NULL,
    confirmed_at TIMESTAMPTZ NULL,

    reason TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_clustering_operations PRIMARY KEY (id),

    CONSTRAINT fk_clustering_operations_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_clustering_operations_source_issue
        FOREIGN KEY (source_canonical_issue_id)
        REFERENCES citizen_issues.canonical_issues(id),

    CONSTRAINT fk_clustering_operations_target_issue
        FOREIGN KEY (target_canonical_issue_id)
        REFERENCES citizen_issues.canonical_issues(id),

    CONSTRAINT fk_clustering_operations_suggested_by
        FOREIGN KEY (suggested_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_clustering_operations_confirmed_by
        FOREIGN KEY (confirmed_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_clustering_operations_type
        CHECK (
            operation_type IN ('suggest','confirm','reject','merge','split','reverse')
        ),

    CONSTRAINT chk_clustering_operations_distance
        CHECK (geo_distance_meters IS NULL OR geo_distance_meters >= 0),

    CONSTRAINT chk_clustering_operations_similarity
        CHECK (
            semantic_similarity_score IS NULL
            OR semantic_similarity_score BETWEEN 0 AND 1
        ),

    CONSTRAINT chk_clustering_operations_metadata
        CHECK (jsonb_typeof(metadata) = 'object'),

    CONSTRAINT chk_clustering_operations_suggestion_actor
        CHECK (suggested_at IS NULL OR suggested_by IS NOT NULL),

    CONSTRAINT chk_clustering_operations_confirmation_actor
        CHECK (confirmed_at IS NULL OR confirmed_by IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_clustering_operations_org_created
    ON citizen_issues.clustering_operations (organization_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_clustering_operations_source
    ON citizen_issues.clustering_operations
        (organization_id, source_canonical_issue_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_clustering_operations_target
    ON citizen_issues.clustering_operations
        (organization_id, target_canonical_issue_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_clustering_operations_group
    ON citizen_issues.clustering_operations
        (organization_id, operation_group_id, created_at);

-- ============================================================================
-- 4. CORROBORATION COUNT MAINTENANCE
-- ============================================================================

CREATE OR REPLACE FUNCTION citizen_issues.refresh_corroboration_counts(
    p_canonical_issue_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_organization_id UUID;
BEGIN
    SELECT ci.organization_id
      INTO v_organization_id
      FROM citizen_issues.canonical_issues ci
     WHERE ci.id = p_canonical_issue_id
     FOR UPDATE;

    IF v_organization_id IS NULL THEN
        RAISE EXCEPTION
            'CIT-08: canonical issue % does not exist',
            p_canonical_issue_id;
    END IF;

    UPDATE citizen_issues.canonical_issues ci
       SET distinct_citizen_count = (
               SELECT COUNT(*)
               FROM citizen_issues.corroborations c
               WHERE c.organization_id = v_organization_id
                 AND c.canonical_issue_id = p_canonical_issue_id
                 AND c.status = 'active'
           ),
           total_corroboration_count = (
               SELECT COUNT(*)
               FROM citizen_issues.corroborations c
               WHERE c.organization_id = v_organization_id
                 AND c.canonical_issue_id = p_canonical_issue_id
                 AND c.status = 'active'
           ),
           updated_at = CURRENT_TIMESTAMP
     WHERE ci.id = p_canonical_issue_id;
END;
$$;

CREATE OR REPLACE FUNCTION citizen_issues.trg_refresh_corroboration_counts()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM citizen_issues.refresh_corroboration_counts(OLD.canonical_issue_id);
        RETURN OLD;
    END IF;

    PERFORM citizen_issues.refresh_corroboration_counts(NEW.canonical_issue_id);

    IF TG_OP = 'UPDATE'
       AND OLD.canonical_issue_id IS DISTINCT FROM NEW.canonical_issue_id THEN
        PERFORM citizen_issues.refresh_corroboration_counts(OLD.canonical_issue_id);
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_corroborations_refresh_counts
    ON citizen_issues.corroborations;

CREATE TRIGGER trg_corroborations_refresh_counts
AFTER INSERT OR UPDATE OF canonical_issue_id, status OR DELETE
ON citizen_issues.corroborations
FOR EACH ROW
EXECUTE FUNCTION citizen_issues.trg_refresh_corroboration_counts();

CREATE OR REPLACE FUNCTION citizen_issues.trg_set_corroborations_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_corroborations_updated_at
    ON citizen_issues.corroborations;

CREATE TRIGGER trg_corroborations_updated_at
BEFORE UPDATE
ON citizen_issues.corroborations
FOR EACH ROW
EXECUTE FUNCTION citizen_issues.trg_set_corroborations_updated_at();

-- ============================================================================
-- 5. RLS
-- ============================================================================

ALTER TABLE citizen_issues.corroborations ENABLE ROW LEVEL SECURITY;
ALTER TABLE citizen_issues.corroborations FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS corroborations_tenant_isolation
    ON citizen_issues.corroborations;

CREATE POLICY corroborations_tenant_isolation
ON citizen_issues.corroborations
USING (organization_id = app.current_organization_id())
WITH CHECK (organization_id = app.current_organization_id());

ALTER TABLE citizen_issues.clustering_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE citizen_issues.clustering_operations FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS clustering_operations_tenant_isolation
    ON citizen_issues.clustering_operations;

CREATE POLICY clustering_operations_tenant_isolation
ON citizen_issues.clustering_operations
USING (organization_id = app.current_organization_id())
WITH CHECK (organization_id = app.current_organization_id());

-- ============================================================================
-- 6. TENANT-SCOPED SUMMARY VIEW
-- ============================================================================

DROP VIEW IF EXISTS citizen_issues.canonical_issue_corroboration_summary;

CREATE VIEW citizen_issues.canonical_issue_corroboration_summary
WITH (security_invoker = true)
AS
SELECT
    ci.organization_id,
    ci.id AS canonical_issue_id,
    ci.ref_number,
    ci.title,
    ci.category,
    ci.status,
    COUNT(c.id) FILTER (WHERE c.status = 'active') AS distinct_citizen_count,
    COUNT(c.id) FILTER (WHERE c.status = 'active') AS active_corroboration_count,
    COUNT(c.id) FILTER (
        WHERE c.status = 'active'
          AND c.notification_status IN ('pending','failed')
    ) AS citizens_needing_notification,
    COUNT(c.id) FILTER (
        WHERE c.status = 'active'
          AND c.closure_confirmation_status = 'pending'
    ) AS citizens_pending_closure_confirmation
FROM citizen_issues.canonical_issues ci
LEFT JOIN citizen_issues.corroborations c
       ON c.organization_id = ci.organization_id
      AND c.canonical_issue_id = ci.id
GROUP BY
    ci.organization_id, ci.id, ci.ref_number, ci.title, ci.category, ci.status;

COMMIT;

-- ============================================================================
-- END DB-015
-- ============================================================================
