-- ============================================================
-- DB-011 — BACKUP & RECOVERY
-- ============================================================
-- Purpose:
--   Database-side control and evidence model for:
--     * continuous WAL archiving
--     * daily backups
--     * encrypted backup evidence
--     * production-credential isolation evidence
--     * PITR / recovery-drill evidence
--     * RPO <= 15 minutes
--     * RTO <= 60 minutes
--
-- IMPORTANT:
--   This schema does NOT perform physical backups, WAL archiving,
--   object-storage operations, or PITR itself.
--
--   PostgreSQL/backup infrastructure performs those operations.
--   This schema records their evidence and enforces database-side
--   integrity rules.
--
-- ============================================================

CREATE SCHEMA IF NOT EXISTS backup_recovery;

-- ============================================================
-- 1. BACKUP POLICIES
-- ============================================================

CREATE TABLE backup_recovery.backup_policies (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,

    backup_frequency TEXT NOT NULL DEFAULT 'daily',
    wal_archiving_required BOOLEAN NOT NULL DEFAULT TRUE,
    point_in_time_recovery_required BOOLEAN NOT NULL DEFAULT TRUE,
    encryption_required BOOLEAN NOT NULL DEFAULT TRUE,
    credential_isolation_required BOOLEAN NOT NULL DEFAULT TRUE,

    target_rpo_minutes INTEGER NOT NULL DEFAULT 15,
    target_rto_minutes INTEGER NOT NULL DEFAULT 60,

    quarterly_drill_required BOOLEAN NOT NULL DEFAULT TRUE,

    production_ready BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_backup_policies
        PRIMARY KEY (id),

    CONSTRAINT fk_backup_policies_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT uq_backup_policies_organization
        UNIQUE (organization_id),

    CONSTRAINT chk_backup_policies_frequency
        CHECK (backup_frequency = 'daily'),

    CONSTRAINT chk_backup_policies_rpo
        CHECK (
            target_rpo_minutes > 0
            AND target_rpo_minutes <= 15
        ),

    CONSTRAINT chk_backup_policies_rto
        CHECK (
            target_rto_minutes > 0
            AND target_rto_minutes <= 60
        )
);

-- ============================================================
-- 2. BACKUP RUNS
-- ============================================================

CREATE TABLE backup_recovery.backup_runs (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    backup_policy_id UUID NOT NULL,

    backup_type TEXT NOT NULL,

    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,

    encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    credential_isolated BOOLEAN NOT NULL DEFAULT FALSE,

    storage_location_reference TEXT,
    backup_reference TEXT,

    verification_status TEXT NOT NULL DEFAULT 'pending',
    verified_at TIMESTAMPTZ,

    status TEXT NOT NULL DEFAULT 'started',
    failure_reason TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_backup_runs
        PRIMARY KEY (id),

    CONSTRAINT fk_backup_runs_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_backup_runs_policy
        FOREIGN KEY (backup_policy_id)
        REFERENCES backup_recovery.backup_policies(id),

    CONSTRAINT chk_backup_runs_type
        CHECK (
            backup_type IN (
                'daily_full',
                'base_backup',
                'manual'
            )
        ),

    CONSTRAINT chk_backup_runs_completed_after_started
        CHECK (
            completed_at IS NULL
            OR completed_at >= started_at
        ),

    CONSTRAINT chk_backup_runs_verification_status
        CHECK (
            verification_status IN (
                'pending',
                'verified',
                'failed'
            )
        ),

    CONSTRAINT chk_backup_runs_status
        CHECK (
            status IN (
                'started',
                'completed',
                'failed'
            )
        ),

    CONSTRAINT chk_backup_runs_verified_timestamp
        CHECK (
            verification_status <> 'verified'
            OR verified_at IS NOT NULL
        ),

    CONSTRAINT chk_backup_runs_completed_requirements
        CHECK (
            status <> 'completed'
            OR (
                completed_at IS NOT NULL
                AND encrypted = TRUE
                AND credential_isolated = TRUE
                AND verification_status = 'verified'
                AND verified_at IS NOT NULL
            )
        )
);

