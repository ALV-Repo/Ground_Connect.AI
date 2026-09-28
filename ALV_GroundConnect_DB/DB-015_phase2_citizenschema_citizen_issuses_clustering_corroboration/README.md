# DB-015 — Citizen Issues, Clustering & Corroboration

Incremental PostgreSQL implementation for CIT-07 through CIT-10.

## Reused existing objects

This package does not recreate:

- citizen_issues.canonical_issues
- citizen_issues.citizen_submissions
- citizen_issues.issue_history
- citizen_issues.closure_confirmations
- identity_authentication_sessions.users
- tenant_and_configuration.tenants

## Added

- citizen_issues.corroborations
- citizen_issues.clustering_operations
- clustering metadata on canonical_issues
- corroboration count maintenance
- tenant-scoped summary view

## CIT-07

Stores category/geo/semantic clustering metadata. The actual semantic clustering
algorithm remains an application/service responsibility.

## CIT-08

One active corroboration per citizen per canonical issue is enforced with
partial unique indexes. Repeated reports from the same citizen therefore do
not increase the distinct-citizen severity signal.

## CIT-09

System suggestions, human confirmation, merge, split and reversal are preserved
as append-only clustering operation records. Existing issue_history remains
the canonical issue state-machine history.

## CIT-10

Each corroborating citizen has individual notification and closure-confirmation
state.

## Execution

Prerequisite: the existing Phase-1 and Phase-2 schemas must exist.

Run:
1. db015_citizen_clustering.sql
2. db015_citizen_clustering_tests.sql

Tests execute in a transaction and roll back test data.

## Important

The SQL stores clustering metadata and decisions; it does not implement the
semantic clustering/AI algorithm itself.

## Integrity rules

DB-015 uses composite `(organization_id, id)` references for new
corroboration relationships so a tenant-A row cannot reference a tenant-B
canonical issue, user, or submission.

Each corroboration must identify the citizen by exactly one mechanism:
`citizen_user_id` for a registered user OR `citizen_handle` for a handle-based
citizen.
