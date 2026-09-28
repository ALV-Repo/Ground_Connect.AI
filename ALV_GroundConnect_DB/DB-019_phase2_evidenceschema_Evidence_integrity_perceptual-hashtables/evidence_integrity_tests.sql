-- ============================================================
-- DB-019 | Evidence Integrity & Perceptual-Hash Tests
-- ============================================================

DO $$
DECLARE
    v_missing INTEGER;
BEGIN

    -- Schema exists
    SELECT COUNT(*)
      INTO v_missing
      FROM information_schema.schemata
     WHERE schema_name = 'evidence_integrity';

    IF v_missing <> 1 THEN
        RAISE EXCEPTION 'DB-019 test failed: evidence_integrity schema missing';
    END IF;

    -- Required tables exist
    SELECT COUNT(*)
      INTO v_missing
      FROM information_schema.tables
     WHERE table_schema = 'evidence_integrity'
       AND table_name IN (
           'evidence_attestations',
           'evidence_perceptual_hashes',
           'evidence_coherence_checks'
       );

    IF v_missing <> 3 THEN
        RAISE EXCEPTION 'DB-019 test failed: required integrity tables missing';
    END IF;

    -- EVD-02 attestation columns
    SELECT COUNT(*)
      INTO v_missing
      FROM information_schema.columns
     WHERE table_schema = 'evidence_integrity'
       AND table_name = 'evidence_attestations'
       AND column_name IN (
           'device_key_id',
           'captured_at',
           'capture_location_lat',
           'capture_location_lng',
           'signed_media_hash',
           'attestation_signature',
           'verification_status'
       );

    IF v_missing <> 7 THEN
        RAISE EXCEPTION 'DB-019 test failed: attestation metadata incomplete';
    END IF;

    -- EVD-02: verified attestations must require device key and signature.
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class r ON r.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = r.relnamespace
        WHERE n.nspname = 'evidence_integrity'
          AND r.relname = 'evidence_attestations'
          AND c.conname = 'chk_evidence_attestations_verified_metadata'
    ) THEN
        RAISE EXCEPTION 'DB-019 test failed: verified attestation metadata rule missing';
    END IF;

    -- EVD-01 business rule: gallery_upload must map to lower_trust_gallery.
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class r ON r.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = r.relnamespace
        WHERE n.nspname = 'tasks_field_reports'
          AND r.relname = 'evidence_media'
          AND c.conname = 'chk_evidence_media_gallery_lower_trust'
          AND pg_get_constraintdef(c.oid) LIKE '%gallery_upload%'
          AND pg_get_constraintdef(c.oid) LIKE '%lower_trust_gallery%'
    ) THEN
        RAISE EXCEPTION 'DB-019 test failed: gallery lower-trust rule definition invalid';
    END IF;

    -- EVD-04 perceptual hash store
    SELECT COUNT(*)
      INTO v_missing
      FROM information_schema.columns
     WHERE table_schema = 'evidence_integrity'
       AND table_name = 'evidence_perceptual_hashes'
       AND column_name IN (
           'phash',
           'matched_evidence_id',
           'hamming_distance',
           'duplicate_match_status'
       );

    IF v_missing <> 4 THEN
        RAISE EXCEPTION 'DB-019 test failed: perceptual-hash fields incomplete';
    END IF;

    -- EVD-05 named coherence checks
    SELECT COUNT(*)
      INTO v_missing
      FROM information_schema.columns
     WHERE table_schema = 'evidence_integrity'
       AND table_name = 'evidence_coherence_checks'
       AND column_name IN (
           'check_type',
           'result',
           'expected_value',
           'observed_value',
           'reason'
       );

    IF v_missing <> 5 THEN
        RAISE EXCEPTION 'DB-019 test failed: coherence-check fields incomplete';
    END IF;

    -- RLS must be enabled
    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'evidence_integrity'
          AND c.relname = 'evidence_attestations'
          AND c.relrowsecurity
          AND c.relforcerowsecurity
    ) THEN
        RAISE EXCEPTION 'DB-019 test failed: RLS/FORCE RLS missing on evidence_attestations';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'evidence_integrity'
          AND c.relname = 'evidence_perceptual_hashes'
          AND c.relrowsecurity
          AND c.relforcerowsecurity
    ) THEN
        RAISE EXCEPTION 'DB-019 test failed: RLS/FORCE RLS missing on evidence_perceptual_hashes';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'evidence_integrity'
          AND c.relname = 'evidence_coherence_checks'
          AND c.relrowsecurity
          AND c.relforcerowsecurity
    ) THEN
        RAISE EXCEPTION 'DB-019 test failed: RLS/FORCE RLS missing on evidence_coherence_checks';
    END IF;

    -- EVD-07 view exists
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.views
        WHERE table_schema = 'evidence_integrity'
          AND table_name = 'field_report_evidence_mix'
    ) THEN
        RAISE EXCEPTION 'DB-019 test failed: evidence mix view missing';
    END IF;



    -- EVD-01: explicit gallery lower-trust classification must exist.
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class r ON r.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = r.relnamespace
        WHERE n.nspname = 'tasks_field_reports'
          AND r.relname = 'evidence_media'
          AND c.conname = 'chk_evidence_media_gallery_lower_trust'
    ) THEN
        RAISE EXCEPTION 'DB-019 test failed: gallery lower-trust business rule missing';
    END IF;

    -- EVD-03: tamper reason/evidence must exist and be enforced.
    SELECT COUNT(*)
      INTO v_missing
      FROM information_schema.columns
     WHERE table_schema = 'tasks_field_reports'
       AND table_name = 'evidence_media'
       AND column_name IN (
           'tamper_detected_at',
           'tamper_reason',
           'tamper_expected_hash',
           'tamper_observed_hash'
       );

    IF v_missing <> 4 THEN
        RAISE EXCEPTION 'DB-019 test failed: tamper evidence fields incomplete';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class r ON r.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = r.relnamespace
        WHERE n.nspname = 'tasks_field_reports'
          AND r.relname = 'evidence_media'
          AND c.conname = 'chk_evidence_media_tamper_evidence'
    ) THEN
        RAISE EXCEPTION 'DB-019 test failed: tamper evidence constraint missing';
    END IF;

    -- EVD-06: integrity status and explicit reason storage.
    SELECT COUNT(*)
      INTO v_missing
      FROM information_schema.columns
     WHERE table_schema = 'tasks_field_reports'
       AND table_name = 'field_reports'
       AND column_name IN ('integrity_status', 'integrity_flags', 'integrity_reasons');

    IF v_missing <> 3 THEN
        RAISE EXCEPTION 'DB-019 test failed: field-report integrity metadata incomplete';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class r ON r.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = r.relnamespace
        WHERE n.nspname = 'tasks_field_reports'
          AND r.relname = 'field_reports'
          AND c.conname = 'chk_field_reports_integrity_reasons_required'
    ) THEN
        RAISE EXCEPTION 'DB-019 test failed: integrity reason requirement missing';
    END IF;

    -- EVD-07: percentages must be exposed by the evidence-mix view.
    SELECT COUNT(*)
      INTO v_missing
      FROM information_schema.columns
     WHERE table_schema = 'evidence_integrity'
       AND table_name = 'field_report_evidence_mix'
       AND column_name IN ('attested_pct', 'unattested_pct', 'flagged_pct');

    IF v_missing <> 3 THEN
        RAISE EXCEPTION 'DB-019 test failed: evidence-mix percentages missing';
    END IF;

    RAISE NOTICE 'DB-019 structural tests passed.';
END $$;