CREATE INDEX idx_backup_runs_organization_id
    ON backup_recovery.backup_runs (organization_id);

CREATE INDEX idx_backup_runs_policy_time
    ON backup_recovery.backup_runs
    (backup_policy_id, started_at DESC);

CREATE INDEX idx_backup_runs_verification
    ON backup_recovery.backup_runs
    (organization_id, verification_status);

CREATE INDEX idx_backup_runs_completed
    ON backup_recovery.backup_runs
    (organization_id, completed_at DESC)
    WHERE status = 'completed';

-- ============================================================
-- 3. WAL ARCHIVE STATUS
-- ============================================================

CREATE TABLE backup_recovery.wal_archive_status (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,

    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_archived_at TIMESTAMPTZ,

    archive_lag_seconds INTEGER,

    archive_status TEXT NOT NULL,

    latest_wal_reference TEXT,
    observation_source TEXT NOT NULL,

    failure_reason TEXT,

    CONSTRAINT pk_wal_archive_status
        PRIMARY KEY (id),

    CONSTRAINT fk_wal_archive_status_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT chk_wal_archive_lag
        CHECK (
            archive_lag_seconds IS NULL
            OR archive_lag_seconds >= 0
        ),

    CONSTRAINT chk_wal_archive_status
        CHECK (
            archive_status IN (
                'healthy',
                'lagging',
                'failed',
                'unknown'
            )
        ),

    CONSTRAINT chk_wal_archive_observation_source
        CHECK (
            observation_source IN (
                'postgresql',
                'backup_service',
                'monitoring',
                'operator'
            )
        )
);

CREATE INDEX idx_wal_archive_status_organization_time
    ON backup_recovery.wal_archive_status
    (organization_id, observed_at DESC);

CREATE INDEX idx_wal_archive_status_health
    ON backup_recovery.wal_archive_status
    (organization_id, archive_status, observed_at DESC);

-- ============================================================
-- 4. RECOVERY DRILLS
-- ============================================================

