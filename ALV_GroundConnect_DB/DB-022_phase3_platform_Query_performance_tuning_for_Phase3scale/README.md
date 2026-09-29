# DB-022 — Query Performance Tuning for Phase-3 Scale

## Scope

Implements the database-side performance foundation for:

- NFR-06: 200,000 members, 200,000 hierarchy nodes, 5,000 concurrent users, 15,000 mobilisation burst, 500,000 messages/day, 10,000 issues/day, 50,000 media uploads/day, 5,000,000 audit events/day.
- HIER-06: at least 200,000 hierarchy nodes per tenant without degrading performance targets.
- Large-table partitioning design for `audit_trail.audit_events`, `messaging.messages`, and `citizen_issues.canonical_issues`.
- Hierarchy index coverage for tenant-scoped subtree, current-assignment, and validity-window queries.
- Read-replica routing for dashboards and search.
- Load-test evidence storage.

## Files

- `23_phase3_performance_tuning.sql`
- `23_phase3_performance_tuning_tests.sql`
- `README.md`

## Important partitioning decision

The existing authoritative tables use UUID-only primary keys and have existing foreign keys that reference those UUIDs. PostgreSQL native partitioned-table unique/primary-key constraints must include the partition key.

Therefore this migration **does not rename, drop, or replace the authoritative tables automatically**.

It creates partitioned staging parents under `phase3_performance` using:

`RANGE(created_at) -> HASH(organization_id)`

This is the physical target for the controlled V003/maintenance-window migration.

Before production cutover, dependent foreign keys must be redesigned to carry the required partition key columns, or an approved alternative key strategy must be adopted. The migration must be rehearsed on a production-sized copy and validated with application traffic.

## Hierarchy indexes

The script adds indexes that complement, rather than replace, the existing hierarchy indexes:

- `(organization_id, parent_id, id)`
- `(organization_id, status, parent_id, id)`
- current assignments `(organization_id, node_id, user_id) WHERE valid_to IS NULL`
- validity lookups `(organization_id, node_id, valid_from, valid_to)`
- current user assignments `(organization_id, user_id, node_id) WHERE valid_to IS NULL`

The existing `idx_nodes_organization_parent` and `idx_node_assignments_current` are retained; duplicates are not recreated.

## Read-replica routing

`phase3_performance.read_workloads` defines:

- `dashboard` → replica allowed
- `search` → replica allowed
- `transactional` → primary
- `audit_export` → primary
- `migration` → primary

The database function only returns the routing decision. The application connection pool/router must select the actual primary or replica connection. No database credentials are stored in this schema.

## Load testing

`load_test_runs` and `load_test_metrics` store measured evidence.

A passing Phase-3 test should demonstrate at least:

- 200,000 hierarchy nodes per tenant
- 200,000 members
- 5,000 concurrent users
- 15,000 peak concurrent users for mobilisation
- 500,000 messages/day
- 10,000 issues/day
- 50,000 media uploads/day
- 5,000,000 audit events/day
- 10x burst behaviour within minutes

The SQL file does **not** claim that these targets have been achieved. Actual load generation, EXPLAIN/EXPLAIN ANALYZE capture, p95/p99 measurement, replica-lag measurement, and application concurrency testing must be executed by the performance/load-test environment.

## Execution order

1. Run the main SQL file.
2. Run the test SQL file.
3. Generate partition staging months, for example:

```sql
SELECT phase3_performance.create_month_partitions('2026-01-01', 24, 8);
```

4. Benchmark hierarchy queries using realistic 200k-node tenant data.
5. Run the Phase-3 workload test externally.
6. Store measured metrics in `phase3_performance.load_test_runs` and `load_test_metrics`.
7. Perform the authoritative partition cutover only through a separately reviewed migration after FK/PK redesign.

## Expected review outcome

This implementation provides the DB-022 performance control plane and safe physical-design staging without silently breaking the existing relational model.

## Review-gap closure — DB-022

The following review gaps are explicitly represented as executable validation targets and are **not claimed as passed until real evidence is captured**:

| Gap | DB-022 implementation | Proof source |
|---|---|---|
| 200k hierarchy proof | Validation target + Phase-3 hierarchy indexes | `validation_results` + load test |
| 5k concurrency proof | Validation target | external application load test |
| 15k burst proof | Validation target with >=10x burst requirement | external burst load test |
| Replica lag telemetry | `replica_lag_telemetry` + `capture_replica_lag_telemetry()` | `pg_stat_replication` |
| EXPLAIN ANALYZE evidence | `explain_evidence` registry | `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` |
| Partition-local indexes | `create_partition_local_indexes()` | leaf partition catalog + index catalog |
| Real performance validation | `validation_results` + executable runner | measured Phase-3 environment |

### Real validation procedure

1. Provision a Phase-3-like PostgreSQL primary and read replica.
2. Populate at least 200,000 hierarchy nodes for a tenant and 200,000 members.
3. Create the required monthly/hash partitions and run:

```sql
SELECT phase3_performance.create_partition_local_indexes();
```

4. Capture replica telemetry:

```sql
SELECT phase3_performance.capture_replica_lag_telemetry();
```

5. Run real hierarchy, dashboard and search queries with:

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ...;
```

6. Store the resulting plan/timing in `phase3_performance.explain_evidence`.
7. Run the application load test at 5,000 concurrent users.
8. Run the mobilisation burst at 15,000 concurrent users.
9. Record measured results in `phase3_performance.load_test_metrics` and mark the corresponding `validation_results` rows `passed` only when the target is actually demonstrated.

### Important distinction

DB-022 now contains the **mechanisms and evidence registry** required to prove the targets. The repository cannot truthfully claim 200k-node, 5k-concurrency, 15k-burst, replica-lag, or real query-performance success merely from executing DDL. Those results must come from an actual Phase-3-sized environment.


