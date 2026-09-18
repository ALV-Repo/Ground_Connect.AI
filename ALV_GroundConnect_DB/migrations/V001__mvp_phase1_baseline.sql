-- V001__mvp_phase1_baseline.sql
-- Phase-1 baseline migration for the Ground Connect
-- Source: reviewed project SQL files supplied with this conversation.
-- IMPORTANT:
--   * This migration preserves source rules; it does not silently correct business values.
--   * Deferred cross-schema foreign keys are added after their referenced tables exist.
--   * pgcrypto/PostGIS are technical dependencies. This migration does not remove them on rollback.
--   * recurring_task_templates remains Phase 3, as specified in the source.
--   * users.import_batch_id remains without an FK because the supplied users source comments it out.
--   * message_recipients.created_at remains absent; therefore its requested inbox index is not created.

BEGIN;

-- Technical dependencies used by the supplied DDL.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS postgis;


-- ================================================================
-- SCHEMA: tenant_and_configuration
CREATE SCHEMA IF NOT EXISTS tenant_and_configuration;


-- SCHEMA: identity_authentication_sessions
CREATE SCHEMA IF NOT EXISTS identity_authentication_sessions;


-- SCHEMA: member_management_bulk_import
CREATE SCHEMA IF NOT EXISTS member_management_bulk_import;


-- SCHEMA: hierarchy_bitemporal_model
 CREATE SCHEMA IF NOT EXISTS hierarchy_bitemporal_model;

 
-- SCHEMA: delegation
 CREATE SCHEMA IF NOT EXISTS delegation;

 
-- SCHEMA: two_person_integrity
 CREATE SCHEMA IF NOT EXISTS two_person_integrity;

 
-- SCHEMA: messaging
 CREATE SCHEMA IF NOT EXISTS messaging;

 
-- SCHEMA: notifications
 CREATE SCHEMA IF NOT EXISTS notifications;

 
-- SCHEMA: prohibited_attribute_firewall
 CREATE SCHEMA IF NOT EXISTS prohibited_attribute_firewall;

 
-- SCHEMA: tasks_field_reports
 CREATE SCHEMA IF NOT EXISTS tasks_field_reports;

 
-- SCHEMA: vendor_support_elevation
 CREATE SCHEMA IF NOT EXISTS vendor_support_elevation;

 -- SCHEMA: audit_trail
CREATE SCHEMA IF NOT EXISTS audit_trail;

-- CREATING TABLE TENANTS

CREATE TABLE tenant_and_configuration.tenants
(
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	slug TEXT NOT NULL UNIQUE,
	name TEXT NOT NULL ,
	status TEXT NOT NULL DEFAULT 'active',
	max_hierarchy_depth SMALLINT NOT NULL DEFAULT 10,
	ai_enabled BOOLEAN NOT NULL DEFAULT TRUE,
	ai_provider_config JSONB NOT NULL DEFAULT '{}'::jsonb,
	tpi_thresholds JSONB NOT NULL DEFAULT '{}'::jsonb,
	sla_config JSONB,
	quiet_hours_from TIME,
	quiet_hours_to TIME,
	compliance_profile_id UUID,
	data_residency_region TEXT NOT NULL DEFAULT 'ap-south-1',
	created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

	CONSTRAINT chk_tenant_status
	CHECK (
		status IN (
			'active',
			'suspended',
			'offboarded'
		)
	),

	CONSTRAINT chk_hierarchy_depth
	CHECK (
		max_hierarchy_depth BETWEEN 1 AND 10
	),

	CONSTRAINT chk_residency_region
	CHECK (
		data_residency_region = 'ap-south-1'
	)
);

-- ALTER TABLE tenant_and_configuration.tenants
-- ADD CONSTRAINT fk_tenant_compliance_profile
-- FOREIGN KEY (compliance_profile_id)
-- REFERENCES compliance_mode.compliance_profiles(id);

-- CREATING TABLE HIERARCHY_LEVELS

CREATE TABLE tenant_and_configuration.hierarchy_levels
(
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	organization_id UUID NOT NULL,
	level_index SMALLINT NOT NULL,
	name TEXT NOT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

	CONSTRAINT fk_hierarchy_levels_organization
		FOREIGN KEY(organization_id)
		REFERENCES tenant_and_configuration.tenants(id),

	CONSTRAINT unq_hirarchy_levels_org_level
		UNIQUE (organization_id, level_index),

	CONSTRAINT chk_hierarchy_level_index
	CHECK (level_index BETWEEN 0 AND 9)
);

