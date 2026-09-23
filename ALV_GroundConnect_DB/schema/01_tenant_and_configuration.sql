CREATE SCHEMA tenant_and_configuration;

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


