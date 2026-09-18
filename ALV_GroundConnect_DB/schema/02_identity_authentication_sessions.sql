CREATE SCHEMA identity_authentication_sessions;


                    /*####################################################
                                    1. CREATING TABLE USERS
                     ######################################################*/

CREATE TABLE identity_authentication_sessions.users (
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    mobile_encrypted BYTEA NOT NULL,

    mobile_hash TEXT NOT NULL,

    name_encrypted BYTEA NOT NULL,

    preferred_language TEXT NOT NULL,

    lifecycle_status TEXT NOT NULL,

    mfa_required BOOLEAN NOT NULL,

    mfa_totp_secret_encrypted BYTEA NULL,

    import_batch_id UUID NULL,

    invited_at TIMESTAMPTZ NULL,

    activated_at TIMESTAMPTZ NULL,

    anonymised_at TIMESTAMPTZ NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT pk_users
        PRIMARY KEY (id),

    CONSTRAINT fk_users_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),
	-- yet to define import_batches table
    -- CONSTRAINT fk_users_import_batch
    --     FOREIGN KEY (import_batch_id)
    --     REFERENCES identity_authentication_sessions.import_batches(id),

    CONSTRAINT unq_users_mobile_encrypted
        UNIQUE (mobile_encrypted),

    CONSTRAINT unq_users_mobile_hash
        UNIQUE (mobile_hash),

    CONSTRAINT chk_users_preferred_language
        CHECK (
            preferred_language IN (
                'en',
                'hi',
                'kn',
                'ta',
                'te'
            )
        ),

    CONSTRAINT chk_users_lifecycle_status
        CHECK (
            lifecycle_status IN (
                'Invited',
                'Active',
                'Suspended',
                'Disabled',
                'Removed'
            )
        )
);

CREATE INDEX idx_users_organization_id
ON identity_authentication_sessions.users (organization_id);

CREATE INDEX idx_users_lifecycle_status
ON identity_authentication_sessions.users (lifecycle_status);



                    /*####################################################
	                                    2. CREATING TABLE DEVICES
                     ######################################################*/

					 
CREATE TABLE identity_authentication_sessions.devices (
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    user_id UUID NOT NULL,

    device_fingerprint TEXT NOT NULL,

    platform TEXT NOT NULL,

    trust_status TEXT NOT NULL,

    attestation_level TEXT NOT NULL,

    registered_at TIMESTAMPTZ NOT NULL,

    revoked_at TIMESTAMPTZ NULL,

    revoked_by UUID NULL,

    last_seen_at TIMESTAMPTZ NULL,

    public_key TEXT NOT NULL,


    -- Primary Key
    CONSTRAINT pk_devices
        PRIMARY KEY (id),

    -- Organization
    CONSTRAINT fk_devices_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    -- User
    CONSTRAINT fk_devices_user
        FOREIGN KEY (user_id)
        REFERENCES identity_authentication_sessions.users(id),

	CONSTRAINT fk_devices_revoked_by
	    FOREIGN KEY (revoked_by)
	    REFERENCES identity_authentication_sessions.users(id),

    -- Device fingerprint must be unique
    CONSTRAINT unq_devices_fingerprint
        UNIQUE (device_fingerprint),

    -- Platform
    CONSTRAINT chk_devices_platform
        CHECK (
            platform IN (
                'android',
                'ios',
                'web'
            )
        ),

    -- Trust status
    CONSTRAINT chk_devices_trust_status
        CHECK (
            trust_status IN (
                'registered',
                'step_up_pending',
                'revoked'
            )
        ),

    -- Attestation level
    CONSTRAINT chk_devices_attestation_level
        CHECK (
            attestation_level IN (
                'full',
                'degraded',
                'rooted_warned',
                'rooted_blocked'
            )
        )
);


CREATE INDEX idx_devices_organization_id
ON identity_authentication_sessions.devices (organization_id);

CREATE INDEX idx_devices_user_id
ON identity_authentication_sessions.devices (user_id);


                    /*####################################################
	                                   3. CREATING TABLE SESSIONS
                     ######################################################*/