CREATE TABLE backup_recovery.recovery_drills (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,

    backup_run_id UUID,

    drill_type TEXT NOT NULL,

    started_at TIMESTAMPTZ NOT NULL,
    recovery_completed_at TIMESTAMPTZ,

    recovery_target_time TIMESTAMPTZ,
    recovered_to_time TIMESTAMPTZ,

    measured_rpo_minutes NUMERIC(12,2),
    measured_rto_minutes NUMERIC(12,2),

    pitr_used BOOLEAN NOT NULL DEFAULT FALSE,
    backup_verified_before_drill BOOLEAN NOT NULL DEFAULT FALSE,

    result TEXT NOT NULL DEFAULT 'in_progress',

    evidence_reference TEXT,
    failure_reason TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_recovery_drills
        PRIMARY KEY (id),

    CONSTRAINT fk_recovery_drills_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_recovery_drills_backup_run
        FOREIGN KEY (backup_run_id)
        REFERENCES backup_recovery.backup_runs(id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_recovery_drills_type
        CHECK (
            drill_type IN (
                'pre_production',
                'quarterly',
                'ad_hoc'
            )
        ),

    CONSTRAINT chk_recovery_drills_completed_after_started
        CHECK (
            recovery_completed_at IS NULL
            OR recovery_completed_at >= started_at
        ),

    CONSTRAINT chk_recovery_drills_rpo
        CHECK (
            measured_rpo_minutes IS NULL
            OR measured_rpo_minutes >= 0
        ),

    CONSTRAINT chk_recovery_drills_rto
        CHECK (
            measured_rto_minutes IS NULL
            OR measured_rto_minutes >= 0
        ),

    CONSTRAINT chk_recovery_drills_result
        CHECK (
            result IN (
                'in_progress',
                'passed',
                'failed'
            )
        ),

    CONSTRAINT chk_recovery_drills_passed
        CHECK (
            result <> 'passed'
            OR (
                recovery_completed_at IS NOT NULL
                AND measured_rpo_minutes IS NOT NULL
                AND measured_rpo_minutes <= 15
                AND measured_rto_minutes IS NOT NULL
                AND measured_rto_minutes <= 60
                AND backup_verified_before_drill = TRUE
                AND evidence_reference IS NOT NULL
            )
        )
);

CREATE INDEX idx_recovery_drills_organization_time
    ON backup_recovery.recovery_drills
    (organization_id, started_at DESC);

CREATE INDEX idx_recovery_drills_result
    ON backup_recovery.recovery_drills
    (organization_id, result);

CREATE INDEX idx_recovery_drills_type
    ON backup_recovery.recovery_drills
    (organization_id, drill_type, started_at DESC);

-- ============================================================
-- 5. FUNCTION: RECORD BACKUP RUN
-- ============================================================

CREATE OR REPLACE FUNCTION backup_recovery.record_backup_run(
    p_organization_id UUID,
    p_backup_policy_id UUID,
    p_backup_type TEXT,
    p_started_at TIMESTAMPTZ,
    p_completed_at TIMESTAMPTZ DEFAULT NULL,
    p_encrypted BOOLEAN DEFAULT FALSE,
    p_credential_isolated BOOLEAN DEFAULT FALSE,
    p_storage_location_reference TEXT DEFAULT NULL,
    p_backup_reference TEXT DEFAULT NULL,
    p_verification_status TEXT DEFAULT 'pending',
    p_verified_at TIMESTAMPTZ DEFAULT NULL,
    p_status TEXT DEFAULT 'started',
    p_failure_reason TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_backup_id UUID;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM tenant_and_configuration.tenants t
        WHERE t.id = p_organization_id
    ) THEN
        RAISE EXCEPTION 'Organization % does not exist', p_organization_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM backup_recovery.backup_policies bp
        WHERE bp.id = p_backup_policy_id
          AND bp.organization_id = p_organization_id
    ) THEN
        RAISE EXCEPTION
            'Backup policy % does not belong to organization %',
            p_backup_policy_id, p_organization_id;
    END IF;

    IF p_status = 'completed' THEN
        IF p_completed_at IS NULL THEN
            RAISE EXCEPTION 'Completed backup requires completed_at';
        END IF;

        IF p_encrypted IS NOT TRUE THEN
            RAISE EXCEPTION 'Completed backup must be encrypted';
        END IF;

        IF p_credential_isolated IS NOT TRUE THEN
            RAISE EXCEPTION
                'Completed backup must use isolated credentials';
        END IF;

        IF p_verification_status <> 'verified' THEN
            RAISE EXCEPTION
                'Completed backup must have verification_status=verified';
        END IF;

        IF p_verified_at IS NULL THEN
            RAISE EXCEPTION 'Verified backup requires verified_at';
        END IF;
    END IF;

    INSERT INTO backup_recovery.backup_runs (
        organization_id,
        backup_policy_id,
        backup_type,
        started_at,
        completed_at,
        encrypted,
        credential_isolated,
        storage_location_reference,
        backup_reference,
        verification_status,
        verified_at,
        status,
        failure_reason
    )
    VALUES (
        p_organization_id,
        p_backup_policy_id,
        p_backup_type,
        p_started_at,
        p_completed_at,
        p_encrypted,
        p_credential_isolated,
        p_storage_location_reference,
        p_backup_reference,
        p_verification_status,
        p_verified_at,
        p_status,
        p_failure_reason
    )
    RETURNING id INTO v_backup_id;

    RETURN v_backup_id;
END;
$$;

-- ============================================================
-- 6. FUNCTION: RECORD WAL ARCHIVE STATUS
-- ============================================================

