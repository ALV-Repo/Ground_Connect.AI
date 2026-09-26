-- DB-013 PostgreSQL control-plane tests.
-- These validate PostgreSQL controls only; Redis integration is separate.

BEGIN;

DO $$
BEGIN
    IF to_regclass('redis_session_authorization.session_cache_policies') IS NULL
       OR to_regclass('redis_session_authorization.refresh_token_families') IS NULL
       OR to_regclass('redis_session_authorization.authorization_versions') IS NULL
    THEN
        RAISE EXCEPTION 'DB-013 required objects are missing';
    END IF;
END $$;

DO $$
BEGIN
    IF redis_session_authorization.validate_authorization_cache_ttl(60)
       IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION '60-second TTL must be accepted';
    END IF;

    BEGIN
        PERFORM redis_session_authorization.validate_authorization_cache_ttl(61);
        RAISE EXCEPTION '61-second TTL was accepted';
    EXCEPTION WHEN SQLSTATE '22023' THEN
        NULL;
    END;
END $$;

DO $$
DECLARE v_org UUID;
BEGIN
    SELECT id INTO v_org FROM tenant_and_configuration.tenants LIMIT 1;
    IF v_org IS NULL THEN
        RAISE EXCEPTION 'Test requires at least one tenant';
    END IF;

    BEGIN
        INSERT INTO redis_session_authorization.session_cache_policies
            (organization_id, idle_ttl_seconds, absolute_ttl_seconds,
             authorization_cache_ttl_seconds)
        VALUES (v_org, 3600, 1800, 60);
        RAISE EXCEPTION 'Invalid TTL policy was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END $$;

DO $$
DECLARE
    v_org UUID;
    v_initial BIGINT;
    v_new BIGINT;
BEGIN
    SELECT id INTO v_org FROM tenant_and_configuration.tenants LIMIT 1;

    v_initial := redis_session_authorization.ensure_authorization_version(v_org);
    IF v_initial <> 1 THEN
        RAISE EXCEPTION 'Expected initial authorization version 1, got %', v_initial;
    END IF;

    v_new := redis_session_authorization.bump_authorization_version(v_org, 'hierarchy');

    IF v_new <> 2 THEN
        RAISE EXCEPTION 'Expected authorization version 2, got %', v_new;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM redis_session_authorization.authorization_invalidation_events
        WHERE organization_id = v_org
          AND authorization_version = v_new
          AND change_type = 'hierarchy'
    ) THEN
        RAISE EXCEPTION 'Hierarchy invalidation event missing';
    END IF;
END $$;

DO $$
DECLARE v_org UUID;
BEGIN
    SELECT id INTO v_org FROM tenant_and_configuration.tenants LIMIT 1;

    BEGIN
        PERFORM redis_session_authorization.bump_authorization_version(
            v_org, 'unsupported_change'
        );
        RAISE EXCEPTION 'Unsupported change type was accepted';
    EXCEPTION WHEN SQLSTATE '22023' THEN
        NULL;
    END;
END $$;

DO $$
DECLARE
    v_org UUID;
    v_user UUID;
    v_family UUID := gen_random_uuid();
    v_generation BIGINT;
BEGIN
    SELECT t.id INTO v_org
    FROM tenant_and_configuration.tenants t LIMIT 1;

    SELECT u.id INTO v_user
    FROM identity_authentication_sessions.users u
    WHERE u.organization_id = v_org
    LIMIT 1;

    IF v_user IS NULL THEN
        RAISE EXCEPTION 'Token test requires a user in the selected tenant';
    END IF;

    v_generation := redis_session_authorization.rotate_refresh_token(
        v_org, v_family, v_user, 'initial-token', 'token-1'
    );
    IF v_generation <> 1 THEN
        RAISE EXCEPTION 'Expected generation 1';
    END IF;

    v_generation := redis_session_authorization.rotate_refresh_token(
        v_org, v_family, v_user, 'token-1', 'token-2'
    );
    IF v_generation <> 2 THEN
        RAISE EXCEPTION 'Expected generation 2';
    END IF;

    BEGIN
        PERFORM redis_session_authorization.rotate_refresh_token(
            v_org, v_family, v_user, 'token-1', 'token-3'
        );
        RAISE EXCEPTION 'Refresh-token reuse was not detected';
    EXCEPTION WHEN SQLSTATE '28000' THEN
        NULL;
    END;

    IF NOT EXISTS (
        SELECT 1
        FROM redis_session_authorization.refresh_token_families
        WHERE session_family_id = v_family
          AND revoked_at IS NOT NULL
          AND revoke_reason = 'token_reuse'
    ) THEN
        RAISE EXCEPTION 'Token family was not revoked after reuse';
    END IF;
END $$;

ROLLBACK;
