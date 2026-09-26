-- DB-013 — Redis Session Store & Authorization-Decision Cache
-- PostgreSQL control plane. Redis remains the runtime store/cache.
-- Stores token hashes and security metadata only; never raw tokens.
--Application service MUST invoke bump_authorization_version() after any hierarchy/role/grant/

CREATE SCHEMA IF NOT EXISTS redis_session_authorization;

CREATE TABLE IF NOT EXISTS redis_session_authorization.session_cache_policies (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    idle_ttl_seconds INTEGER NOT NULL,
    absolute_ttl_seconds INTEGER NOT NULL,
    authorization_cache_ttl_seconds INTEGER NOT NULL DEFAULT 60,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_session_cache_policies PRIMARY KEY (id),
    CONSTRAINT uq_session_cache_policies_organization UNIQUE (organization_id),
    CONSTRAINT fk_session_cache_policies_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT chk_session_cache_policies_idle_ttl
        CHECK (idle_ttl_seconds > 0),
    CONSTRAINT chk_session_cache_policies_absolute_ttl
        CHECK (absolute_ttl_seconds >= idle_ttl_seconds),
    CONSTRAINT chk_session_cache_policies_authz_ttl
        CHECK (authorization_cache_ttl_seconds BETWEEN 1 AND 60)
);