CREATE OR REPLACE FUNCTION backup_recovery.record_wal_archive_status(
    p_organization_id UUID,
    p_observed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    p_last_archived_at TIMESTAMPTZ DEFAULT NULL,
    p_archive_lag_seconds INTEGER DEFAULT NULL,
    p_archive_status TEXT DEFAULT 'unknown',
    p_latest_wal_reference TEXT DEFAULT NULL,
    p_observation_source TEXT DEFAULT 'monitoring',
    p_failure_reason TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_status_id UUID;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM tenant_and_configuration.tenants t
        WHERE t.id = p_organization_id
    ) THEN
        RAISE EXCEPTION 'Organization % does not exist', p_organization_id;
    END IF;

    INSERT INTO backup_recovery.wal_archive_status (
        organization_id,
        observed_at,
        last_archived_at,
        archive_lag_seconds,
        archive_status,
        latest_wal_reference,
        observation_source,
        failure_reason
    )
    VALUES (
        p_organization_id,
        p_observed_at,
        p_last_archived_at,
        p_archive_lag_seconds,
        p_archive_status,
        p_latest_wal_reference,
        p_observation_source,
        p_failure_reason
    )
    RETURNING id INTO v_status_id;

    RETURN v_status_id;
END;
$$;

-- ============================================================
-- 7. FUNCTION: RECORD RECOVERY DRILL
-- ============================================================

CREATE OR REPLACE FUNCTION backup_recovery.record_recovery_drill(
    p_organization_id UUID,
    p_backup_run_id UUID DEFAULT NULL,
    p_drill_type TEXT DEFAULT 'ad_hoc',
    p_started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    p_recovery_completed_at TIMESTAMPTZ DEFAULT NULL,
    p_recovery_target_time TIMESTAMPTZ DEFAULT NULL,
    p_recovered_to_time TIMESTAMPTZ DEFAULT NULL,
    p_measured_rpo_minutes NUMERIC(12,2) DEFAULT NULL,
    p_measured_rto_minutes NUMERIC(12,2) DEFAULT NULL,
    p_pitr_used BOOLEAN DEFAULT FALSE,
    p_backup_verified_before_drill BOOLEAN DEFAULT FALSE,
    p_result TEXT DEFAULT 'in_progress',
    p_evidence_reference TEXT DEFAULT NULL,
    p_failure_reason TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_drill_id UUID;
    v_backup_verified BOOLEAN;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM tenant_and_configuration.tenants t
        WHERE t.id = p_organization_id
    ) THEN
        RAISE EXCEPTION 'Organization % does not exist', p_organization_id;
    END IF;

    IF p_backup_run_id IS NOT NULL THEN
        SELECT (
            br.status = 'completed'
            AND br.verification_status = 'verified'
        )
        INTO v_backup_verified
        FROM backup_recovery.backup_runs br
        WHERE br.id = p_backup_run_id
          AND br.organization_id = p_organization_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Backup run % does not belong to organization %',
                p_backup_run_id, p_organization_id;
        END IF;

        IF p_result = 'passed' AND v_backup_verified IS NOT TRUE THEN
            RAISE EXCEPTION
                'Passed recovery drill requires a completed and verified backup';
        END IF;
    END IF;

    IF p_result = 'passed' THEN
        IF p_recovery_completed_at IS NULL THEN
            RAISE EXCEPTION
                'Passed recovery drill requires recovery_completed_at';
        END IF;

        IF p_measured_rpo_minutes IS NULL
           OR p_measured_rpo_minutes > 15 THEN
            RAISE EXCEPTION
                'Passed recovery drill requires RPO <= 15 minutes';
        END IF;

        IF p_measured_rto_minutes IS NULL
           OR p_measured_rto_minutes > 60 THEN
            RAISE EXCEPTION
                'Passed recovery drill requires RTO <= 60 minutes';
        END IF;

        IF p_backup_verified_before_drill IS NOT TRUE THEN
            RAISE EXCEPTION
                'Passed recovery drill requires verified backup before drill';
        END IF;

        IF NULLIF(BTRIM(p_evidence_reference), '') IS NULL THEN
            RAISE EXCEPTION
                'Passed recovery drill requires evidence_reference';
        END IF;
    END IF;

    INSERT INTO backup_recovery.recovery_drills (
        organization_id,
        backup_run_id,
        drill_type,
        started_at,
        recovery_completed_at,
        recovery_target_time,
        recovered_to_time,
        measured_rpo_minutes,
        measured_rto_minutes,
        pitr_used,
        backup_verified_before_drill,
        result,
        evidence_reference,
        failure_reason
    )
    VALUES (
        p_organization_id,
        p_backup_run_id,
        p_drill_type,
        p_started_at,
        p_recovery_completed_at,
        p_recovery_target_time,
        p_recovered_to_time,
        p_measured_rpo_minutes,
        p_measured_rto_minutes,
        p_pitr_used,
        p_backup_verified_before_drill,
        p_result,
        p_evidence_reference,
        p_failure_reason
    )
    RETURNING id INTO v_drill_id;

    RETURN v_drill_id;
