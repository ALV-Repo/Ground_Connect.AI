-- ============================================================
-- PHASE 2: DOCUMENTS AND MEETINGS
-- ============================================================

CREATE SCHEMA IF NOT EXISTS documents_meetings;

-- documents

CREATE TABLE documents_meetings.documents
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    uploader_id UUID NOT NULL,
    title TEXT NOT NULL,
    object_storage_key TEXT NOT NULL,
    media_type TEXT NOT NULL,
    malware_scanned BOOLEAN NOT NULL,
    malware_scan_at TIMESTAMPTZ NULL,
    exif_stripped_key TEXT NULL,
    original_metadata_key TEXT NULL,
    policy JSONB NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_documents PRIMARY KEY (id),

    CONSTRAINT fk_documents_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_documents_uploader
        FOREIGN KEY (uploader_id)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_documents_media_type
        CHECK (
            media_type IN (
                'pdf',
                'image',
                'video',
                'office'
            )
        )
);

CREATE INDEX idx_documents_organization_id
    ON documents_meetings.documents (organization_id);


--  MEETINGS

CREATE TABLE documents_meetings.meetings
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    title TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    location TEXT NULL,
    organizer_id UUID NOT NULL,
    participant_ids UUID[] NOT NULL,
    agenda TEXT NULL,
    recording_storage_key TEXT NULL,
    recording_consent_captured BOOLEAN NOT NULL,
    consent_receipt_ids UUID[] NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_meetings PRIMARY KEY (id),

    CONSTRAINT fk_meetings_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_meetings_organizer
        FOREIGN KEY (organizer_id)
        REFERENCES identity_authentication_sessions.users(id)
);

CREATE INDEX idx_meetings_organization_id
    ON documents_meetings.meetings (organization_id);


--  MEETING ACTION ITEMS

CREATE TABLE documents_meetings.meeting_action_items
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    meeting_id UUID NOT NULL,
    proposed_task JSONB NOT NULL,
    ai_confidence NUMERIC(4,3) NULL,
    confirmed_task_id UUID NULL,
    confirmed_at TIMESTAMPTZ NULL,
    confirmed_by UUID NULL,
    rejected_at TIMESTAMPTZ NULL,
    rejected_by UUID NULL,

    CONSTRAINT pk_meeting_action_items PRIMARY KEY (id),

    CONSTRAINT fk_meeting_action_items_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_meeting_action_items_meeting
        FOREIGN KEY (meeting_id)
        REFERENCES documents_meetings.meetings(id),

    CONSTRAINT fk_meeting_action_items_confirmed_task
        FOREIGN KEY (confirmed_task_id)
        REFERENCES tasks_field_reports.tasks(id),

    CONSTRAINT fk_meeting_action_items_confirmed_by
        FOREIGN KEY (confirmed_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT fk_meeting_action_items_rejected_by
        FOREIGN KEY (rejected_by)
        REFERENCES identity_authentication_sessions.users(id)
);

CREATE INDEX idx_meeting_action_items_organization_id
    ON documents_meetings.meeting_action_items (organization_id);

CREATE INDEX idx_meeting_action_items_meeting_id
    ON documents_meetings.meeting_action_items (meeting_id);


-- ============================================================
