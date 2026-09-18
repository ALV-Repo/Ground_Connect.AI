CREATE SCHEMA notifications;

-- creating table notification_preferences

CREATE TABLE notifications.notification_preferences (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    user_id UUID NOT NULL,
    channels JSONB NOT NULL,
    quiet_hours_from TIME NULL,
    quiet_hours_to TIME NULL,
    emergency_override BOOLEAN NOT NULL DEFAULT TRUE,
    security_override BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_notification_preferences
        PRIMARY KEY (id),

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
    id UUID NOT NULL DEFAULT gen_random_uuid(),
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

    CONSTRAINT pk_notification_log
        PRIMARY KEY (id),

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


