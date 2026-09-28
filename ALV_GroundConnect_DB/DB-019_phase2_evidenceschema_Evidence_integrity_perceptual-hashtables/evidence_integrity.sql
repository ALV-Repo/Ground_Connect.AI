-- ============================================================
-- DB-019 | Evidence Integrity & Perceptual-Hash Tables
-- SRS: EVD-01..EVD-07
-- ============================================================
-- Design note:
-- tasks_field_reports.evidence_media already exists in schema 10 and
-- already stores the core media/evidence record. This module adds the
-- normalized integrity records required by DB-019 without duplicating
-- evidence_media.
--
-- Dependencies:
--   01_tenant_and_configuration.sql
--   02_identity_authentication_sessions.sql
--   10_tasks_field_reports.sql
--
-- Tenant identity is taken from the authenticated session through
-- app.require_organization_context(); organization_id is not accepted
-- as a request-time authorization parameter.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS evidence_integrity;


-- ============================================================
-- EVD-01 / EVD-03 / EVD-06
-- STRENGTHEN EXISTING CANONICAL EVIDENCE / REPORT TABLES
-- ============================================================

-- EVD-01: gallery uploads are explicitly lower-trust.
ALTER TABLE tasks_field_reports.evidence_media
    DROP CONSTRAINT IF EXISTS chk_evidence_media_trust_class;

UPDATE tasks_field_reports.evidence_media
SET trust_class = 'lower_trust_gallery'
WHERE capture_method = 'gallery_upload'
  AND trust_class <> 'lower_trust_gallery';

ALTER TABLE tasks_field_reports.evidence_media
    ADD CONSTRAINT chk_evidence_media_trust_class
    CHECK (
        trust_class IN (
            'attested',
            'attested_offline',
            'unattested',
            'lower_trust_gallery'
        )
    );

ALTER TABLE tasks_field_reports.evidence_media
    DROP CONSTRAINT IF EXISTS chk_evidence_media_gallery_lower_trust;

ALTER TABLE tasks_field_reports.evidence_media
    ADD CONSTRAINT chk_evidence_media_gallery_lower_trust
    CHECK (
        (capture_method = 'gallery_upload' AND trust_class = 'lower_trust_gallery')
        OR
        (capture_method <> 'gallery_upload' AND trust_class <> 'lower_trust_gallery')
    );

CREATE INDEX IF NOT EXISTS idx_evidence_media_gallery_lower_trust
    ON tasks_field_reports.evidence_media (organization_id, report_id)
    WHERE trust_class = 'lower_trust_gallery';

-- EVD-03: record concrete tamper evidence/reason on the canonical media row.
ALTER TABLE tasks_field_reports.evidence_media
    ADD COLUMN IF NOT EXISTS tamper_detected_at TIMESTAMPTZ NULL;

ALTER TABLE tasks_field_reports.evidence_media
    ADD COLUMN IF NOT EXISTS tamper_reason TEXT NULL;

ALTER TABLE tasks_field_reports.evidence_media
    ADD COLUMN IF NOT EXISTS tamper_expected_hash TEXT NULL;

ALTER TABLE tasks_field_reports.evidence_media
    ADD COLUMN IF NOT EXISTS tamper_observed_hash TEXT NULL;

UPDATE tasks_field_reports.evidence_media
SET tamper_detected_at = COALESCE(tamper_detected_at, uploaded_at),
    tamper_reason = COALESCE(
        tamper_reason,
        'tampered status was recorded before DB-019 tamper-reason fields were introduced'
    )
WHERE tampered = TRUE;

ALTER TABLE tasks_field_reports.evidence_media
    DROP CONSTRAINT IF EXISTS chk_evidence_media_tamper_evidence;

ALTER TABLE tasks_field_reports.evidence_media
    ADD CONSTRAINT chk_evidence_media_tamper_evidence
    CHECK (
        tampered = FALSE
        OR (
            tamper_detected_at IS NOT NULL
            AND tamper_reason IS NOT NULL
            AND length(btrim(tamper_reason)) > 0
        )
    );

-- EVD-06: explicit named reason storage for human integrity review.
ALTER TABLE tasks_field_reports.field_reports
    ADD COLUMN IF NOT EXISTS integrity_reasons JSONB
    NOT NULL DEFAULT '[]'::jsonb;

UPDATE tasks_field_reports.field_reports
SET integrity_reasons = CASE
    WHEN jsonb_typeof(integrity_flags) = 'array'
         AND jsonb_array_length(integrity_flags) > 0
    THEN integrity_flags
    WHEN integrity_status = 'verified'
    THEN '[]'::jsonb
    ELSE '["integrity_reason_not_recorded_in_legacy_schema"]'::jsonb
