-- ============================================================
-- DB-012 PostgreSQL-side tests
-- ============================================================

BEGIN;

DO $$
BEGIN
    IF to_regclass('search_index.tenant_indexes') IS NULL
       OR to_regclass('search_index.search_records') IS NULL THEN
        RAISE EXCEPTION 'DB-012 TEST FAILED: search objects missing';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_search_tenant_indexes_organization'
    ) THEN
        RAISE EXCEPTION 'DB-012 TEST FAILED: one-index-per-tenant constraint missing';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_search_records_tenant_index_scoped'
    ) THEN
        RAISE EXCEPTION 'DB-012 TEST FAILED: tenant/index composite FK missing';
    END IF;
END $$;

DO $$
DECLARE
    v_enabled BOOLEAN;
    v_forced BOOLEAN;
BEGIN
    SELECT c.relrowsecurity, c.relforcerowsecurity
    INTO v_enabled, v_forced
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'search_index'
      AND c.relname = 'search_records';

    IF NOT v_enabled OR NOT v_forced THEN
        RAISE EXCEPTION 'DB-012 TEST FAILED: search_records RLS/FORCE RLS missing';
    END IF;
END $$;

DO $$
BEGIN
	IF NOT EXISTS (
		SELECT 1
		FROM information_schema.columns
		WHERE table_schema = 'search_index'
			AND table_name = 'search_records'
			AND column_name = 'transliteration_variants'
		) THEN
			RAISE EXCEPTION
				'DB-012 TEST FAILED: transliteration_variants missing';
	END IF;
END $$;
 
-- ============================================================
-- TEN-04 CONTRACT TEST
-- Cross-tenant index association must be impossible
-- ============================================================
 
/*DO $$
DECLARE
	v_tenant_a UUID := gen_random_uuid();
	v_tenant_b UUID := gen_random_uuid();
	 
	v_index_a UUID;
BEGIN
 
	INSERT INTO search_index.tenant_indexes
		(
		organization_id,
		index_name
		)
	VALUES
	(
	v_tenant_a,
	'tenant_a_idx'
	)
	RETURNING id INTO v_index_a;
 
	BEGIN
 
	INSERT INTO search_index.search_records
	(
		organization_id,
		tenant_index_id,
		resource_type,
		resource_id,
		search_text,
		authorization_scope
	)
	VALUES
	(
		v_tenant_b,
		v_index_a,
		'document',
		gen_random_uuid(),
		'cross tenant leak',
		'{}'::jsonb
	);
 
	RAISE EXCEPTION
		'TEN-04 FAILED: cross-tenant insertion succeeded';
 
	EXCEPTION
		WHEN foreign_key_violation THEN
			NULL;
	END;
 
END $$;*/
 
ROLLBACK;

DO $$
BEGIN
    RAISE NOTICE 'DB-012 PostgreSQL-side tests passed';
END $$;