CREATE INDEX idx_hierarchy_levels_organization_id
ON tenant_and_configuration.hierarchy_levels (organization_id);


-- CREATING TABLE USERS


CREATE TABLE identity_authentication_sessions.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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




-- CREATING TABLE DEVICES

CREATE TABLE identity_authentication_sessions.devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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


                   
-- CREATING TABLE SESSIONS
                     


CREATE TABLE identity_authentication_sessions.sessions (
   id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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


                    
-- CREATING TABLE OTP_LOG                     


CREATE TABLE identity_authentication_sessions.otp_log (
   id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mobile_hash TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    purpose TEXT NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ NULL,
    invalidated_at TIMESTAMPTZ NULL,


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



                    
 -- CREATING TABLE AUTH_LOCKOUTS                   




CREATE TABLE identity_authentication_sessions.auth_lockouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_hash TEXT NOT NULL,
    source_ip_hash TEXT NOT NULL,
    attempt_count INTEGER NOT NULL,
    locked_at TIMESTAMPTZ NULL,
    locked_until TIMESTAMPTZ NULL,
    unlock_path TEXT NULL,
    unlocked_at TIMESTAMPTZ NULL,
    unlocked_by UUID NULL,


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


-- CREATING TABLE IMPORT_BATCHES


CREATE TABLE member_management_bulk_import.import_batches
(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    uploaded_by UUID NOT NULL,
    filename TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    accepted_count INTEGER NULL,
    rejected_count INTEGER NULL,
    dry_run_report JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    committed_at TIMESTAMPTZ NULL,


    -- Foreign Key: Tenant / Organization
    CONSTRAINT fk_import_batches_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    -- Foreign Key: User who uploaded the file
    CONSTRAINT fk_import_batches_uploaded_by
        FOREIGN KEY (uploaded_by)
        REFERENCES identity_authentication_sessions.users(id),

    -- Allowed import statuses
    CONSTRAINT chk_import_batches_status
        CHECK (
            status IN (
                'dry_run',
                'dry_run_complete',
                'committing',
                'committed',
                'failed'
            )
        )
);


-- INDEX
CREATE INDEX idx_import_batches_organization_id
    ON member_management_bulk_import.import_batches (organization_id);


-- CREATING TABLE NODES                     

					 
CREATE TABLE hierarchy_bitemporal_model.nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    parent_id UUID NULL,
    level_id UUID NOT NULL,
    name TEXT NOT NULL,
    code TEXT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    orphaned BOOLEAN NOT NULL DEFAULT FALSE,
    orphaned_since TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT fk_nodes_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_nodes_parent
        FOREIGN KEY (parent_id)
        REFERENCES hierarchy_bitemporal_model.nodes(id),

    CONSTRAINT fk_nodes_level
        FOREIGN KEY (level_id)
        REFERENCES tenant_and_configuration.hierarchy_levels(id),

    CONSTRAINT chk_nodes_status
        CHECK (
            status IN (
                'active',
                'suspended',
                'archived'
            )
        ),

    CONSTRAINT chk_nodes_parent_self_reference
        CHECK (
            parent_id IS NULL OR parent_id <> id
        ),

    CONSTRAINT chk_nodes_orphaned_consistency
        CHECK (
            (orphaned = TRUE AND orphaned_since IS NOT NULL)
            OR
            (orphaned = FALSE AND orphaned_since IS NULL)
        )
);

-- INDEXES

CREATE INDEX idx_nodes_organization_id
    ON hierarchy_bitemporal_model.nodes (organization_id);

CREATE INDEX idx_nodes_parent_id
    ON hierarchy_bitemporal_model.nodes (parent_id);


CREATE INDEX idx_nodes_organization_parent
    ON hierarchy_bitemporal_model.nodes
    (organization_id, parent_id);

CREATE UNIQUE INDEX uq_nodes_organization_code
    ON hierarchy_bitemporal_model.nodes
    (organization_id, code)
    WHERE code IS NOT NULL;
	

 -- CREATING TABLE NODE_ASSIGNMENTS


CREATE TABLE hierarchy_bitemporal_model.node_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    user_id UUID NOT NULL,
    node_id UUID NOT NULL,
    role TEXT NOT NULL,
    is_responsible_person BOOLEAN NOT NULL DEFAULT FALSE,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recorded_by UUID NOT NULL,
    transfer_id UUID NULL,
    delegation_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT fk_node_assignments_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_node_assignments_user
        FOREIGN KEY (user_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_node_assignments_node
        FOREIGN KEY (node_id)
        REFERENCES hierarchy_bitemporal_model.nodes(id),

    CONSTRAINT fk_node_assignments_recorded_by
        FOREIGN KEY (recorded_by)
        REFERENCES identity_authentication_sessions.users(id),

    

    CONSTRAINT chk_node_assignments_role
        CHECK (
            role IN (
                'leader',
                'coordinator',
                'field_worker',
                'compliance',
                'security_admin',
                'org_admin',
                'citizen',
                'integration_client'
            )
        ),

    CONSTRAINT chk_node_assignments_valid_period
        CHECK (
            valid_to IS NULL
            OR valid_to > valid_from
        ),

    CONSTRAINT chk_node_assignments_transfer_delegation
        CHECK (
            NOT (
                transfer_id IS NOT NULL
                AND delegation_id IS NOT NULL
            )
        )
);

-- INDEXES

CREATE INDEX idx_node_assignments_organization_id
    ON hierarchy_bitemporal_model.node_assignments
    (organization_id);

CREATE INDEX idx_node_assignments_user_validity
    ON hierarchy_bitemporal_model.node_assignments
    (user_id, valid_from, valid_to);
	
CREATE INDEX idx_node_assignments_node_validity
    ON hierarchy_bitemporal_model.node_assignments
    (node_id, valid_from, valid_to);

CREATE UNIQUE INDEX uq_node_assignments_responsible_person
    ON hierarchy_bitemporal_model.node_assignments
    (node_id, is_responsible_person)
    WHERE is_responsible_person = TRUE
      AND valid_to IS NULL;




-- CREATING TABLE TRANSFERS			 



CREATE TABLE hierarchy_bitemporal_model.transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    ordered_by UUID NOT NULL,
    user_id UUID NOT NULL,
    from_node_id UUID NOT NULL,
    to_node_id UUID NOT NULL,
    from_role TEXT NOT NULL,
    to_role TEXT NOT NULL,
    effective_date TIMESTAMPTZ NOT NULL,
    stated_reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    tpi_request_id UUID NULL,
    bulk_batch_id UUID NULL,
    committed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT fk_transfers_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_transfers_ordered_by
        FOREIGN KEY (ordered_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_transfers_user
        FOREIGN KEY (user_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_transfers_from_node
        FOREIGN KEY (from_node_id)
        REFERENCES hierarchy_bitemporal_model.nodes(id),

    CONSTRAINT fk_transfers_to_node
        FOREIGN KEY (to_node_id)
        REFERENCES hierarchy_bitemporal_model.nodes(id),

    CONSTRAINT chk_transfers_different_nodes
        CHECK (from_node_id <> to_node_id),

    CONSTRAINT chk_transfers_status
        CHECK (
            status IN (
                'pending',
                'committed',
                'rolled_back'
            )
        ),

    CONSTRAINT chk_transfers_stated_reason
        CHECK (length(trim(stated_reason)) > 0)
);

-- INDEXES

CREATE INDEX idx_transfers_organization_id
    ON hierarchy_bitemporal_model.transfers (organization_id);


CREATE INDEX idx_transfers_bulk_batch_id
    ON hierarchy_bitemporal_model.transfers (bulk_batch_id);


-- CRATING TABLE DELEGATIONS

CREATE TABLE delegation.delegations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    delegator_id UUID NOT NULL,
    delegatee_id UUID NOT NULL,
    scope JSONB NOT NULL,
    depth SMALLINT NOT NULL
        CHECK (depth >= 1),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ NULL,
    revoked_by UUID NULL,
    created_at TIMESTAMPTZ NOT NULL,



    -- Foreign Keys
    CONSTRAINT fk_delegations_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_delegations_delegator
        FOREIGN KEY (delegator_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_delegations_delegatee
        FOREIGN KEY (delegatee_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_delegations_revoked_by
        FOREIGN KEY (revoked_by)
        REFERENCES identity_authentication_sessions.users(id)
);



-- INDEXES
CREATE INDEX idx_delegations_organization_id
ON delegation.delegations (organization_id);

CREATE INDEX idx_delegations_delegator_id
ON delegation.delegations (delegator_id);

CREATE INDEX idx_delegations_delegatee_id
ON delegation.delegations (delegatee_id);

-- DEPENDENT CONSTRAINT

ALTER TABLE hierarchy_bitemporal_model.node_assignments
ADD CONSTRAINT fk_node_assignments_delegation
    FOREIGN KEY (delegation_id)
    REFERENCES delegation.delegations(id);

	

-- creating table tpi_requests


CREATE TABLE two_person_integrity.tpi_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    action_type TEXT NOT NULL,
    requester_id UUID NOT NULL,
    payload JSONB NOT NULL,
    threshold_context JSONB NOT NULL,
    status TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    break_glass BOOLEAN NOT NULL DEFAULT FALSE,
    break_glass_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT fk_tpi_requests_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_tpi_requests_requester
        FOREIGN KEY (requester_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_tpi_requests_action_type
        CHECK (
            action_type IN (
                'bulk_export',
                'mass_message',
                'bulk_reassign',
                'role_grant',
                'audit_delete',
                'ai_provider_change',
                'security_control_disable',
                'prohibited_firewall_disable',
                'hierarchy_bulk_transfer'
            )
        ),

    CONSTRAINT chk_tpi_requests_status
        CHECK (
            status IN (
                'pending',
                'approved',
                'rejected',
                'expired',
                'break_glass'
            )
        )
);

CREATE INDEX idx_tpi_requests_organization_id
    ON two_person_integrity.tpi_requests (organization_id);

CREATE INDEX idx_tpi_requests_status
    ON two_person_integrity.tpi_requests (status);




-- creating table tpi_approvals


CREATE TABLE two_person_integrity.tpi_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    request_id UUID NOT NULL,
    approver_id UUID NOT NULL,
    mfa_verified_at TIMESTAMPTZ NOT NULL,
    decision TEXT NOT NULL,
    decision_reason TEXT NULL,
    decided_at TIMESTAMPTZ NOT NULL,


    CONSTRAINT fk_tpi_approvals_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_tpi_approvals_request
        FOREIGN KEY (request_id)
        REFERENCES two_person_integrity.tpi_requests(id),

    CONSTRAINT fk_tpi_approvals_approver
        FOREIGN KEY (approver_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_tpi_approvals_decision
        CHECK (
            decision IN ('approved', 'rejected')
        )
);
CREATE INDEX idx_tpi_approvals_request_id
    ON two_person_integrity.tpi_approvals (request_id);
	

-- CREATING TABLE MESSAGES


CREATE TABLE messaging.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    sender_id UUID NOT NULL,
    sender_assignment_id UUID NOT NULL,
    message_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_encrypted BYTEA NOT NULL,
    body_language TEXT NOT NULL,
    target_spec JSONB NOT NULL,
    propagation_policy JSONB NOT NULL,
    response_mode TEXT NOT NULL,
    scheduled_for TIMESTAMPTZ NULL,
    dispatch_started_at TIMESTAMPTZ NULL,
    halt_requested_at TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NULL,
    tpi_request_id UUID NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT fk_messages_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_messages_sender
        FOREIGN KEY (sender_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_messages_sender_assignment
        FOREIGN KEY (sender_assignment_id)
        REFERENCES hierarchy_bitemporal_model.node_assignments(id),

    CONSTRAINT fk_messages_tpi_request
        FOREIGN KEY (tpi_request_id)
        REFERENCES two_person_integrity.tpi_requests(id),

    CONSTRAINT chk_messages_message_type
        CHECK (
            message_type IN (
                'Announcement',
                'Instruction',
                'Task-linked',
                'Information',
                'Meeting',
                'Document',
                'Survey',
                'Emergency',
                'Issue-linked'
            )
        ),

    CONSTRAINT chk_messages_response_mode
        CHECK (
            response_mode IN (
                'none',
                'acknowledge',
                'reply_parent',
                'reply_chain',
                'aggregated',
                'escalation'
            )
        ),

    CONSTRAINT chk_messages_status
        CHECK (
            status IN (
                'draft',
                'scheduled',
                'dispatching',
                'dispatched',
                'halted',
                'expired'
            )
        )
);

-- INDEXES

CREATE INDEX idx_messages_organization_id
    ON messaging.messages (organization_id);

CREATE INDEX idx_messages_sender_id
    ON messaging.messages (sender_id);

CREATE INDEX idx_messages_status
    ON messaging.messages (status);
	


-- CREATING TABLE MESSAGE_RECIPIENTS


CREATE TABLE messaging.message_recipients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    message_id UUID NOT NULL,
    recipient_id UUID NOT NULL,
    recipient_assignment_id UUID NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    failure_reason TEXT NULL,
    queued_at TIMESTAMPTZ NULL,
    delivered_at TIMESTAMPTZ NULL,
    read_at TIMESTAMPTZ NULL,
    acknowledged_at TIMESTAMPTZ NULL,
    revoked_at TIMESTAMPTZ NULL,
    offline_purge_pending BOOLEAN NOT NULL DEFAULT FALSE,


    CONSTRAINT fk_message_recipients_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_message_recipients_message
        FOREIGN KEY (message_id)
        REFERENCES messaging.messages(id),

    CONSTRAINT fk_message_recipients_recipient
        FOREIGN KEY (recipient_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_message_recipients_assignment
        FOREIGN KEY (recipient_assignment_id)
        REFERENCES hierarchy_bitemporal_model.node_assignments(id),

    CONSTRAINT chk_message_recipients_channel
        CHECK (
            channel IN (
                'push',
                'in_app',
                'sms',
                'email',
                'whatsapp'
            )
        ),

    CONSTRAINT chk_message_recipients_status
        CHECK (
            status IN (
                'queued',
                'delivered',
                'read',
                'acknowledged',
                'failed',
                'revoked'
            )
        )
);

-- INDEXES
CREATE INDEX idx_message_recipients_organization_id
    ON messaging.message_recipients (organization_id);

CREATE INDEX idx_message_recipients_message_id
    ON messaging.message_recipients (message_id);

CREATE INDEX idx_message_recipients_recipient_id
    ON messaging.message_recipients (recipient_id);

CREATE INDEX idx_message_recipients_status
    ON messaging.message_recipients (status);

CREATE INDEX idx_message_recipients_message_status
    ON messaging.message_recipients (message_id, status);
	
/* CANT CREATE SECOND COMPOSITE INDEX (recipient_id, created_at DESC) for inbox queries , 
BECAUSE CREATED_AT COLUMN NOT PRESENT IN  message_recipients*/


-- CREATING TABLE MESSAGE_GROUPS

CREATE TABLE messaging.message_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    spec JSONB NOT NULL,
    member_ids UUID[] NOT NULL,
    last_recomputed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT fk_message_groups_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT chk_message_groups_type
        CHECK (
            type IN (
                'hierarchy_level',
                'node_subtree',
                'custom'
            )
        ),

    CONSTRAINT chk_message_groups_spec_object
        CHECK (
            jsonb_typeof(spec) = 'object'
        )
);

CREATE INDEX idx_message_groups_organization_id
    ON messaging.message_groups (organization_id);

	

-- creating table notification_preferences


CREATE TABLE notifications.notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    user_id UUID NOT NULL,
    channels JSONB NOT NULL,
    quiet_hours_from TIME NULL,
    quiet_hours_to TIME NULL,
    emergency_override BOOLEAN NOT NULL DEFAULT TRUE,
    security_override BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,



    CONSTRAINT fk_notification_preferences_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_notification_preferences_user
        FOREIGN KEY (user_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT uq_notification_preferences_user
        UNIQUE (user_id),

    CONSTRAINT chk_notification_preferences_emergency_override
        CHECK (emergency_override = TRUE),

    CONSTRAINT chk_notification_preferences_security_override
        CHECK (security_override = TRUE)
);


-- creatig table notification_log


CREATE TABLE notifications.notification_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    user_id UUID NOT NULL,
    message_id UUID NULL,
    channel TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    cost_usd NUMERIC(10,6) NULL,
    sent_at TIMESTAMPTZ NULL,
    delivered_at TIMESTAMPTZ NULL,
    failed_reason TEXT NULL,



    CONSTRAINT fk_notification_log_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_notification_log_user
        FOREIGN KEY (user_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_notification_log_message
        FOREIGN KEY (message_id)
        REFERENCES messaging.messages(id),

    CONSTRAINT chk_notification_log_channel
        CHECK (
            channel IN (
                'push',
                'in_app',
                'sms',
                'email',
                'whatsapp'
            )
        ),

    CONSTRAINT chk_notification_log_status
        CHECK (
            status IN (
                'sent',
                'delivered',
                'failed'
            )
        )
);

-- indexes
CREATE INDEX idx_notification_log_organization_id
    ON notifications.notification_log (organization_id);

CREATE INDEX idx_notification_log_user_id
    ON notifications.notification_log (user_id);

	

-- CREATING TABLE PROHIBITED_TERMS



CREATE TABLE prohibited_attribute_firewall.prohibited_terms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NULL,
    term TEXT NOT NULL,
    language TEXT NOT NULL,
    transliterations TEXT[] NOT NULL,
    category TEXT NOT NULL,
    version INTEGER NOT NULL,
    added_by UUID NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    removed_at TIMESTAMPTZ NULL,



    CONSTRAINT fk_prohibited_terms_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_prohibited_terms_added_by
        FOREIGN KEY (added_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_prohibited_terms_language
        CHECK (
            language IN (
                'en',
                'hi',
                'kn' )
        ),

    CONSTRAINT chk_prohibited_terms_category
        CHECK (
            category IN (
                'religion',
                'caste',
                'community',
                'political',
                'persuasion',
                'custom')
        )
);



-- CREATING TABLE PROHIBITED_ALERTS



CREATE TABLE prohibited_attribute_firewall.prohibited_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    attempted_field TEXT NOT NULL,
    matched_term_id UUID NOT NULL,
    actor_id UUID NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID NULL,
    blocked_at TIMESTAMPTZ NOT NULL,
    reported_to_co_at TIMESTAMPTZ NULL,
    compliance_officer_id UUID NULL,


    CONSTRAINT fk_prohibited_alerts_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_prohibited_alerts_matched_term
        FOREIGN KEY (matched_term_id)
        REFERENCES prohibited_attribute_firewall.prohibited_terms(id),

    CONSTRAINT fk_prohibited_alerts_actor
        FOREIGN KEY (actor_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_prohibited_alerts_compliance_officer
        FOREIGN KEY (compliance_officer_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_prohibited_alerts_resource_type
        CHECK (
            resource_type IN (
                'custom_field',
                'free_text',
                'export'
            )
        )
);
-- INDEXES
CREATE INDEX idx_prohibited_alerts_organization_id
    ON prohibited_attribute_firewall.prohibited_alerts (organization_id);

CREATE INDEX idx_prohibited_alerts_blocked_at
    ON prohibited_attribute_firewall.prohibited_alerts (blocked_at);
	

-- CREATING TABLE tasks



CREATE TABLE tasks_field_reports.tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    title TEXT NOT NULL,
    description TEXT NULL,
    creator_id UUID NOT NULL,
    creator_assignment_id UUID NOT NULL,
    assignee_id UUID NOT NULL,
    assignee_node_id UUID NOT NULL,
    parent_task_id UUID NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    deadline TIMESTAMPTZ NULL,
    location GEOGRAPHY(POINT, 4326) NULL,
    escalation_rule JSONB NULL,
    working_hours_calendar_id UUID NULL,
    response_requirement TEXT NULL,
    blocked_reason TEXT NULL,
    blocked_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    accepted_at TIMESTAMPTZ NULL,
    rejected_at TIMESTAMPTZ NULL,
    overdue_detected_at TIMESTAMPTZ NULL,
    recurring_template_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT fk_tasks_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_tasks_creator
        FOREIGN KEY (creator_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_tasks_creator_assignment
        FOREIGN KEY (creator_assignment_id)
        REFERENCES hierarchy_bitemporal_model.node_assignments(id),

    CONSTRAINT fk_tasks_assignee
        FOREIGN KEY (assignee_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_tasks_assignee_node
        FOREIGN KEY (assignee_node_id)
        REFERENCES hierarchy_bitemporal_model.nodes(id),

    CONSTRAINT fk_tasks_parent_task
        FOREIGN KEY (parent_task_id)
        REFERENCES tasks_field_reports.tasks(id),

    

    CONSTRAINT chk_tasks_priority
        CHECK (
            priority IN (
                'High',
                'Medium',
                'Low'
            )
        ),

    CONSTRAINT chk_tasks_status
        CHECK (
            status IN (
                'Assigned',
                'Accepted',
                'In_Progress',
                'Blocked',
                'Completed',
                'Rejected',
                'Overdue'
            )
        ),

    CONSTRAINT chk_tasks_response_requirement
        CHECK (
            response_requirement IN (
                'text',
                'photo',
                'video',
                'voice',
                'location'
            )
            OR response_requirement IS NULL
        )
);

-- INDEXES

CREATE INDEX idx_tasks_organization_id
    ON tasks_field_reports.tasks (organization_id);

CREATE INDEX idx_tasks_assignee_id
    ON tasks_field_reports.tasks (assignee_id);

CREATE INDEX idx_tasks_status
    ON tasks_field_reports.tasks (status);



-- CREATING TABLE TASK_HISTORY


CREATE TABLE tasks_field_reports.task_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    task_id UUID NOT NULL,
    from_status TEXT NULL,
    to_status TEXT NOT NULL,
    actor_id UUID NOT NULL,
    actor_assignment_id UUID NOT NULL,
    reason TEXT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT fk_task_history_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_task_history_task
        FOREIGN KEY (task_id)
        REFERENCES tasks_field_reports.tasks(id),

    CONSTRAINT fk_task_history_actor
        FOREIGN KEY (actor_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_task_history_actor_assignment
        FOREIGN KEY (actor_assignment_id)
        REFERENCES hierarchy_bitemporal_model.node_assignments(id)
);
-- INDEXES
CREATE INDEX idx_task_history_organization_id
    ON tasks_field_reports.task_history (organization_id);

CREATE INDEX idx_task_history_task_id
    ON tasks_field_reports.task_history (task_id);
	


-- CREATING TABLE FIELD_REPORTS


CREATE TABLE tasks_field_reports.field_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    task_id UUID NOT NULL,
    reporter_id UUID NOT NULL,
    reporter_assignment_id UUID NOT NULL,
    text TEXT NULL,
    completion_pct SMALLINT NULL,
    location GEOGRAPHY(POINT, 4326) NULL,
    integrity_status TEXT NOT NULL,
    integrity_flags JSONB NOT NULL,
    attested_count INTEGER NOT NULL DEFAULT 0,
    unattested_count INTEGER NOT NULL DEFAULT 0,
    flagged_count INTEGER NOT NULL DEFAULT 0,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT fk_field_reports_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_field_reports_task
        FOREIGN KEY (task_id)
        REFERENCES tasks_field_reports.tasks(id),

    CONSTRAINT fk_field_reports_reporter
        FOREIGN KEY (reporter_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_field_reports_reporter_assignment
        FOREIGN KEY (reporter_assignment_id)
        REFERENCES hierarchy_bitemporal_model.node_assignments(id),

    CONSTRAINT chk_field_reports_completion_pct
        CHECK (
            completion_pct BETWEEN 0 AND 100
            OR completion_pct IS NULL
        ),

    CONSTRAINT chk_field_reports_integrity_status
        CHECK (
            integrity_status IN (
                'verified',
                'unverified',
                'inconsistent'
            )
        ),

    CONSTRAINT chk_field_reports_integrity_flags_array
        CHECK (
            jsonb_typeof(integrity_flags) = 'array'
        ),

    CONSTRAINT chk_field_reports_attested_count
        CHECK (attested_count >= 0),

    CONSTRAINT chk_field_reports_unattested_count
        CHECK (unattested_count >= 0),

    CONSTRAINT chk_field_reports_flagged_count
        CHECK (flagged_count >= 0)
);

-- INDEXES

CREATE INDEX idx_field_reports_organization_id
    ON tasks_field_reports.field_reports (organization_id);

CREATE INDEX idx_field_reports_task_id
    ON tasks_field_reports.field_reports (task_id);
	

-- CREATING TABLE EVIDENCE_MEDIA


CREATE TABLE tasks_field_reports.evidence_media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    report_id UUID NOT NULL,
    media_type TEXT NOT NULL,
    capture_method TEXT NOT NULL,
    trust_class TEXT NOT NULL,
    object_storage_key TEXT NOT NULL,
    media_hash TEXT NOT NULL,
    phash TEXT NULL,
    phash_duplicate_of UUID NULL,
    exif_stripped BOOLEAN NOT NULL,
    original_metadata_key TEXT NULL,
    capture_at TIMESTAMPTZ NULL,
    capture_location_lat NUMERIC(10,7) NULL,
    capture_location_lng NUMERIC(10,7) NULL,
    device_id UUID NULL,
    signed_attestation JSONB NULL,
    attestation_status TEXT NOT NULL,
    coherence_flags JSONB NOT NULL,
    tampered BOOLEAN NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT fk_evidence_media_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_evidence_media_report
        FOREIGN KEY (report_id)
        REFERENCES tasks_field_reports.field_reports(id),

    CONSTRAINT fk_evidence_media_phash_duplicate_of
        FOREIGN KEY (phash_duplicate_of)
        REFERENCES tasks_field_reports.evidence_media(id),

    CONSTRAINT fk_evidence_media_device
        FOREIGN KEY (device_id)
        REFERENCES identity_authentication_sessions.devices(id),

    CONSTRAINT chk_evidence_media_media_type
        CHECK (
            media_type IN (
                'photo',
                'video',
                'audio',
                'document'
            )
        ),

    CONSTRAINT chk_evidence_media_capture_method
        CHECK (
            capture_method IN (
                'in_app_camera',
                'in_app_recorder',
                'gallery_upload',
                'offline_capture'
            )
        ),

    CONSTRAINT chk_evidence_media_trust_class
        CHECK (
            trust_class IN (
                'attested',
                'attested_offline',
                'unattested'
            )
        ),

    CONSTRAINT chk_evidence_media_attestation_status
        CHECK (
            attestation_status IN (
                'attested',
                'attested_offline',
                'unattested',
                'tampered'
            )
        ),

    CONSTRAINT chk_evidence_media_coherence_flags_array
        CHECK (
            jsonb_typeof(coherence_flags) = 'array'
        )
);
-- INDEXES
CREATE INDEX idx_evidence_media_organization_id
    ON tasks_field_reports.evidence_media (organization_id);

CREATE INDEX idx_evidence_media_report_id
    ON tasks_field_reports.evidence_media (report_id);


-- CREATING TABLE WORKING_HOURS_CALENDARS


CREATE TABLE tasks_field_reports.working_hours_calendars (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    working_days INTEGER[] NOT NULL,
    working_from TIME NOT NULL,
    working_to TIME NOT NULL,
    holidays DATE[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT fk_working_hours_calendars_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id)
);

-- INDEX
CREATE INDEX idx_working_hours_calendars_organization_id
    ON tasks_field_reports.working_hours_calendars (organization_id);




/* DEPENDENT CONSTRAINTS*/
ALTER TABLE tasks_field_reports.tasks
ADD CONSTRAINT fk_tasks_working_hours_calendar
        FOREIGN KEY (working_hours_calendar_id)
        REFERENCES tasks_field_reports.working_hours_calendars(id)

/* RUN AFTER CREATING recurring_task_templates
THIS TABLE IN PHASE 3

CONSTRAINT fk_tasks_recurring_template
        FOREIGN KEY (recurring_template_id)
        REFERENCES recurring_task_templates(id),
	*/

-- creating table support_elevations

CREATE TABLE vendor_support_elevation.support_elevations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    operator_id UUID NOT NULL,
    approved_by UUID NOT NULL,
    stated_reason TEXT NOT NULL,
    duration_hours SMALLINT NOT NULL DEFAULT 4,
    granted_at TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NULL,
    expired_at TIMESTAMPTZ NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    CONSTRAINT fk_support_elevations_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_support_elevations_operator
        FOREIGN KEY (operator_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_support_elevations_approved_by
        FOREIGN KEY (approved_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_support_elevations_duration_hours
        CHECK (duration_hours <= 24),

    CONSTRAINT chk_support_elevations_status
        CHECK (
            status IN (
                'pending',
                'active',
                'expired',
                'revoked'
            )
        )
);

CREATE INDEX idx_support_elevations_organization_id
    ON vendor_support_elevation.support_elevations (organization_id);

	

-- creating table audit_events


CREATE TABLE audit_trail.audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    seq BIGSERIAL NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL,
    actor_id UUID NULL,
    acting_for_id UUID NULL,
    session_id UUID NULL,
    action_type TEXT NOT NULL,
    resource_type TEXT NULL,
    resource_id UUID NULL,
    payload JSONB NULL,
    ip_hash TEXT NULL,
    legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,


    -- Sequence must be unique
    CONSTRAINT unq_audit_events_seq
        UNIQUE (seq)
);

CREATE INDEX idx_audit_events_organization_id
ON audit_trail.audit_events (organization_id);

CREATE INDEX idx_audit_events_action_type
ON audit_trail.audit_events (action_type);

CREATE INDEX idx_audit_events_resource_type
ON audit_trail.audit_events (resource_type);

CREATE INDEX idx_audit_events_created_at
ON audit_trail.audit_events (created_at);



-- creating table audit_checkpoints

CREATE TABLE audit_trail.audit_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    seq_at_checkpoint BIGINT NOT NULL,
    chain_hash TEXT NOT NULL,
    checkpointed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    external_storage_ref TEXT NOT NULL,

);

CREATE INDEX idx_audit_checkpoints_organization_id
    ON audit_trail.audit_checkpoints (organization_id);

-- ================================================================
-- DEFERRED FOREIGN KEYS
-- ================================================================

ALTER TABLE hierarchy_bitemporal_model.node_assignments
    ADD CONSTRAINT fk_node_assignments_transfer
    FOREIGN KEY (transfer_id)
    REFERENCES hierarchy_bitemporal_model.transfers(id);

ALTER TABLE hierarchy_bitemporal_model.node_assignments
    ADD CONSTRAINT fk_node_assignments_delegation
    FOREIGN KEY (delegation_id)
    REFERENCES delegation.delegations(id);

ALTER TABLE hierarchy_bitemporal_model.transfers
    ADD CONSTRAINT fk_transfers_tpi_request
    FOREIGN KEY (tpi_request_id)
    REFERENCES two_person_integrity.tpi_requests(id);

COMMIT;
