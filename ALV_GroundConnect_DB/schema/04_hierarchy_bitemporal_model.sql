CREATE SCHEMA hierarchy_bitemporal_model;
                    /*####################################################
                                     CREATING TABLE NODES
                     ######################################################*/

					 
CREATE TABLE hierarchy_bitemporal_model.nodes (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
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

    CONSTRAINT pk_nodes
        PRIMARY KEY (id),

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

                    /*####################################################
                                    CREATING TABLE NODE_ASSIGNMENTS
                     ######################################################*/



CREATE TABLE hierarchy_bitemporal_model.node_assignments (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
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

    CONSTRAINT pk_node_assignments
        PRIMARY KEY (id),

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




                    /*####################################################
                                    CREATING TABLE TRANSFERS
                     ######################################################*/
					 



CREATE TABLE hierarchy_bitemporal_model.transfers (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
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

    CONSTRAINT pk_transfers
        PRIMARY KEY (id),

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



/*NOTE : transfers
delegations NOT YET CREATED SO RUN THIS AFTER CREATION OF TRANSFERS AND DELEGATIONS TABLE */


ALTER TABLE hierarchy_bitemporal_model.node_assignments
ADD CONSTRAINT fk_node_assignments_transfer
    FOREIGN KEY (transfer_id)
    REFERENCES hierarchy_bitemporal_model.transfers(id);


	

	
	