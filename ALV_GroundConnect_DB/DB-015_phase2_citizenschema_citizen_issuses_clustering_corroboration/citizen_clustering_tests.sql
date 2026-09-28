-- ============================================================================
-- DB-015 TESTS: CIT-07 .. CIT-10
-- ============================================================================

BEGIN;

-- The project uses FORCE RLS. Missing organization context must fail closed.
SELECT set_config('app.organization_id', '', true);

DO $$
BEGIN
    BEGIN
        PERFORM 1 FROM citizen_issues.corroborations;
        RAISE EXCEPTION 'Expected missing tenant context to fail';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
END;
$$;

-- Test tenants.
INSERT INTO tenant_and_configuration.tenants (slug, name)
VALUES ('db015-test-a', 'DB-015 Test A'),
       ('db015-test-b', 'DB-015 Test B');

CREATE TEMP TABLE db015_ctx ON COMMIT DROP AS
SELECT
    MAX(id) FILTER (WHERE slug = 'db015-test-a') AS org_a,
    MAX(id) FILTER (WHERE slug = 'db015-test-b') AS org_b
FROM tenant_and_configuration.tenants;

SELECT set_config(
    'app.organization_id',
    (SELECT org_a::text FROM db015_ctx),
    true
);

-- Test citizens.
INSERT INTO identity_authentication_sessions.users
(
    organization_id, mobile_encrypted, mobile_hash, name_encrypted,
    preferred_language, lifecycle_status, mfa_required
)
VALUES
(
    (SELECT org_a FROM db015_ctx),
    pgp_sym_encrypt('9999000001', 'db015'),
    encode(digest('9999000001','sha256'),'hex'),
    pgp_sym_encrypt('Citizen A', 'db015'),
    'en', 'Active', false
),
(
    (SELECT org_a FROM db015_ctx),
    pgp_sym_encrypt('9999000002', 'db015'),
    encode(digest('9999000002','sha256'),'hex'),
    pgp_sym_encrypt('Citizen B', 'db015'),
    'en', 'Active', false
);

-- Canonical issues.
INSERT INTO citizen_issues.canonical_issues
(
    organization_id, ref_number, title, category, priority, location, status,
    clustering_status, clustering_method, geo_proximity_meters,
    semantic_similarity_score, clustering_suggested_at, clustering_suggested_by
)
VALUES
(
    (SELECT org_a FROM db015_ctx),
    'DB015-A',
    'Broken transformer',
    'electrical',
    'High',
    ST_SetSRID(ST_MakePoint(77.5946,12.9716),4326)::geography,
    'New',
    'suggested',
    'category_geo_semantic',
    25.50,
    0.9420,
    CURRENT_TIMESTAMP,
    (SELECT id FROM identity_authentication_sessions.users
      WHERE mobile_hash=encode(digest('9999000001','sha256'),'hex'))
),
(
    (SELECT org_a FROM db015_ctx),
    'DB015-B',
    'Transformer issue nearby',
    'electrical',
    'High',
    ST_SetSRID(ST_MakePoint(77.5950,12.9718),4326)::geography,
    'New',
    'confirmed'
);

-- CIT-07: metadata and similarity constraint.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM citizen_issues.canonical_issues
        WHERE ref_number='DB015-A'
          AND clustering_method='category_geo_semantic'
          AND geo_proximity_meters=25.50
          AND semantic_similarity_score=0.9420
    ) THEN
        RAISE EXCEPTION 'CIT-07 metadata test failed';
    END IF;
END;
$$;

DO $$
BEGIN
    BEGIN
        UPDATE citizen_issues.canonical_issues
           SET semantic_similarity_score=1.1
         WHERE ref_number='DB015-A';
        RAISE EXCEPTION 'Similarity CHECK did not reject > 1';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END;
$$;

-- A corroboration cannot identify the same person by both mechanisms.
DO $$
BEGIN
    BEGIN
        INSERT INTO citizen_issues.corroborations
        (
            organization_id, canonical_issue_id, citizen_user_id, citizen_handle
        )
        SELECT
            (SELECT org_a FROM db015_ctx),
            id,
            (SELECT id FROM identity_authentication_sessions.users
             WHERE mobile_hash=encode(digest('9999000001','sha256'),'hex')),
            'citizen-a'
        FROM citizen_issues.canonical_issues
        WHERE ref_number='DB015-A';

        RAISE EXCEPTION 'Corroboration accepted both citizen identities';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END;
$$;

-- CIT-08: one citizen can only have one active corroboration per issue.
INSERT INTO citizen_issues.corroborations
(
    organization_id, canonical_issue_id, citizen_user_id
)
SELECT
    (SELECT org_a FROM db015_ctx),
    id,
    (SELECT id FROM identity_authentication_sessions.users
     WHERE mobile_hash=encode(digest('9999000001','sha256'),'hex'))
FROM citizen_issues.canonical_issues
WHERE ref_number='DB015-A';

DO $$
BEGIN
    BEGIN
        INSERT INTO citizen_issues.corroborations
        (
            organization_id, canonical_issue_id, citizen_user_id
        )
        SELECT
            (SELECT org_a FROM db015_ctx),
            id,
            (SELECT id FROM identity_authentication_sessions.users
             WHERE mobile_hash=encode(digest('9999000001','sha256'),'hex'))
        FROM citizen_issues.canonical_issues
        WHERE ref_number='DB015-A';

        RAISE EXCEPTION 'Duplicate active citizen corroboration accepted';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;
END;
$$;

INSERT INTO citizen_issues.corroborations
(
    organization_id, canonical_issue_id, citizen_user_id
)
SELECT
    (SELECT org_a FROM db015_ctx),
    id,
    (SELECT id FROM identity_authentication_sessions.users
     WHERE mobile_hash=encode(digest('9999000002','sha256'),'hex'))
