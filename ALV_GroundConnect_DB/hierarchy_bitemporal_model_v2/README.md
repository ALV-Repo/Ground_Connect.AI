# Hierarchy Bitemporal Model V2

## Purpose

Updated database implementation for hierarchy nodes and
bitemporal parent-child assignments.

## Requirements

- Nodes table
- Node assignments table
- `valid_from`
- `valid_to`
- `recorded_at`
- `recorded_by`
- Single parent per validity interval
- Multi-parent structures rejected
- Cycle prevention enforced at the database level

## Database Objects

### Schema

- `hierarchy_bitemporal_model`

### Tables

- `hierarchy_bitemporal_model.nodes`
- `hierarchy_bitemporal_model.node_assignments`

### Temporal Attributes

The `node_assignments` table maintains the validity period of
each parent-child relationship:

- `valid_from` — start of business validity
- `valid_to` — end of business validity; `NULL` represents an open-ended interval
- `recorded_at` — timestamp when the assignment was recorded
- `recorded_by` — user who recorded the assignment

## Hierarchy Integrity

### Single Parent Per Validity Interval

A node can have only one parent during any overlapping
validity interval.

Overlapping assignments such as:

    Node B → Parent A [2026-01-01, 2026-06-01)
    Node B → Parent C [2026-03-01, 2026-09-01)

are rejected at the database level.

Non-overlapping historical assignments are allowed:

    Node B → Parent A [2026-01-01, 2026-04-01)
    Node B → Parent C [2026-04-01, 2026-09-01)

### Multi-Parent Prevention

Multi-parent structures are rejected by enforcing a
single-parent-per-validity-interval constraint using a
PostgreSQL `EXCLUDE USING GIST` constraint.

The constraint prevents the same node within the same
organization from having overlapping parent assignments.

### Cycle Prevention

Cycle prevention is enforced at the **database level**.

A PostgreSQL trigger uses recursive hierarchy traversal to
detect circular parent-child relationships.

For example, the following structure is rejected:

    A → B
    B → C
    C → A

The database raises an exception when a hierarchy cycle is
detected.

Cycle prevention is therefore not dependent on application-side
validation.

### Self-Parent Prevention

A node cannot be assigned as its own parent.

Example:

    A → A

is rejected using a database `CHECK` constraint.

## Database-Level Enforcement

The following hierarchy rules are enforced directly by
PostgreSQL:

| Rule | Enforcement |
|------|-------------|
| Valid validity interval | `CHECK` constraint |
| Node cannot be its own parent | `CHECK` constraint |
| Child must exist | Foreign key |
| Parent must exist | Foreign key |
| Parent must belong to same organization | Composite foreign key |
| Single parent per validity interval | `EXCLUDE USING GIST` |
| Multi-parent structures | `EXCLUDE USING GIST` |
| Cycle prevention | Database trigger |

## Database Trigger

The cycle-prevention function is:

    hierarchy_bitemporal_model.prevent_hierarchy_cycle()

The trigger is:

    trg_prevent_hierarchy_cycle

The trigger executes database-level validation for hierarchy
assignments and rejects circular relationships.

## Historical Hierarchy Changes

Historical parent changes are supported when validity intervals
do not overlap.

Example:

    B → A [2026-01-01, 2026-04-01)
    B → C [2026-04-01, 2026-07-01)

This is valid because the two assignments do not overlap.

## Validation

The implementation is designed to reject:

1. Invalid validity intervals
2. Self-parent relationships
3. Overlapping parent assignments
4. Multi-parent structures
5. Circular hierarchy relationships
6. Cross-organization parent-child relationships

All hierarchy integrity rules are enforced at the database
level.