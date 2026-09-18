CREATE SCHEMA tasks_field_reports;
CREATE EXTENSION IF NOT EXISTS postgis;


-- CREATING TABLE tasks

CREATE TABLE tasks_field_reports.tasks (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
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

    CONSTRAINT pk_tasks
        PRIMARY KEY (id),

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
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    task_id UUID NOT NULL,
    from_status TEXT NULL,
    to_status TEXT NOT NULL,
    actor_id UUID NOT NULL,
    actor_assignment_id UUID NOT NULL,
    reason TEXT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_task_history
        PRIMARY KEY (id),

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
    id UUID NOT NULL DEFAULT gen_random_uuid(),
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

    CONSTRAINT pk_field_reports
        PRIMARY KEY (id),

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
    id UUID NOT NULL DEFAULT gen_random_uuid(),
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

    CONSTRAINT pk_evidence_media
        PRIMARY KEY (id),

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
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    working_days INTEGER[] NOT NULL,
    working_from TIME NOT NULL,
    working_to TIME NOT NULL,
    holidays DATE[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_working_hours_calendars
        PRIMARY KEY (id),

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
