-- ============================================================
-- OBJECT STORAGE KEY REGISTRY
-- DB-007 REVIEW RESOLUTION
-- ============================================================
--
-- PURPOSE
-- -------
-- This file is an ADDITIONAL implementation created during
-- the review of DB-007 — Object-Storage Key Scoping &
-- Signed-URL Policy.
--
-- ORIGINAL DB-007 IMPLEMENTATION
-- ------------------------------
-- The DB-007 task was originally defined and implemented in:
--
--   object_storage_key_scoping.sql
--
-- This file does NOT replace or rename the original DB-007
-- implementation.
--
-- WHY THIS FILE EXISTS
-- --------------------
-- During the review of DB-007, the review team identified
-- the need for an explicit database-level object-storage key
-- registry.
--
-- This file was therefore added specifically to address
-- that review remark.
--
-- RELATIONSHIP TO DB-007
-- ----------------------
-- Both files belong to the same DB-007 implementation area:
--
--     DB-007/
--     ├── object_storage_key_scoping.sql
--     │   └── Original DB-007 task implementation
--     │
--     └── object_storage_keys.sql
--         └── Additional implementation added to resolve
--             the DB-007 review remark
--
-- IMPORTANT
-- ---------
-- object_storage_keys.sql is NOT a new or separate task.
-- It is a review-resolution component of DB-007.
--
-- The original DB-007 file and this review-resolution file
-- should therefore be maintained together as part of the
-- DB-007 implementation.
--
-- DEPENDENCY NOTE
-- ---------------
-- The SQL execution order must follow the actual database
-- object dependencies (schemas, tables, foreign keys,
-- functions, triggers, etc.).
--
-- File placement in the DB-007 folder documents the logical
-- relationship between these files; it does not by itself
-- create a SQL execution dependency.
--
-- ============================================================


CREATE SCHEMA IF NOT EXISTS object_storage;

CREATE TABLE object_storage.storage_keys
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    object_storage_key TEXT NOT NULL,

    key_prefix TEXT NOT NULL,

    purpose TEXT NOT NULL,

    signed_url_policy JSONB NOT NULL DEFAULT
        '{
            "allowed_methods": ["GET"],
            "max_expiry_seconds": 900
        }'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_storage_keys
        PRIMARY KEY (id),

    CONSTRAINT fk_storage_keys_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT chk_storage_keys_signed_url_policy
        CHECK (
            jsonb_typeof(signed_url_policy) = 'object'
        ),

    CONSTRAINT chk_storage_keys_max_expiry
        CHECK (
            COALESCE(
                (signed_url_policy ->> 'max_expiry_seconds')::INTEGER,
                900
            ) BETWEEN 1 AND 900
        )
);