END
WHERE integrity_reasons = '[]'::jsonb;

ALTER TABLE tasks_field_reports.field_reports
    DROP CONSTRAINT IF EXISTS chk_field_reports_integrity_reasons_array;

ALTER TABLE tasks_field_reports.field_reports
    ADD CONSTRAINT chk_field_reports_integrity_reasons_array
    CHECK (jsonb_typeof(integrity_reasons) = 'array');

ALTER TABLE tasks_field_reports.field_reports
    DROP CONSTRAINT IF EXISTS chk_field_reports_integrity_reasons_required;

ALTER TABLE tasks_field_reports.field_reports
    ADD CONSTRAINT chk_field_reports_integrity_reasons_required
    CHECK (
        integrity_status = 'verified'
        OR jsonb_array_length(integrity_reasons) > 0
    );

CREATE INDEX IF NOT EXISTS idx_field_reports_integrity_status
    ON tasks_field_reports.field_reports (organization_id, integrity_status);


-- ============================================================
-- EVD-02 / EVD-03
-- VERIFIED ATTESTATION RECORD
-- ============================================================

CREATE TABLE evidence_integrity.evidence_attestations (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    evidence_id UUID NOT NULL,

    device_id UUID NULL,
    device_key_id TEXT NULL,
    signature_algorithm TEXT NULL,
    signed_media_hash TEXT NOT NULL,
    attestation_signature TEXT NULL,

    captured_at TIMESTAMPTZ NOT NULL,
    attested_at TIMESTAMPTZ NULL,
    verified_at TIMESTAMPTZ NULL,

    capture_location_lat NUMERIC(10,7) NULL,
    capture_location_lng NUMERIC(10,7) NULL,
    location_accuracy_m NUMERIC(10,2) NULL,

    capture_mode TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'pending',

    verification_reason TEXT NULL,
    verified_by UUID NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_evidence_attestations
        PRIMARY KEY (id),

    CONSTRAINT fk_evidence_attestations_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_evidence_attestations_evidence
        FOREIGN KEY (evidence_id)
        REFERENCES tasks_field_reports.evidence_media(id),

    CONSTRAINT fk_evidence_attestations_device
        FOREIGN KEY (device_id)
        REFERENCES identity_authentication_sessions.devices(id),

    CONSTRAINT fk_evidence_attestations_verified_by
        FOREIGN KEY (verified_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_evidence_attestations_capture_mode
        CHECK (
            capture_mode IN (
                'in_app_camera',
                'in_app_recorder',
                'offline_capture',
                'gallery_upload'
            )
        ),

    CONSTRAINT chk_evidence_attestations_verification_status
        CHECK (
            verification_status IN (
                'pending',
                'attested',
                'attested_offline',
                'unattested',
                'tampered'
            )
        ),

    CONSTRAINT chk_evidence_attestations_location_accuracy
        CHECK (
            location_accuracy_m IS NULL
            OR location_accuracy_m >= 0
        ),

    CONSTRAINT chk_evidence_attestations_hash
        CHECK (
            signed_media_hash ~ '^[0-9a-fA-F]{64}$'
        ),

    CONSTRAINT chk_evidence_attestations_verified_metadata
        CHECK (
            verification_status NOT IN ('attested', 'attested_offline')
            OR (
                device_key_id IS NOT NULL
                AND length(btrim(device_key_id)) > 0
                AND attestation_signature IS NOT NULL
                AND length(btrim(attestation_signature)) > 0
            )
        )
);

CREATE UNIQUE INDEX uq_evidence_attestations_evidence
    ON evidence_integrity.evidence_attestations
    (organization_id, evidence_id);

CREATE INDEX idx_evidence_attestations_device
    ON evidence_integrity.evidence_attestations
    (organization_id, device_id);

CREATE INDEX idx_evidence_attestations_captured_at
    ON evidence_integrity.evidence_attestations
    (organization_id, captured_at);

CREATE INDEX idx_evidence_attestations_status
    ON evidence_integrity.evidence_attestations
    (organization_id, verification_status);


-- ============================================================
-- EVD-04
-- PERCEPTUAL HASH STORE
-- ============================================================

CREATE TABLE evidence_integrity.evidence_perceptual_hashes (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    evidence_id UUID NOT NULL,

    hash_algorithm TEXT NOT NULL,
    phash TEXT NOT NULL,
    hash_bits SMALLINT NOT NULL DEFAULT 64,

    duplicate_match_status TEXT NOT NULL DEFAULT 'not_checked',
    matched_evidence_id UUID NULL,
    hamming_distance INTEGER NULL,
    match_threshold SMALLINT NULL,

    computed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_evidence_perceptual_hashes
        PRIMARY KEY (id),

    CONSTRAINT fk_evidence_perceptual_hashes_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_evidence_perceptual_hashes_evidence
        FOREIGN KEY (evidence_id)
        REFERENCES tasks_field_reports.evidence_media(id),

    CONSTRAINT fk_evidence_perceptual_hashes_matched_evidence
        FOREIGN KEY (matched_evidence_id)
        REFERENCES tasks_field_reports.evidence_media(id),

    CONSTRAINT chk_evidence_perceptual_hashes_algorithm
        CHECK (
            hash_algorithm IN (
                'phash',
                'dhash',
                'ahash'
            )
        ),

    CONSTRAINT chk_evidence_perceptual_hashes_hash_bits
        CHECK (hash_bits > 0),

    CONSTRAINT chk_evidence_perceptual_hashes_match_status
        CHECK (
            duplicate_match_status IN (
                'not_checked',
                'no_match',
                'exact_match',
                'near_match'
            )
        ),

    CONSTRAINT chk_evidence_perceptual_hashes_hamming_distance
        CHECK (
            hamming_distance IS NULL
            OR hamming_distance >= 0
        ),

    CONSTRAINT chk_evidence_perceptual_hashes_threshold
        CHECK (
            match_threshold IS NULL
            OR match_threshold >= 0
        ),

    CONSTRAINT chk_evidence_perceptual_hashes_match_target
        CHECK (
            duplicate_match_status IN ('exact_match', 'near_match')
            AND matched_evidence_id IS NOT NULL
            OR duplicate_match_status IN ('not_checked', 'no_match')
        )
);

CREATE INDEX idx_evidence_perceptual_hashes_lookup
    ON evidence_integrity.evidence_perceptual_hashes
    (organization_id, hash_algorithm, phash);

CREATE INDEX idx_evidence_perceptual_hashes_evidence
    ON evidence_integrity.evidence_perceptual_hashes
    (organization_id, evidence_id);

CREATE INDEX idx_evidence_perceptual_hashes_match
    ON evidence_integrity.evidence_perceptual_hashes
    (organization_id, matched_evidence_id)
    WHERE matched_evidence_id IS NOT NULL;


-- ============================================================
-- EVD-05
-- NAMED COHERENCE-CHECK RESULTS
-- ============================================================

CREATE TABLE evidence_integrity.evidence_coherence_checks (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    evidence_id UUID NOT NULL,
    report_id UUID NOT NULL,

    check_type TEXT NOT NULL,
    result TEXT NOT NULL,

    expected_value JSONB NULL,
    observed_value JSONB NULL,
    deviation_value NUMERIC NULL,

    checked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason TEXT NULL,

    CONSTRAINT pk_evidence_coherence_checks
        PRIMARY KEY (id),

    CONSTRAINT fk_evidence_coherence_checks_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_evidence_coherence_checks_evidence
        FOREIGN KEY (evidence_id)
        REFERENCES tasks_field_reports.evidence_media(id),

    CONSTRAINT fk_evidence_coherence_checks_report
        FOREIGN KEY (report_id)
        REFERENCES tasks_field_reports.field_reports(id),

    CONSTRAINT chk_evidence_coherence_checks_type
        CHECK (
            check_type IN (
                'capture_location_vs_assigned_unit',
                'capture_time_vs_task_window',
                'travel_plausibility'
            )
        ),

    CONSTRAINT chk_evidence_coherence_checks_result
        CHECK (
            result IN (
                'passed',
                'failed',
                'not_evaluable'
            )
        ),

    CONSTRAINT chk_evidence_coherence_checks_deviation
        CHECK (
            deviation_value IS NULL
            OR deviation_value >= 0
        )
);

CREATE INDEX idx_evidence_coherence_checks_evidence
    ON evidence_integrity.evidence_coherence_checks
    (organization_id, evidence_id);

CREATE INDEX idx_evidence_coherence_checks_report
    ON evidence_integrity.evidence_coherence_checks
    (organization_id, report_id);

CREATE INDEX idx_evidence_coherence_checks_failed
    ON evidence_integrity.evidence_coherence_checks
    (organization_id, check_type, checked_at)
    WHERE result = 'failed';


-- ============================================================
-- EVD-06 / EVD-07
-- EVIDENCE-MIX SUMMARY VIEW
-- ============================================================
-- This view exposes the evidence mix needed by dashboards/AI
-- summaries. It does not itself make a worker penalty decision.

CREATE VIEW evidence_integrity.field_report_evidence_mix
WITH (security_invoker = true) AS
WITH evidence_counts AS (
    SELECT
        fr.organization_id,
        fr.id AS report_id,
        COUNT(em.id) AS evidence_count,
        COUNT(em.id) FILTER (
            WHERE em.attestation_status IN ('attested', 'attested_offline')
        ) AS attested_count,
        COUNT(em.id) FILTER (
            WHERE em.attestation_status = 'unattested'
               OR em.trust_class = 'lower_trust_gallery'
        ) AS unattested_count,
        COUNT(em.id) FILTER (
            WHERE em.attestation_status = 'tampered'
               OR em.tampered = TRUE
               OR EXISTS (
                    SELECT 1
                    FROM evidence_integrity.evidence_coherence_checks ecc
                    WHERE ecc.organization_id = em.organization_id
                      AND ecc.evidence_id = em.id
                      AND ecc.result = 'failed'
               )
        ) AS flagged_count
    FROM tasks_field_reports.field_reports fr
    LEFT JOIN tasks_field_reports.evidence_media em
        ON em.organization_id = fr.organization_id
       AND em.report_id = fr.id
    GROUP BY
        fr.organization_id,
        fr.id
)
SELECT
    organization_id,
    report_id,
    evidence_count,
    attested_count,
    unattested_count,
    flagged_count,
    ROUND(100.0 * attested_count / NULLIF(evidence_count, 0), 2)
        AS attested_pct,
    ROUND(100.0 * unattested_count / NULLIF(evidence_count, 0), 2)
        AS unattested_pct,
    ROUND(100.0 * flagged_count / NULLIF(evidence_count, 0), 2)
        AS flagged_pct
FROM evidence_counts;


-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE evidence_integrity.evidence_attestations
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE evidence_integrity.evidence_attestations
    FORCE ROW LEVEL SECURITY;

CREATE POLICY evidence_attestations_tenant_isolation
ON evidence_integrity.evidence_attestations
USING (
    organization_id = app.require_organization_context()
)
WITH CHECK (
    organization_id = app.require_organization_context()
);


ALTER TABLE evidence_integrity.evidence_perceptual_hashes
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE evidence_integrity.evidence_perceptual_hashes
    FORCE ROW LEVEL SECURITY;

CREATE POLICY evidence_perceptual_hashes_tenant_isolation
ON evidence_integrity.evidence_perceptual_hashes
USING (
    organization_id = app.require_organization_context()
)
WITH CHECK (
    organization_id = app.require_organization_context()
);


ALTER TABLE evidence_integrity.evidence_coherence_checks
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE evidence_integrity.evidence_coherence_checks
    FORCE ROW LEVEL SECURITY;

CREATE POLICY evidence_coherence_checks_tenant_isolation
ON evidence_integrity.evidence_coherence_checks
USING (
    organization_id = app.require_organization_context()
)
WITH CHECK (
    organization_id = app.require_organization_context()
);


-- ============================================================
-- EVD-01 / EVD-02 / EVD-03 IMPLEMENTATION NOTE
-- ============================================================
-- Existing tasks_field_reports.evidence_media remains the
-- canonical media record.
--
-- EVD-01:
--   capture_method distinguishes in-app capture, offline capture,
--   and gallery upload. Application policy must prevent evidence-class
--   camera/recorder capture from being silently represented as gallery
--   media.
--
-- EVD-02:
--   evidence_attestations stores the device key identifier, captured
--   timestamp, coarse coordinates, media hash, signature and server
--   verification status.
--
-- EVD-03:
--   server verification must compare the received media hash with
--   signed_media_hash and set verification_status='tampered' when
--   signature/hash verification fails.
--
-- EVD-04:
--   perceptual-hash computation and Hamming-distance comparison are
--   application/worker responsibilities. The database stores the
--   resulting hash and cited prior evidence within the same tenant.
--
-- EVD-05:
--   each coherence check is stored as a named result. Failed checks
--   are queryable individually.
--
-- EVD-06:
--   field_reports.integrity_status remains the human-review outcome
--   (verified/unverified/inconsistent). No automatic worker penalty
--   is implemented here.
--
-- EVD-07:
--   field_report_evidence_mix exposes attested/unattested/flagged
--   counts for downstream dashboard and AI-summary layers.
