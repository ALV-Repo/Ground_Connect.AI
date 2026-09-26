-- ============================================================
-- DB-010 — KMS/HSM KEY MANAGEMENT & ROTATION
-- ============================================================
--
-- PURPOSE
-- -------
-- This file implements DB-010 for the MVP phase.
--
-- Requirement:
--   Keys managed in KMS/HSM with documented rotation schedule.
--   Keys must never appear in source code, Docker images, or
--   configuration files.
--   Per-tenant key separation architecture is prepared for MVP;
--   full isolation is planned for Phase 3.
--
-- IMPORTANT SECURITY BOUNDARY
-- ---------------------------
-- PostgreSQL stores ONLY KMS/HSM references and key-management
-- metadata. Actual cryptographic key material, private keys,
-- key-encryption keys, KMS credentials, HSM credentials, and
-- secrets must remain inside the configured KMS/HSM.
--
-- This file MUST NOT contain:
--   * plaintext cryptographic keys
--   * private keys
--   * KMS/HSM credentials
--   * access tokens
--   * cloud secret values
--
-- TENANT SEPARATION
-- -----------------
-- Every managed key record is tenant-scoped through
-- organization_id. The combination of organization_id and the
-- provider's key reference is unique, preventing one tenant's
-- key reference from being registered against another tenant.
--
-- MVP / PHASE 3 NOTE
-- ------------------
-- MVP prepares the logical per-tenant key-separation architecture.
-- Full physical/isolation-boundary enforcement is a Phase 3
-- concern and is not claimed by this database file.
--
-- ROTATION POLICY
-- ---------------
-- The database records a rotation schedule and key-version
-- history. The default documented application policy is a
-- 90-day rotation interval. The database does not perform the
-- cryptographic rotation itself; the KMS/HSM and its controlled
-- operational workflow perform the actual rotation.
--
-- FILE
-- ----
-- kms_hsm_key_management.sql
--
-- TASK
-- ----
-- DB-010
--
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS kms_hsm_key_management;

-- ============================================================
-- KMS/HSM KEY REGISTRY
-- ============================================================

CREATE TABLE kms_hsm_key_management.managed_keys
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    provider TEXT NOT NULL,

    key_reference TEXT NOT NULL,

    key_alias TEXT NULL,

    key_purpose TEXT NOT NULL,

    rotation_interval_days INTEGER NOT NULL DEFAULT 90,

    last_rotated_at TIMESTAMPTZ NULL,

    next_rotation_at TIMESTAMPTZ NOT NULL,

    status TEXT NOT NULL DEFAULT 'active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_managed_keys
        PRIMARY KEY (id),

    CONSTRAINT fk_managed_keys_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT uq_managed_keys_org_reference
        UNIQUE (organization_id, key_reference),

    CONSTRAINT chk_managed_keys_provider
        CHECK (
            provider IN (
                'aws_kms',
                'azure_key_vault',
                'gcp_kms',
                'hsm',
                'other'
            )
        ),

    CONSTRAINT chk_managed_keys_purpose
        CHECK (
            key_purpose IN (
                'data_encryption',
                'field_encryption',
                'database_encryption',
                'object_storage',
                'signing',
                'other'
            )
        ),

    CONSTRAINT chk_managed_keys_rotation_interval
        CHECK (
            rotation_interval_days BETWEEN 1 AND 3650
        ),

    CONSTRAINT chk_managed_keys_rotation_order
        CHECK (
            last_rotated_at IS NULL
            OR next_rotation_at > last_rotated_at
        ),

    CONSTRAINT chk_managed_keys_status
        CHECK (
            status IN (
                'pending',
                'active',
                'rotation_due',
                'disabled',
                'retired'
            )
        )
);

CREATE INDEX idx_managed_keys_organization_id
    ON kms_hsm_key_management.managed_keys (organization_id);

CREATE INDEX idx_managed_keys_rotation_due
    ON kms_hsm_key_management.managed_keys
        (next_rotation_at, organization_id)
    WHERE status IN ('active', 'rotation_due');

CREATE INDEX idx_managed_keys_status
    ON kms_hsm_key_management.managed_keys
        (organization_id, status);

-- ============================================================
-- KEY VERSION REGISTRY
-- ============================================================
--
-- Stores KMS/HSM version references only.
-- Actual key material is never stored here.
-- ============================================================