FROM citizen_issues.canonical_issues
WHERE ref_number='DB015-A';

DO $$
BEGIN
    IF (
        SELECT distinct_citizen_count
        FROM citizen_issues.canonical_issues
        WHERE ref_number='DB015-A'
    ) <> 2 THEN
        RAISE EXCEPTION 'Expected distinct citizen count = 2';
    END IF;
END;
$$;

-- CIT-10: individual notification + closure state.
UPDATE citizen_issues.corroborations
   SET notification_status='sent',
       last_notified_at=CURRENT_TIMESTAMP,
       closure_confirmation_status='confirmed',
       closure_confirmed_at=CURRENT_TIMESTAMP
 WHERE canonical_issue_id=(
       SELECT id FROM citizen_issues.canonical_issues WHERE ref_number='DB015-A'
 )
 AND citizen_user_id=(
       SELECT id FROM identity_authentication_sessions.users
       WHERE mobile_hash=encode(digest('9999000001','sha256'),'hex')
 );

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM citizen_issues.corroborations
        WHERE notification_status='sent'
          AND closure_confirmation_status='confirmed'
    ) THEN
        RAISE EXCEPTION 'CIT-10 individual tracking failed';
    END IF;
END;
$$;

-- CIT-09: suggestion, human confirmation, merge, split and reversal history.
INSERT INTO citizen_issues.clustering_operations
(
    organization_id, operation_type, source_canonical_issue_id,
    target_canonical_issue_id, category_match, geo_distance_meters,
    semantic_similarity_score, suggested_by, suggested_at
)
SELECT
    (SELECT org_a FROM db015_ctx), 'suggest', a.id, b.id, true, 52.10, 0.9310,
    (SELECT id FROM identity_authentication_sessions.users
     WHERE mobile_hash=encode(digest('9999000001','sha256'),'hex')),
    CURRENT_TIMESTAMP
FROM citizen_issues.canonical_issues a
CROSS JOIN citizen_issues.canonical_issues b
WHERE a.ref_number='DB015-A' AND b.ref_number='DB015-B';

INSERT INTO citizen_issues.clustering_operations
(
    organization_id, operation_type, source_canonical_issue_id,
    target_canonical_issue_id, confirmed_by, confirmed_at, reason
)
SELECT
    (SELECT org_a FROM db015_ctx), 'confirm', a.id, b.id,
    (SELECT id FROM identity_authentication_sessions.users
     WHERE mobile_hash=encode(digest('9999000001','sha256'),'hex')),
    CURRENT_TIMESTAMP, 'Human confirmed'
FROM citizen_issues.canonical_issues a
CROSS JOIN citizen_issues.canonical_issues b
WHERE a.ref_number='DB015-A' AND b.ref_number='DB015-B';

INSERT INTO citizen_issues.clustering_operations
(
    organization_id, operation_type, source_canonical_issue_id,
    target_canonical_issue_id, confirmed_by, confirmed_at, reason
)
SELECT
    (SELECT org_a FROM db015_ctx), 'merge', b.id, a.id,
    (SELECT id FROM identity_authentication_sessions.users
     WHERE mobile_hash=encode(digest('9999000001','sha256'),'hex')),
    CURRENT_TIMESTAMP, 'Merge history'
FROM citizen_issues.canonical_issues a
CROSS JOIN citizen_issues.canonical_issues b
WHERE a.ref_number='DB015-A' AND b.ref_number='DB015-B';

INSERT INTO citizen_issues.clustering_operations
(
    organization_id, operation_type, source_canonical_issue_id,
    target_canonical_issue_id, confirmed_by, confirmed_at, reason
)
SELECT
    (SELECT org_a FROM db015_ctx), 'split', a.id, b.id,
    (SELECT id FROM identity_authentication_sessions.users
     WHERE mobile_hash=encode(digest('9999000001','sha256'),'hex')),
    CURRENT_TIMESTAMP, 'Split history'
FROM citizen_issues.canonical_issues a
CROSS JOIN citizen_issues.canonical_issues b
WHERE a.ref_number='DB015-A' AND b.ref_number='DB015-B';

INSERT INTO citizen_issues.clustering_operations
(
    organization_id, operation_type, source_canonical_issue_id,
    target_canonical_issue_id, confirmed_by, confirmed_at, reason
)
SELECT
    (SELECT org_a FROM db015_ctx), 'reverse', a.id, b.id,
    (SELECT id FROM identity_authentication_sessions.users
     WHERE mobile_hash=encode(digest('9999000001','sha256'),'hex')),
    CURRENT_TIMESTAMP, 'Reverse prior decision'
FROM citizen_issues.canonical_issues a
CROSS JOIN citizen_issues.canonical_issues b
WHERE a.ref_number='DB015-A' AND b.ref_number='DB015-B';

DO $$
BEGIN
    IF (
        SELECT COUNT(*)
        FROM citizen_issues.clustering_operations
        WHERE operation_type IN ('suggest','confirm','merge','split','reverse')
    ) <> 5 THEN
        RAISE EXCEPTION 'CIT-09 history test failed';
    END IF;
END;
$$;

-- Tenant isolation.
SELECT set_config(
    'app.organization_id',
    (SELECT org_b::text FROM db015_ctx),
    true
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM citizen_issues.corroborations) THEN
        RAISE EXCEPTION 'CIT-08 tenant isolation failed';
    END IF;

    IF EXISTS (SELECT 1 FROM citizen_issues.clustering_operations) THEN
        RAISE EXCEPTION 'CIT-09 tenant isolation failed';
    END IF;
END;
$$;

ROLLBACK;

-- ============================================================================
-- END DB-015 TESTS
-- ============================================================================