END;
$$;

-- ============================================================
-- 8. TRIGGER: BACKUP INTEGRITY
-- ============================================================

CREATE OR REPLACE FUNCTION backup_recovery.trg_validate_backup_run()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status = 'completed' THEN
        IF NEW.completed_at IS NULL THEN
            RAISE EXCEPTION 'Completed backup requires completed_at';
        END IF;

        IF NEW.encrypted IS NOT TRUE THEN
            RAISE EXCEPTION 'Completed backup must be encrypted';
        END IF;

        IF NEW.credential_isolated IS NOT TRUE THEN
            RAISE EXCEPTION
                'Completed backup must use isolated credentials';
        END IF;

        IF NEW.verification_status <> 'verified' THEN
            RAISE EXCEPTION
                'Completed backup must be verified';
        END IF;

        IF NEW.verified_at IS NULL THEN
            RAISE EXCEPTION 'Verified backup requires verified_at';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_backup_runs_validate
BEFORE INSERT OR UPDATE
ON backup_recovery.backup_runs
FOR EACH ROW
EXECUTE FUNCTION backup_recovery.trg_validate_backup_run();

-- ============================================================
-- 9. TRIGGER: RECOVERY-DRILL INTEGRITY
-- ============================================================

CREATE OR REPLACE FUNCTION backup_recovery.trg_validate_recovery_drill()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_backup_valid BOOLEAN;
BEGIN
    IF NEW.result = 'passed' THEN

        IF NEW.recovery_completed_at IS NULL THEN
            RAISE EXCEPTION
                'Passed recovery drill requires recovery_completed_at';
        END IF;

        IF NEW.measured_rpo_minutes IS NULL
           OR NEW.measured_rpo_minutes > 15 THEN
            RAISE EXCEPTION
                'Passed recovery drill requires RPO <= 15 minutes';
        END IF;

        IF NEW.measured_rto_minutes IS NULL
           OR NEW.measured_rto_minutes > 60 THEN
            RAISE EXCEPTION
                'Passed recovery drill requires RTO <= 60 minutes';
        END IF;

        IF NEW.backup_verified_before_drill IS NOT TRUE THEN
            RAISE EXCEPTION
                'Passed recovery drill requires verified backup before drill';
        END IF;

        IF NULLIF(BTRIM(NEW.evidence_reference), '') IS NULL THEN
            RAISE EXCEPTION
                'Passed recovery drill requires evidence_reference';
        END IF;

        IF NEW.backup_run_id IS NOT NULL THEN
            SELECT (
                br.status = 'completed'
                AND br.verification_status = 'verified'
            )
            INTO v_backup_valid
            FROM backup_recovery.backup_runs br
            WHERE br.id = NEW.backup_run_id
              AND br.organization_id = NEW.organization_id;

            IF v_backup_valid IS NOT TRUE THEN
                RAISE EXCEPTION
                    'Passed recovery drill must reference a completed and verified backup';
            END IF;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_recovery_drills_validate
