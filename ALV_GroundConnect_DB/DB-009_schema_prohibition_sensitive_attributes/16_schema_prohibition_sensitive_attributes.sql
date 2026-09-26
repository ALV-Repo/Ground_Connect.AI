-- ============================================================
-- schema_prohibition_sensitive_attributes.sql
-- SCHEMA PROHIBITION OF SENSITIVE ATTRIBUTES
-- ============================================================
-- Requirements:
--   PROH-01 Core schema contains NO field for:
--          religion, caste, community, political affiliation,
--          voting intention, or persuasion/propensity score.
--          These fields are absent, not nullable.
--
--   PROH-02 Multilingual denylist is versioned and can be updated
--          without redeployment.
--
--   PROH-03 Every denylist change is audited and the denylist is
--          used to screen custom-field creation.
--
-- This is an incremental migration.
-- It extends the existing prohibited_attribute_firewall schema.
-- It does NOT recreate prohibited_terms or prohibited_alerts.
-- ============================================================

BEGIN;

-- ============================================================
-- 1. DEPENDENCY CHECKS
-- ============================================================

DO $$
BEGIN
    IF to_regclass('prohibited_attribute_firewall.prohibited_terms') IS NULL THEN
        RAISE EXCEPTION
            'Missing dependency: prohibited_attribute_firewall.prohibited_terms';
    END IF;

    IF to_regclass('prohibited_attribute_firewall.prohibited_alerts') IS NULL THEN
        RAISE EXCEPTION
            'Missing dependency: prohibited_attribute_firewall.prohibited_alerts';
    END IF;

    IF to_regprocedure(
        'audit_trail.append_audit_event(uuid,uuid,uuid,uuid,text,text,uuid,jsonb,text,boolean)'
    ) IS NULL THEN
        RAISE EXCEPTION
            'Missing dependency: audit_trail.append_audit_event(...). Run 15_append_only_hash_chained_audit.sql first.';
    END IF;
END
$$;


-- ============================================================
-- 2. PROH-01
-- CORE SCHEMA PROHIBITION
-- ============================================================
--
-- The following attributes are prohibited from the application
-- data model. They must not exist as columns at all.
--
-- The check deliberately excludes the policy/audit schemas because
-- those schemas must contain the denylist vocabulary itself.
--
-- Deployment fails if a prohibited column is found.
-- ============================================================

DO $$
DECLARE
    v_found TEXT;
BEGIN

    SELECT string_agg(
        format(
            '%I.%I.%I',
            table_schema,
            table_name,
            column_name
        ),
        ', '
        ORDER BY table_schema, table_name, column_name
    )
    INTO v_found
    FROM information_schema.columns
    WHERE table_schema NOT IN
    (
        'pg_catalog',
        'information_schema',
        'prohibited_attribute_firewall',
        'audit_trail',
        'object_storage_security',
        'app'
    )
    AND
    (
        lower(column_name) IN
        (
            'religion',
            'religion_id',

            'caste',
            'caste_id',

            'community',
            'community_id',

            'political_affiliation',
            'political_affiliation_id',
            'political_party',
            'political_party_id',
            'political_preference',

            'voting_intention',
            'voting_intention_id',
            'vote_intention',
            'voting_preference',

            'persuasion_score',
            'persuasion_propensity',
            'propensity_score',
            'political_propensity_score'
        )

        OR

        lower(column_name) ~
        '(religion|caste|community|political[_ ]?(affiliation|party|preference)|voting[_ ]?(intention|preference)|persuasion[_ ]?(score|propensity)|propensity[_ ]?score)'
    );

    IF v_found IS NOT NULL THEN

        RAISE EXCEPTION
            'PROH-01 violation. Prohibited sensitive attribute columns found: %',
            v_found;

    END IF;
END
$$;


-- ============================================================
-- 3. DENYLIST LANGUAGE POLICY
-- ============================================================
--
-- Existing denylist supports multilingual terms. This changes the
-- language restriction from a fixed list to lowercase two-letter
-- language codes so new languages can be introduced by data change,
-- not schema redeployment.
-- ============================================================

ALTER TABLE prohibited_attribute_firewall.prohibited_terms
    DROP CONSTRAINT IF EXISTS chk_prohibited_terms_language;