CREATE TABLE identity_authentication_sessions.sessions (
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    session_family_id UUID NOT NULL,

    user_id UUID NOT NULL,

    device_id UUID NOT NULL,

    refresh_token_hash TEXT NOT NULL,

    access_token_jti TEXT NOT NULL,

    idle_expires_at TIMESTAMPTZ NOT NULL,

    absolute_expires_at TIMESTAMPTZ NOT NULL,

    revoked_at TIMESTAMPTZ NULL,

    revoke_reason TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    -- Primary Key
    CONSTRAINT pk_sessions
        PRIMARY KEY (id),

    -- Organization
    CONSTRAINT fk_sessions_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    -- User
    CONSTRAINT fk_sessions_user
        FOREIGN KEY (user_id)
        REFERENCES identity_authentication_sessions.users(id),

    -- Device
    CONSTRAINT fk_sessions_device
        FOREIGN KEY (device_id)
        REFERENCES identity_authentication_sessions.devices(id),

    -- Refresh token hash must be unique
    CONSTRAINT unq_sessions_refresh_token_hash
        UNIQUE (refresh_token_hash),

    -- Access token JTI must be unique
    CONSTRAINT unq_sessions_access_token_jti
        UNIQUE (access_token_jti),

    -- Valid revoke reasons
    CONSTRAINT chk_sessions_revoke_reason
        CHECK (
            revoke_reason IN (
                'logout',
                'device_revoked',
                'token_reuse',
                'admin',
                'transfer'
            )
            OR revoke_reason IS NULL
        )
);

CREATE INDEX idx_sessions_organization_id
ON identity_authentication_sessions.sessions (organization_id);

CREATE INDEX idx_sessions_session_family_id
ON identity_authentication_sessions.sessions (session_family_id);

CREATE INDEX idx_sessions_user_id
ON identity_authentication_sessions.sessions (user_id);

CREATE INDEX idx_sessions_device_id
ON identity_authentication_sessions.sessions (device_id);


                    /*####################################################
	                                   4. CREATING TABLE OTP_LOG
                     ######################################################*/


CREATE TABLE identity_authentication_sessions.otp_log (
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    mobile_hash TEXT NOT NULL,

    code_hash TEXT NOT NULL,

    purpose TEXT NOT NULL,

    issued_at TIMESTAMPTZ NOT NULL,

    expires_at TIMESTAMPTZ NOT NULL,

    used_at TIMESTAMPTZ NULL,

    invalidated_at TIMESTAMPTZ NULL,


    -- Primary Key
    CONSTRAINT pk_otp_log
        PRIMARY KEY (id),

    -- Valid OTP purpose
    CONSTRAINT chk_otp_log_purpose
        CHECK (
            purpose IN (
                'login',
                'mfa',
                'account_recovery',
                'tpi_approval',
                'citizen_track'
            )
        )
);	

CREATE INDEX idx_otp_log_mobile_hash
ON identity_authentication_sessions.otp_log (mobile_hash);



                    /*####################################################
	                                 5. CREATING TABLE AUTH_LOCKOUTS
                     ######################################################*/




CREATE TABLE identity_authentication_sessions.auth_lockouts (
    id UUID NOT NULL DEFAULT gen_random_uuid(),

    identity_hash TEXT NOT NULL,

    source_ip_hash TEXT NOT NULL,

    attempt_count INTEGER NOT NULL,

    locked_at TIMESTAMPTZ NULL,

    locked_until TIMESTAMPTZ NULL,

    unlock_path TEXT NULL,

    unlocked_at TIMESTAMPTZ NULL,

    unlocked_by UUID NULL,


    -- Primary Key
    CONSTRAINT pk_auth_lockouts
        PRIMARY KEY (id),

    -- User who performed manual unlock
    CONSTRAINT fk_auth_lockouts_unlocked_by
        FOREIGN KEY (unlocked_by)
        REFERENCES identity_authentication_sessions.users(id),

    -- Valid unlock path
    CONSTRAINT chk_auth_lockouts_unlock_path
        CHECK (
            unlock_path IN (
                'otp_recovery',
                'admin_manual',
                'auto_expiry'
            )
            OR unlock_path IS NULL
        )
);

CREATE INDEX idx_auth_lockouts_identity_hash
ON identity_authentication_sessions.auth_lockouts (identity_hash);

CREATE INDEX idx_auth_lockouts_source_ip_hash
ON identity_authentication_sessions.auth_lockouts (source_ip_hash);













