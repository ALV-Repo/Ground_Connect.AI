-- ============================================================
-- PHASE 2: RECURRING TASK TEMPLATES
-- ============================================================

CREATE SCHEMA IF NOT EXISTS recurring_tasks;

-- recurring_task_templates

CREATE TABLE recurring_tasks.recurring_task_templates
(
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    title_template TEXT NOT NULL,
    description TEXT NULL,
    assignee_role TEXT NOT NULL,
    priority TEXT NOT NULL,
    schedule_type TEXT NOT NULL,
    cron_expression TEXT NULL,
    deadline_offset_hours INTEGER NULL,
    escalation_rule JSONB NULL,
    active BOOLEAN NOT NULL,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_recurring_task_templates PRIMARY KEY (id),

    CONSTRAINT fk_recurring_task_templates_organization
        FOREIGN KEY (organization_id)
        REFERENCES tenant_and_configuration.tenants(id),

    CONSTRAINT fk_recurring_task_templates_created_by
        FOREIGN KEY (created_by)
        REFERENCES identity_authentication_sessions.users(id),

    CONSTRAINT chk_recurring_task_templates_schedule_type
        CHECK (
            schedule_type IN (
                'daily',
                'weekly',
                'monthly',
                'custom_cron'
            )
        )
);

CREATE INDEX idx_recurring_task_templates_organization_id
    ON recurring_tasks.recurring_task_templates (organization_id);
