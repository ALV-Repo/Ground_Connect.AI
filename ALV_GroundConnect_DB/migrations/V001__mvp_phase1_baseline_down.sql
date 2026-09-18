-- V001__mvp_phase1_baseline_down.sql
-- Reversible rollback for V001__mvp_phase1_baseline.sql
-- Schemas are dropped in reverse dependency order.
-- Extensions are intentionally NOT dropped because they may be shared by other applications.

BEGIN;

DROP SCHEMA IF EXISTS audit_trail CASCADE;
DROP SCHEMA IF EXISTS vendor_support_elevation CASCADE;
DROP SCHEMA IF EXISTS tasks_field_reports CASCADE;
DROP SCHEMA IF EXISTS prohibited_attribute_firewall CASCADE;
DROP SCHEMA IF EXISTS notifications CASCADE;
DROP SCHEMA IF EXISTS messaging CASCADE;
DROP SCHEMA IF EXISTS two_person_integrity CASCADE;
DROP SCHEMA IF EXISTS delegation CASCADE;
DROP SCHEMA IF EXISTS hierarchy_bitemporal_model CASCADE;
DROP SCHEMA IF EXISTS member_management_bulk_import CASCADE;
DROP SCHEMA IF EXISTS identity_authentication_sessions CASCADE;
DROP SCHEMA IF EXISTS tenant_and_configuration CASCADE;

COMMIT;