CREATE TABLE kms_hsm_key_management.key_versions
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    managed_key_id UUID NOT NULL,

    organization_id UUID NOT NULL,

    provider_version_reference TEXT NOT NULL,

    version_number INTEGER NOT NULL,

    activated_at TIMESTAMPTZ NOT NULL,

    retired_at TIMESTAMPTZ NULL,

    status TEXT NOT NULL DEFAULT 'active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_key_versions
        PRIMARY KEY (id),

    CONSTRAINT fk_key_versions_managed_key
        FOREIGN KEY (managed_key_id)
        REFERENCES kms_hsm_key_management.managed_keys(id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_key_versions_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT uq_key_versions_managed_version
        UNIQUE (managed_key_id, version_number),

    CONSTRAINT uq_key_versions_provider_reference
        UNIQUE (organization_id, provider_version_reference),

    CONSTRAINT chk_key_versions_version_number
        CHECK (version_number >= 1),

    CONSTRAINT chk_key_versions_status
        CHECK (
            status IN (
                'active',
                'retired',
                'disabled'
            )
        ),

    CONSTRAINT chk_key_versions_retirement
        CHECK (
            retired_at IS NULL
            OR retired_at >= activated_at
        )
);

CREATE INDEX idx_key_versions_managed_key
    ON kms_hsm_key_management.key_versions
        (managed_key_id, version_number DESC);

CREATE INDEX idx_key_versions_organization_id
    ON kms_hsm_key_management.key_versions
        (organization_id);

CREATE INDEX idx_key_versions_active
    ON kms_hsm_key_management.key_versions
        (organization_id, managed_key_id)
    WHERE status = 'active';

-- ============================================================
-- ONE ACTIVE VERSION PER MANAGED KEY
-- ============================================================

CREATE UNIQUE INDEX uq_key_versions_one_active
    ON kms_hsm_key_management.key_versions (managed_key_id)
    WHERE status = 'active';

-- ============================================================
-- ROTATION HISTORY
-- ============================================================
--
-- Records rotation events without storing any key material.
-- ============================================================

CREATE TABLE kms_hsm_key_management.rotation_events
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    managed_key_id UUID NOT NULL,

    previous_version_id UUID NULL,

    new_version_id UUID NULL,

    rotation_type TEXT NOT NULL DEFAULT 'scheduled',

    rotated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    initiated_by TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'completed',

    notes TEXT NULL,

    CONSTRAINT pk_rotation_events
        PRIMARY KEY (id),

    CONSTRAINT fk_rotation_events_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_rotation_events_managed_key
        FOREIGN KEY (managed_key_id)
        REFERENCES kms_hsm_key_management.managed_keys(id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_rotation_events_previous_version
        FOREIGN KEY (previous_version_id)
        REFERENCES kms_hsm_key_management.key_versions(id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_rotation_events_new_version
        FOREIGN KEY (new_version_id)
        REFERENCES kms_hsm_key_management.key_versions(id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_rotation_events_type
        CHECK (
            rotation_type IN (
                'scheduled',
                'manual',
                'emergency'
            )
        ),

    CONSTRAINT chk_rotation_events_initiated_by
        CHECK (
            initiated_by IN (
                'kms',
                'hsm',
                'platform',
                'operator'
            )
        ),

    CONSTRAINT chk_rotation_events_status
        CHECK (
            status IN (
                'pending',
                'completed',
                'failed'
            )
        )
);

CREATE INDEX idx_rotation_events_organization_id
    ON kms_hsm_key_management.rotation_events
        (organization_id);

CREATE INDEX idx_rotation_events_managed_key_time
    ON kms_hsm_key_management.rotation_events
        (managed_key_id, rotated_at DESC);

CREATE INDEX idx_rotation_events_status
    ON kms_hsm_key_management.rotation_events
        (organization_id, status);

-- ============================================================
-- SECURITY NOTE
-- ============================================================
--
-- No SQL object in this file stores the actual cryptographic
-- secret/key material. key_reference and
-- provider_version_reference are identifiers only.
--
-- Application deployments must supply KMS/HSM access through
-- the platform's approved secret/identity mechanism. Secrets
-- must not be placed in SQL files, Docker images, application
-- configuration files, or Git repositories.
--
-- Actual rotation is executed by the configured KMS/HSM and
-- controlled operational workflow. These tables provide the
-- tenant-scoped registry, schedule metadata, version history,
-- and rotation audit trail required by DB-010.
--
-- ============================================================
