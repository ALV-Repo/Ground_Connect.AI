CREATE SCHEMA member_management_bulk_import;


-- CREATING TABLE IMPORT_BATCHES
CREATE TABLE member_management_bulk_import.import_batches
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),

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

    -- Primary Key
    CONSTRAINT pk_import_batches
        PRIMARY KEY (id),

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