BEFORE INSERT OR UPDATE
ON backup_recovery.recovery_drills
FOR EACH ROW
EXECUTE FUNCTION backup_recovery.trg_validate_recovery_drill();

-- ============================================================
-- 10. VIEW: USABLE BACKUPS
-- ============================================================

CREATE OR REPLACE VIEW backup_recovery.usable_backups AS
SELECT
    br.id,
    br.organization_id,
    br.backup_policy_id,
    br.backup_type,
    br.started_at,
    br.completed_at,
    br.encrypted,
    br.credential_isolated,
    br.storage_location_reference,
    br.backup_reference,
    br.verification_status,
    br.verified_at,
    br.created_at
FROM backup_recovery.backup_runs br
WHERE br.status = 'completed'
  AND br.encrypted = TRUE
  AND br.credential_isolated = TRUE
  AND br.verification_status = 'verified'
  AND br.verified_at IS NOT NULL;

-- ============================================================
-- 11. VIEW: RECOVERY READINESS
-- ============================================================
-- Evidence-based database view.
-- It does not replace operational monitoring or a real recovery drill.

CREATE OR REPLACE VIEW backup_recovery.recovery_readiness AS
WITH latest_wal AS (
    SELECT DISTINCT ON (organization_id)
        organization_id,
        observed_at,
        last_archived_at,
        archive_lag_seconds,
        archive_status
    FROM backup_recovery.wal_archive_status
    ORDER BY organization_id, observed_at DESC
),
latest_verified_backup AS (
    SELECT DISTINCT ON (organization_id)
        organization_id,
        id AS backup_run_id,
        completed_at,
        verified_at
    FROM backup_recovery.usable_backups
    ORDER BY organization_id, completed_at DESC NULLS LAST
),
latest_passed_drill AS (
    SELECT DISTINCT ON (organization_id)
        organization_id,
        id AS recovery_drill_id,
        started_at,
        recovery_completed_at,
        measured_rpo_minutes,
        measured_rto_minutes,
        pitr_used
    FROM backup_recovery.recovery_drills
    WHERE result = 'passed'
    ORDER BY organization_id, recovery_completed_at DESC NULLS LAST
)
SELECT
    COALESCE(bp.organization_id, lw.organization_id,
             vb.organization_id, rd.organization_id) AS organization_id,

    (bp.id IS NOT NULL) AS policy_configured,

    (lw.archive_status = 'healthy') AS wal_archive_healthy,

    (vb.backup_run_id IS NOT NULL) AS verified_backup_available,

    (rd.recovery_drill_id IS NOT NULL) AS passed_recovery_drill_available,

    rd.measured_rpo_minutes,
    rd.measured_rto_minutes,
    rd.pitr_used,

    (
        bp.id IS NOT NULL
        AND lw.archive_status = 'healthy'
        AND vb.backup_run_id IS NOT NULL
        AND rd.recovery_drill_id IS NOT NULL
        AND rd.measured_rpo_minutes <= 15
        AND rd.measured_rto_minutes <= 60
    ) AS database_evidence_ready

FROM backup_recovery.backup_policies bp
FULL OUTER JOIN latest_wal lw
    ON lw.organization_id = bp.organization_id
FULL OUTER JOIN latest_verified_backup vb
    ON vb.organization_id = COALESCE(bp.organization_id, lw.organization_id)
FULL OUTER JOIN latest_passed_drill rd
    ON rd.organization_id = COALESCE(
        bp.organization_id,
        lw.organization_id,
        vb.organization_id
    );

-- ============================================================
-- END DB-011
-- ============================================================