ALTER TABLE prohibited_attribute_firewall.prohibited_terms
    ADD CONSTRAINT chk_prohibited_terms_language
    CHECK (language ~ '^[a-z]{2}$');


-- ============================================================
-- 4. IMMUTABLE DENYLIST CHANGE HISTORY
-- ============================================================
--
-- Every change receives a historical version.
-- No delete is used for normal denylist removal.
-- ============================================================

CREATE TABLE IF NOT EXISTS
prohibited_attribute_firewall.prohibited_term_history
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    term_id UUID NOT NULL,

    organization_id UUID NULL,

    term TEXT NOT NULL,

    language TEXT NOT NULL,

    transliterations TEXT[] NOT NULL,

    category TEXT NOT NULL,

    version INTEGER NOT NULL,

    operation TEXT NOT NULL,

    changed_by UUID NOT NULL,

    changed_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    removed_at TIMESTAMPTZ NULL,

    CONSTRAINT pk_prohibited_term_history
        PRIMARY KEY (id),

    CONSTRAINT fk_prohibited_term_history_term
        FOREIGN KEY (term_id)
        REFERENCES prohibited_attribute_firewall.prohibited_terms(id),

    CONSTRAINT fk_prohibited_term_history_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_prohibited_term_history_changed_by
        FOREIGN KEY (changed_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_prohibited_term_history_operation
        CHECK
        (
            operation IN
            (
                'INSERT',
                'UPDATE',
                'REMOVE'
            )
        ),

    CONSTRAINT chk_prohibited_term_history_language
        CHECK (language ~ '^[a-z]{2}$')
);


CREATE INDEX IF NOT EXISTS
idx_prohibited_term_history_term_version
ON prohibited_attribute_firewall.prohibited_term_history
(
    term_id,
    version
);


CREATE INDEX IF NOT EXISTS
idx_prohibited_term_history_org_changed
ON prohibited_attribute_firewall.prohibited_term_history
(
    organization_id,
    changed_at
);


-- ============================================================
-- 5. DENYLIST CHANGE AUDIT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION
prohibited_attribute_firewall.audit_prohibited_term_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path =
    prohibited_attribute_firewall,
    audit_trail,
    pg_catalog
AS $$
DECLARE
    v_row prohibited_attribute_firewall.prohibited_terms%ROWTYPE;
    v_operation TEXT;
    v_actor UUID;
    v_session UUID;
BEGIN

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'Direct DELETE is prohibited. Use remove_prohibited_term().';
    END IF;

    v_row := NEW;

    v_operation :=
        CASE
            WHEN TG_OP = 'INSERT'
                THEN 'INSERT'

            WHEN OLD.removed_at IS NULL
             AND NEW.removed_at IS NOT NULL
                THEN 'REMOVE'

            ELSE 'UPDATE'
        END;

    v_actor :=
        NULLIF(
            current_setting('app.user_id', true),
            ''
        )::UUID;

    IF v_actor IS NULL THEN
        v_actor := v_row.added_by;
    END IF;

    v_session :=
        NULLIF(
            current_setting('app.session_id', true),
            ''
        )::UUID;

    INSERT INTO
    prohibited_attribute_firewall.prohibited_term_history
    (
        term_id,
        organization_id,
        term,
        language,
        transliterations,
        category,
        version,
        operation,
        changed_by,
        changed_at,
        removed_at
    )
    VALUES
    (
        v_row.id,
        v_row.organization_id,
        v_row.term,
        v_row.language,
        v_row.transliterations,
        v_row.category,
        v_row.version,
        v_operation,
        v_actor,
        CURRENT_TIMESTAMP,
        v_row.removed_at
    );

    PERFORM audit_trail.append_audit_event
    (
        v_row.organization_id,
        v_actor,
        NULL,
        v_session,
        'PROHIBITED_TERM_CHANGED',
        'prohibited_term',
        v_row.id,
        jsonb_build_object
        (
            'operation', v_operation,
            'term_id', v_row.id,
            'language', v_row.language,
            'category', v_row.category,
            'version', v_row.version,
            'removed_at', v_row.removed_at
        ),
        NULL,
        TRUE
    );

    RETURN NEW;

END;
$$;


DROP TRIGGER IF EXISTS
trg_audit_prohibited_term_change
ON prohibited_attribute_firewall.prohibited_terms;