CREATE TABLE IF NOT EXISTS redis_session_authorization.refresh_token_families (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    session_family_id UUID NOT NULL,
    user_id UUID NOT NULL,
    current_token_hash TEXT NOT NULL,
    token_generation BIGINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_rotated_at TIMESTAMPTZ NULL,
    revoked_at TIMESTAMPTZ NULL,
    revoke_reason TEXT NULL,

    CONSTRAINT pk_refresh_token_families PRIMARY KEY (id),
    CONSTRAINT uq_refresh_token_families_session_family UNIQUE (session_family_id),
    CONSTRAINT uq_refresh_token_families_current_token_hash UNIQUE (current_token_hash),
    CONSTRAINT fk_refresh_token_families_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT fk_refresh_token_families_user
        FOREIGN KEY (user_id)
        REFERENCES identity_authentication_sessions.users(id),
    CONSTRAINT chk_refresh_token_families_generation CHECK (token_generation >= 1),
    CONSTRAINT chk_refresh_token_families_revoke_reason CHECK (
        revoke_reason IN ('logout','token_reuse','device_revoked','admin','transfer')
        OR revoke_reason IS NULL
    ),
    CONSTRAINT chk_refresh_token_families_revocation_state CHECK (
        (revoked_at IS NULL AND revoke_reason IS NULL)
        OR (revoked_at IS NOT NULL AND revoke_reason IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_refresh_token_families_org
ON redis_session_authorization.refresh_token_families (organization_id);

CREATE INDEX IF NOT EXISTS idx_refresh_token_families_user
ON redis_session_authorization.refresh_token_families (user_id);

CREATE TABLE IF NOT EXISTS redis_session_authorization.refresh_token_events (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    session_family_id UUID NOT NULL,
    user_id UUID NOT NULL,
    token_generation BIGINT NOT NULL,
    token_hash TEXT NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    CONSTRAINT pk_refresh_token_events PRIMARY KEY (id),
    CONSTRAINT fk_refresh_token_events_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT fk_refresh_token_events_user
        FOREIGN KEY (user_id)
        REFERENCES identity_authentication_sessions.users(id),
    CONSTRAINT chk_refresh_token_events_generation CHECK (token_generation >= 1),
    CONSTRAINT chk_refresh_token_events_type CHECK (
        event_type IN ('issued','rotated','reuse_detected','family_revoked')
    ),
    CONSTRAINT chk_refresh_token_events_details CHECK (jsonb_typeof(details) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_refresh_token_events_family_time
ON redis_session_authorization.refresh_token_events
(session_family_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS redis_session_authorization.authorization_versions (
    organization_id UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_authorization_versions PRIMARY KEY (organization_id),
    CONSTRAINT fk_authorization_versions_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT chk_authorization_versions_positive CHECK (version >= 1)
);

CREATE TABLE IF NOT EXISTS redis_session_authorization.authorization_invalidation_events (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    authorization_version BIGINT NOT NULL,
    change_type TEXT NOT NULL,
    resource_id UUID NULL,
    actor_user_id UUID NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    CONSTRAINT pk_authorization_invalidation_events PRIMARY KEY (id),
    CONSTRAINT fk_authorization_invalidation_events_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
    CONSTRAINT fk_authorization_invalidation_events_actor
        FOREIGN KEY (actor_user_id)
        REFERENCES identity_authentication_sessions.users(id),
    CONSTRAINT chk_authorization_invalidation_events_version CHECK (authorization_version >= 1),
    CONSTRAINT chk_authorization_invalidation_events_type CHECK (
        change_type IN ('hierarchy','role','grant','delegation')
    ),
    CONSTRAINT chk_authorization_invalidation_events_details CHECK (
        jsonb_typeof(details) = 'object'
    )
);

CREATE INDEX IF NOT EXISTS idx_authz_invalidation_events_org_time
ON redis_session_authorization.authorization_invalidation_events
(organization_id, occurred_at DESC);

CREATE OR REPLACE FUNCTION redis_session_authorization.ensure_authorization_version(
    p_organization_id UUID
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE v_version BIGINT;
BEGIN
    INSERT INTO redis_session_authorization.authorization_versions
        (organization_id, version)
    VALUES (p_organization_id, 1)
    ON CONFLICT (organization_id) DO NOTHING;

    SELECT version INTO v_version
    FROM redis_session_authorization.authorization_versions
    WHERE organization_id = p_organization_id;

    RETURN v_version;
END;
$$;

CREATE OR REPLACE FUNCTION redis_session_authorization.bump_authorization_version(
    p_organization_id UUID,
    p_change_type TEXT,
    p_resource_id UUID DEFAULT NULL,
    p_actor_user_id UUID DEFAULT NULL,
    p_details JSONB DEFAULT '{}'::JSONB
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE v_version BIGINT;
BEGIN
    IF p_change_type NOT IN ('hierarchy','role','grant','delegation') THEN
        RAISE EXCEPTION 'Unsupported authorization change type: %', p_change_type
            USING ERRCODE = '22023';
    END IF;

    IF jsonb_typeof(COALESCE(p_details, '{}'::JSONB)) <> 'object' THEN
        RAISE EXCEPTION 'p_details must be a JSON object'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO redis_session_authorization.authorization_versions
        (organization_id, version, updated_at)
    VALUES (p_organization_id, 2, CURRENT_TIMESTAMP)
    ON CONFLICT (organization_id)
    DO UPDATE SET
        version = redis_session_authorization.authorization_versions.version + 1,
        updated_at = CURRENT_TIMESTAMP
    RETURNING version INTO v_version;

    INSERT INTO redis_session_authorization.authorization_invalidation_events
        (organization_id, authorization_version, change_type,
         resource_id, actor_user_id, details)
    VALUES
        (p_organization_id, v_version, p_change_type,
         p_resource_id, p_actor_user_id, COALESCE(p_details, '{}'::JSONB));

    RETURN v_version;
END;
$$;

CREATE OR REPLACE FUNCTION redis_session_authorization.validate_authorization_cache_ttl(
    p_ttl_seconds INTEGER
)
RETURNS BOOLEAN
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    IF p_ttl_seconds IS NULL OR p_ttl_seconds < 1 OR p_ttl_seconds > 60 THEN
        RAISE EXCEPTION
            'Authorization-decision cache TTL must be between 1 and 60 seconds'
            USING ERRCODE = '22023';
    END IF;
    RETURN TRUE;
END;
$$;

CREATE OR REPLACE FUNCTION redis_session_authorization.rotate_refresh_token(
    p_organization_id UUID,
    p_session_family_id UUID,
    p_user_id UUID,
    p_previous_token_hash TEXT,
    p_new_token_hash TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_family redis_session_authorization.refresh_token_families%ROWTYPE;
    v_generation BIGINT;
BEGIN
    IF NULLIF(trim(p_previous_token_hash), '') IS NULL
       OR NULLIF(trim(p_new_token_hash), '') IS NULL
    THEN
        RAISE EXCEPTION 'Refresh-token hashes must be non-empty'
            USING ERRCODE = '22023';
    END IF;

    IF p_previous_token_hash = p_new_token_hash THEN
        RAISE EXCEPTION 'New refresh-token hash must differ from previous hash'
            USING ERRCODE = '22023';
    END IF;

    SELECT * INTO v_family
    FROM redis_session_authorization.refresh_token_families
    WHERE session_family_id = p_session_family_id
    FOR UPDATE;

    IF NOT FOUND THEN
        INSERT INTO redis_session_authorization.refresh_token_families
            (organization_id, session_family_id, user_id,
             current_token_hash, token_generation, last_rotated_at)
        VALUES
            (p_organization_id, p_session_family_id, p_user_id,
             p_new_token_hash, 1, CURRENT_TIMESTAMP)
        RETURNING token_generation INTO v_generation;

        INSERT INTO redis_session_authorization.refresh_token_events
            (organization_id, session_family_id, user_id,
             token_generation, token_hash, event_type)
        VALUES
            (p_organization_id, p_session_family_id, p_user_id,
             v_generation, p_new_token_hash, 'issued');

        RETURN v_generation;
    END IF;

    IF v_family.revoked_at IS NOT NULL THEN
        RAISE EXCEPTION 'Refresh-token family is already revoked'
            USING ERRCODE = '42501';
    END IF;

    IF v_family.organization_id <> p_organization_id
       OR v_family.user_id <> p_user_id THEN
        RAISE EXCEPTION 'Refresh-token family tenant/user mismatch'
            USING ERRCODE = '42501';
    END IF;

    IF v_family.current_token_hash <> p_previous_token_hash THEN
        UPDATE redis_session_authorization.refresh_token_families
        SET revoked_at = CURRENT_TIMESTAMP,
            revoke_reason = 'token_reuse'
        WHERE id = v_family.id;

        INSERT INTO redis_session_authorization.refresh_token_events
            (organization_id, session_family_id, user_id,
             token_generation, token_hash, event_type, details)
        VALUES
            (v_family.organization_id, v_family.session_family_id,
             v_family.user_id, v_family.token_generation,
             p_previous_token_hash, 'reuse_detected',
             jsonb_build_object('expected_generation', v_family.token_generation));

        RAISE EXCEPTION
            'Refresh-token reuse detected; entire token family revoked'
            USING ERRCODE = '28000';
    END IF;

    v_generation := v_family.token_generation + 1;

    UPDATE redis_session_authorization.refresh_token_families
    SET current_token_hash = p_new_token_hash,
        token_generation = v_generation,
        last_rotated_at = CURRENT_TIMESTAMP
    WHERE id = v_family.id;

    INSERT INTO redis_session_authorization.refresh_token_events
        (organization_id, session_family_id, user_id,
         token_generation, token_hash, event_type)
    VALUES
        (v_family.organization_id, v_family.session_family_id,
         v_family.user_id, v_generation, p_new_token_hash, 'rotated');

    RETURN v_generation;
END;
$$;

CREATE OR REPLACE FUNCTION redis_session_authorization.revoke_refresh_token_family(
    p_session_family_id UUID,
    p_reason TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE v_family redis_session_authorization.refresh_token_families%ROWTYPE;
BEGIN
    IF p_reason NOT IN ('logout','token_reuse','device_revoked','admin','transfer') THEN
        RAISE EXCEPTION 'Unsupported refresh-token family revoke reason: %', p_reason
            USING ERRCODE = '22023';
    END IF;

    SELECT * INTO v_family
    FROM redis_session_authorization.refresh_token_families
    WHERE session_family_id = p_session_family_id
    FOR UPDATE;

    IF NOT FOUND THEN RETURN FALSE; END IF;

    IF v_family.revoked_at IS NULL THEN
        UPDATE redis_session_authorization.refresh_token_families
        SET revoked_at = CURRENT_TIMESTAMP,
            revoke_reason = p_reason
        WHERE id = v_family.id;

        INSERT INTO redis_session_authorization.refresh_token_events
            (organization_id, session_family_id, user_id,
             token_generation, token_hash, event_type, details)
        VALUES
            (v_family.organization_id, v_family.session_family_id,
             v_family.user_id, v_family.token_generation,
             v_family.current_token_hash, 'family_revoked',
             jsonb_build_object('reason', p_reason));
    END IF;

    RETURN TRUE;
END;
$$;

ALTER TABLE redis_session_authorization.session_cache_policies
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE redis_session_authorization.session_cache_policies
    FORCE ROW LEVEL SECURITY;

ALTER TABLE redis_session_authorization.refresh_token_families
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE redis_session_authorization.refresh_token_families
    FORCE ROW LEVEL SECURITY;

ALTER TABLE redis_session_authorization.refresh_token_events
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE redis_session_authorization.refresh_token_events
    FORCE ROW LEVEL SECURITY;

ALTER TABLE redis_session_authorization.authorization_versions
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE redis_session_authorization.authorization_versions
    FORCE ROW LEVEL SECURITY;

ALTER TABLE redis_session_authorization.authorization_invalidation_events
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE redis_session_authorization.authorization_invalidation_events
    FORCE ROW LEVEL SECURITY;

CREATE POLICY session_cache_policies_tenant_isolation
ON redis_session_authorization.session_cache_policies
USING (organization_id = app.current_organization_id())
WITH CHECK (organization_id = app.current_organization_id());

CREATE POLICY refresh_token_families_tenant_isolation
ON redis_session_authorization.refresh_token_families
USING (organization_id = app.current_organization_id())
WITH CHECK (organization_id = app.current_organization_id());

CREATE POLICY refresh_token_events_tenant_isolation
ON redis_session_authorization.refresh_token_events
USING (organization_id = app.current_organization_id())
WITH CHECK (organization_id = app.current_organization_id());

CREATE POLICY authorization_versions_tenant_isolation
ON redis_session_authorization.authorization_versions
USING (organization_id = app.current_organization_id())
WITH CHECK (organization_id = app.current_organization_id());

CREATE POLICY authorization_invalidation_events_tenant_isolation
ON redis_session_authorization.authorization_invalidation_events
USING (organization_id = app.current_organization_id())
WITH CHECK (organization_id = app.current_organization_id());

CREATE OR REPLACE VIEW redis_session_authorization.current_cache_control AS
SELECT
    p.organization_id,
    p.id AS policy_id,
    p.idle_ttl_seconds,
    p.absolute_ttl_seconds,
    p.authorization_cache_ttl_seconds,
    av.version AS authorization_version,
    p.enabled
FROM redis_session_authorization.session_cache_policies p
JOIN redis_session_authorization.authorization_versions av
  ON av.organization_id = p.organization_id
WHERE p.enabled = TRUE;