CREATE TRIGGER
trg_audit_prohibited_term_change
AFTER INSERT OR UPDATE
ON prohibited_attribute_firewall.prohibited_terms
FOR EACH ROW
EXECUTE FUNCTION
prohibited_attribute_firewall.audit_prohibited_term_change();


-- ============================================================
-- 6. CONTROLLED DENYLIST INSERT
-- ============================================================

CREATE OR REPLACE FUNCTION
prohibited_attribute_firewall.add_prohibited_term
(
    p_organization_id UUID,
    p_term TEXT,
    p_language TEXT,
    p_transliterations TEXT[],
    p_category TEXT,
    p_added_by UUID
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path =
    prohibited_attribute_firewall,
    pg_catalog
AS $$
DECLARE
    v_id UUID := gen_random_uuid();
    v_version INTEGER;
BEGIN

    IF p_term IS NULL
       OR length(btrim(p_term)) = 0 THEN
        RAISE EXCEPTION
            'Prohibited term cannot be empty';
    END IF;

    IF p_language IS NULL
       OR p_language !~ '^[a-z]{2}$' THEN
        RAISE EXCEPTION
            'Language must be a lowercase two-letter code';
    END IF;

    IF p_category NOT IN
    (
        'religion',
        'caste',
        'community',
        'political',
        'persuasion',
        'custom'
    ) THEN
        RAISE EXCEPTION
            'Unsupported prohibited-term category: %',
            p_category;
    END IF;

    SELECT COALESCE(MAX(version), 0) + 1
      INTO v_version
      FROM prohibited_attribute_firewall.prohibited_terms
     WHERE organization_id IS NOT DISTINCT FROM p_organization_id
       AND language = p_language
       AND category = p_category;

    INSERT INTO
    prohibited_attribute_firewall.prohibited_terms
    (
        id,
        organization_id,
        term,
        language,
        transliterations,
        category,
        version,
        added_by
    )
    VALUES
    (
        v_id,
        p_organization_id,
        btrim(p_term),
        p_language,
        COALESCE(
            p_transliterations,
            ARRAY[]::TEXT[]
        ),
        p_category,
        v_version,
        p_added_by
    );

    RETURN v_id;

END;
$$;


-- ============================================================
-- 7. CONTROLLED DENYLIST UPDATE
-- ============================================================

CREATE OR REPLACE FUNCTION
prohibited_attribute_firewall.update_prohibited_term
(
    p_term_id UUID,
    p_term TEXT,
    p_language TEXT,
    p_transliterations TEXT[],
    p_category TEXT,
    p_changed_by UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path =
    prohibited_attribute_firewall,
    pg_catalog
AS $$
DECLARE
    v_organization_id UUID;
    v_next_version INTEGER;
BEGIN

    IF p_term IS NULL
       OR length(btrim(p_term)) = 0 THEN
        RAISE EXCEPTION
            'Prohibited term cannot be empty';
    END IF;

    IF p_language IS NULL
       OR p_language !~ '^[a-z]{2}$' THEN
        RAISE EXCEPTION
            'Language must be a lowercase two-letter code';
    END IF;

    IF p_category NOT IN
    (
        'religion',
        'caste',
        'community',
        'political',
        'persuasion',
        'custom'
    ) THEN
        RAISE EXCEPTION
            'Unsupported prohibited-term category: %',
            p_category;
    END IF;

    SELECT organization_id
      INTO v_organization_id
      FROM prohibited_attribute_firewall.prohibited_terms
     WHERE id = p_term_id
       AND removed_at IS NULL
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Active prohibited term % was not found',
            p_term_id;
    END IF;

    SELECT COALESCE(MAX(version), 0) + 1
      INTO v_next_version
      FROM prohibited_attribute_firewall.prohibited_terms
     WHERE organization_id IS NOT DISTINCT FROM v_organization_id
       AND language = p_language
       AND category = p_category;

    UPDATE prohibited_attribute_firewall.prohibited_terms
       SET term = btrim(p_term),
           language = p_language,
           transliterations =
               COALESCE(
                   p_transliterations,
                   ARRAY[]::TEXT[]
               ),
           category = p_category,
           version = v_next_version
     WHERE id = p_term_id;

    RETURN TRUE;

END;
$$;


-- ============================================================
-- 8. CONTROLLED DENYLIST REMOVAL
-- ============================================================
--
-- Removal is a versioned UPDATE, never a DELETE.
-- ============================================================

CREATE OR REPLACE FUNCTION
prohibited_attribute_firewall.remove_prohibited_term
(
    p_term_id UUID,
    p_removed_by UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path =
    prohibited_attribute_firewall,
    pg_catalog
AS $$
BEGIN

    UPDATE prohibited_attribute_firewall.prohibited_terms
       SET removed_at = CURRENT_TIMESTAMP,
           version = version + 1,
           added_by = p_removed_by
     WHERE id = p_term_id
       AND removed_at IS NULL;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Active prohibited term % was not found',
            p_term_id;
    END IF;

    RETURN TRUE;

END;
$$;


-- ============================================================
-- 9. PREVENT DIRECT DELETE OF DENYLIST
-- ============================================================

CREATE OR REPLACE FUNCTION
prohibited_attribute_firewall.prevent_term_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    RAISE EXCEPTION
        'Direct DELETE is prohibited. Use remove_prohibited_term().';

END;
$$;


DROP TRIGGER IF EXISTS
trg_prevent_prohibited_term_delete
ON prohibited_attribute_firewall.prohibited_terms;


CREATE TRIGGER
trg_prevent_prohibited_term_delete
BEFORE DELETE
ON prohibited_attribute_firewall.prohibited_terms
FOR EACH ROW
EXECUTE FUNCTION
prohibited_attribute_firewall.prevent_term_delete();


-- ============================================================
-- 10. CUSTOM-FIELD SCREENING
-- ============================================================
--
-- This function MUST be called by the custom-field creation path
-- before a custom field is persisted.
--
-- It checks:
--   * field name
--   * aliases
--   * active global denylist
--   * active tenant denylist
--   * transliterations
--
-- On match:
--   1. prohibited_alerts row is created
--   2. audit event is created
--   3. custom-field creation is rejected
-- ============================================================

CREATE OR REPLACE FUNCTION
prohibited_attribute_firewall.screen_custom_field
(
    p_organization_id UUID,
    p_field_name TEXT,
    p_language TEXT DEFAULT NULL,
    p_aliases TEXT[] DEFAULT ARRAY[]::TEXT[],
    p_actor_id UUID DEFAULT NULL,
    p_resource_id UUID DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path =
    prohibited_attribute_firewall,
    audit_trail,
    pg_catalog
AS $$
DECLARE
    v_match prohibited_attribute_firewall.prohibited_terms%ROWTYPE;
    v_candidates TEXT[];
    v_actor UUID;
    v_session UUID;
BEGIN

    IF p_field_name IS NULL
       OR length(btrim(p_field_name)) = 0 THEN
        RAISE EXCEPTION
            'Custom field name is required';
    END IF;

    IF p_language IS NOT NULL
       AND p_language !~ '^[a-z]{2}$' THEN
        RAISE EXCEPTION
            'Language must be a lowercase two-letter code';
    END IF;

    v_actor :=
        COALESCE
        (
            p_actor_id,
            NULLIF(
                current_setting('app.user_id', true),
                ''
            )::UUID
        );

    v_session :=
        NULLIF(
            current_setting('app.session_id', true),
            ''
        )::UUID;

    v_candidates :=
        ARRAY[
            lower(
                regexp_replace(
                    btrim(p_field_name),
                    '\s+',
                    ' ',
                    'g'
                )
            )
        ]
        ||
        COALESCE
        (
            ARRAY
            (
                SELECT lower(
                    regexp_replace(
                        btrim(x),
                        '\s+',
                        ' ',
                        'g'
                    )
                )
                FROM unnest(p_aliases) AS x
                WHERE x IS NOT NULL
                  AND length(btrim(x)) > 0
            ),
            ARRAY[]::TEXT[]
        );

    SELECT pt.*
      INTO v_match
      FROM prohibited_attribute_firewall.prohibited_terms pt
     WHERE pt.removed_at IS NULL
       AND
       (
           pt.organization_id IS NULL
           OR pt.organization_id = p_organization_id
       )
       AND
       (
           p_language IS NULL
           OR pt.language = p_language
       )
       AND EXISTS
       (
           SELECT 1
           FROM unnest(v_candidates) c(candidate)
           WHERE
               c.candidate =
               lower(
                   regexp_replace(
                       btrim(pt.term),
                       '\s+',
                       ' ',
                       'g'
                   )
               )
               OR EXISTS
               (
                   SELECT 1
                   FROM unnest(pt.transliterations) t(translit)
                   WHERE
                       c.candidate =
                       lower(
                           regexp_replace(
                               btrim(t.translit),
                               '\s+',
                               ' ',
                               'g'
                           )
                       )
               )
       )
     ORDER BY
         CASE
             WHEN pt.organization_id =
                  p_organization_id
             THEN 0
             ELSE 1
         END,
         pt.version DESC
     LIMIT 1;

    IF FOUND THEN

        INSERT INTO
        prohibited_attribute_firewall.prohibited_alerts
        (
            organization_id,
            attempted_field,
            matched_term_id,
            actor_id,
            resource_type,
            resource_id,
            blocked_at
        )
        VALUES
        (
            p_organization_id,
            p_field_name,
            v_match.id,
            v_actor,
            'custom_field',
            p_resource_id,
            CURRENT_TIMESTAMP
        );

        PERFORM audit_trail.append_audit_event
        (
            p_organization_id,
            v_actor,
            NULL,
            v_session,
            'CUSTOM_FIELD_BLOCKED',
            'custom_field',
            p_resource_id,
            jsonb_build_object
            (
                'attempted_field', p_field_name,
                'matched_term_id', v_match.id,
                'matched_category', v_match.category,
                'matched_language', v_match.language,
                'matched_version', v_match.version
            ),
            NULL,
            TRUE
        );

        RAISE EXCEPTION
            'Custom field creation blocked by prohibited-attribute policy';

    END IF;

    RETURN TRUE;

END;
$$;


-- ============================================================
-- 11. ACTIVE DENYLIST VIEW
-- ============================================================

CREATE OR REPLACE VIEW
prohibited_attribute_firewall.v_active_prohibited_terms
AS
SELECT
    id,
    organization_id,
    term,
    language,
    transliterations,
    category,
    version,
    added_by,
    added_at,
    removed_at
FROM prohibited_attribute_firewall.prohibited_terms
WHERE removed_at IS NULL;


-- ============================================================
-- 12. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS
idx_prohibited_terms_active_org_language
ON prohibited_attribute_firewall.prohibited_terms
(
    organization_id,
    language,
    category,
    version
)
WHERE removed_at IS NULL;


CREATE INDEX IF NOT EXISTS
idx_prohibited_terms_active_term
ON prohibited_attribute_firewall.prohibited_terms
(
    lower(term)
)
WHERE removed_at IS NULL;


CREATE INDEX IF NOT EXISTS
idx_prohibited_alerts_org_field
ON prohibited_attribute_firewall.prohibited_alerts
(
    organization_id,
    attempted_field,
    blocked_at
);


-- ============================================================
-- 13. CONTROLLED ROLES
-- ============================================================

DO $$
BEGIN

    IF NOT EXISTS
    (
        SELECT 1
        FROM pg_roles
        WHERE rolname =
              'prohibited_attribute_admin_role'
    ) THEN

        CREATE ROLE prohibited_attribute_admin_role
            NOLOGIN
            NOSUPERUSER
            NOBYPASSRLS;

    END IF;

    IF NOT EXISTS
    (
        SELECT 1
        FROM pg_roles
        WHERE rolname =
              'custom_field_screening_role'
    ) THEN

        CREATE ROLE custom_field_screening_role
            NOLOGIN
            NOSUPERUSER
            NOBYPASSRLS;

    END IF;

END
$$;


REVOKE ALL
ON TABLE prohibited_attribute_firewall.prohibited_terms
FROM PUBLIC;

REVOKE ALL
ON TABLE prohibited_attribute_firewall.prohibited_term_history
FROM PUBLIC;

REVOKE ALL
ON TABLE prohibited_attribute_firewall.prohibited_alerts
FROM PUBLIC;


REVOKE ALL
ON FUNCTION
prohibited_attribute_firewall.add_prohibited_term(
    UUID,
    TEXT,
    TEXT,
    TEXT[],
    TEXT,
    UUID
)
FROM PUBLIC;


REVOKE ALL
ON FUNCTION
prohibited_attribute_firewall.update_prohibited_term(
    UUID,
    TEXT,
    TEXT,
    TEXT[],
    TEXT,
    UUID
)
FROM PUBLIC;


REVOKE ALL
ON FUNCTION
prohibited_attribute_firewall.remove_prohibited_term(
    UUID,
    UUID
)
FROM PUBLIC;


REVOKE ALL
ON FUNCTION
prohibited_attribute_firewall.screen_custom_field(
    UUID,
    TEXT,
    TEXT,
    TEXT[],
    UUID,
    UUID
)
FROM PUBLIC;


GRANT USAGE
ON SCHEMA prohibited_attribute_firewall
TO
    prohibited_attribute_admin_role,
    custom_field_screening_role;


GRANT EXECUTE
ON FUNCTION
prohibited_attribute_firewall.add_prohibited_term(
    UUID,
    TEXT,
    TEXT,
    TEXT[],
    TEXT,
    UUID
)
TO prohibited_attribute_admin_role;


GRANT EXECUTE
ON FUNCTION
prohibited_attribute_firewall.update_prohibited_term(
    UUID,
    TEXT,
    TEXT,
    TEXT[],
    TEXT,
    UUID
)
TO prohibited_attribute_admin_role;


GRANT EXECUTE
ON FUNCTION
prohibited_attribute_firewall.remove_prohibited_term(
    UUID,
    UUID
)
TO prohibited_attribute_admin_role;


GRANT EXECUTE
ON FUNCTION
prohibited_attribute_firewall.screen_custom_field(
    UUID,
    TEXT,
    TEXT,
    TEXT[],
    UUID,
    UUID
)
TO custom_field_screening_role;


-- ============================================================
-- 14. VERIFICATION QUERIES
-- ============================================================

-- PROH-01: Must return zero rows.
SELECT
    table_schema,
    table_name,
    column_name
FROM information_schema.columns
WHERE table_schema NOT IN
(
    'pg_catalog',
    'information_schema',
    'prohibited_attribute_firewall',
    'audit_trail',
    'object_storage_security',
    'app'
)
AND
(
    lower(column_name) IN
    (
        'religion',
        'religion_id',
        'caste',
        'caste_id',
        'community',
        'community_id',
        'political_affiliation',
        'political_affiliation_id',
        'political_party',
        'political_party_id',
        'political_preference',
        'voting_intention',
        'voting_intention_id',
        'vote_intention',
        'voting_preference',
        'persuasion_score',
        'persuasion_propensity',
        'propensity_score',
        'political_propensity_score'
    )
    OR
    lower(column_name) ~
    '(religion|caste|community|political[_ ]?(affiliation|party|preference)|voting[_ ]?(intention|preference)|persuasion[_ ]?(score|propensity)|propensity[_ ]?score)'
);


-- PROH-02: Active, versioned multilingual denylist.
SELECT
    id,
    organization_id,
    term,
    language,
    category,
    version,
    added_at,
    removed_at
FROM prohibited_attribute_firewall.prohibited_terms
ORDER BY
    organization_id NULLS FIRST,
    category,
    language,
    version;


-- PROH-03: Denylist change history.
SELECT
    term_id,
    operation,
    version,
    changed_by,
    changed_at,
    removed_at
FROM prohibited_attribute_firewall.prohibited_term_history
ORDER BY changed_at DESC;


-- Custom-field screening function must exist.
SELECT
    routine_schema,
    routine_name,
    routine_type
FROM information_schema.routines
WHERE routine_schema =
      'prohibited_attribute_firewall'
AND routine_name IN
(
    'add_prohibited_term',
    'update_prohibited_term',
    'remove_prohibited_term',
    'screen_custom_field'
)
ORDER BY routine_name;


-- Denylist audit triggers.
SELECT
    tgname,
    pg_get_triggerdef(oid) AS trigger_definition
FROM pg_trigger
WHERE tgrelid =
      'prohibited_attribute_firewall.prohibited_terms'::regclass
AND NOT tgisinternal
ORDER BY tgname;


COMMIT;

-- ============================================================
-- END OF schema_prohibition_sensitive_attributes.sql
-- ============================================================
