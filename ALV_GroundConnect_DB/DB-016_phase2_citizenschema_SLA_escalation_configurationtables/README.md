# DB-016 — SLA & Compliance Configuration

## 1. Purpose

This module implements **DB-016: SLA & escalation configuration tables** for the Ground Connect database.

It covers:

- **CIT-13** — Tenant-configurable SLA response and resolution targets by issue category and priority, with escalation-chain configuration and SLA-breach processing.
- **CMP-01** — Named and versioned compliance profiles containing tenant-wide compliance controls.
- **CMP-02** — Auditable, immutable activation/deactivation history of the compliance profile that was in force.

This implementation is **incremental**. It reuses the existing Phase-2 tables created by the earlier schema files and does not recreate the existing SLA or compliance-profile master tables.

---

## 2. Files

### Migration

`db016_sla_compliance.sql`

Contains the DB-016 database changes:

- Existing SLA matrix enhancements
- SLA escalation chains
- SLA escalation chain steps
- SLA escalation events / breach outbox
- Compliance profile enhancements
- Compliance profile activation/deactivation history
- Atomic compliance profile activation/deactivation functions
- SLA breach processing function
- Tenant RLS / FORCE RLS
- Supporting constraints and indexes

### Tests

`db016_sla_compliance_tests.sql`

Contains non-destructive DB-016 verification checks for:

- Required objects
- SLA configuration columns
- Compliance profile controls
- Active-profile uniqueness
- Append-only activation history
- Activation snapshot protection
- SLA breach processor
- RLS / FORCE RLS
- Audit dependency

---

## 3. Requirements Covered

| Requirement | Coverage |
|---|---|
| DB-016 | SLA matrix, escalation configuration and compliance profile configuration |
| CIT-13 | Response/resolution targets and tenant-configured escalation chains |
| CMP-01 | Named/versioned profiles and tenant-wide compliance controls |
| CMP-02 | Immutable activation/deactivation history and audited profile contents |

---

# 4. SLA Configuration

The existing table:

`citizen_issues.sla_config`

is reused.

The table continues to define an SLA for:

- Organization
- Issue category
- Priority
- Response target
- Resolution target

DB-016 additionally associates an SLA configuration with an escalation chain.

### Important columns

```text
organization_id
category
priority
response_target_minutes
resolution_target_minutes
escalation_chain_id
```

### Constraints

DB-016 enforces:

- Response target must be greater than zero.
- Resolution target must be greater than zero.
- Response target must not exceed the resolution target.
- One SLA configuration exists per:

```text
organization_id + category + priority
```

---

# 5. Escalation Chains

Escalation configuration is normalized into:

`citizen_issues.sla_escalation_chains`

A chain represents a named, versioned escalation policy for a tenant.

Important fields include:

```text
organization_id
name
version
enabled
```

The combination:

```text
organization_id + name + version
```

is unique.

This allows a tenant to maintain different versions of an escalation policy without overwriting the previous version.

---

# 6. Escalation Chain Steps

Individual escalation levels are stored in:

`citizen_issues.sla_escalation_chain_steps`

Each step contains:

```text
escalation_chain_id
step_no
trigger_after_minutes
target_type
target_ref
target_value
notification_channel
enabled
```

Supported target types:

```text
user
node
role
channel
```

Supported notification channels:

```text
in_app
sms
voice
email
webhook
```

Steps are ordered using `step_no`.

The same escalation chain cannot contain duplicate step numbers.

---

# 7. SLA Breach Processing

PostgreSQL triggers cannot execute merely because wall-clock time reaches an SLA deadline.

Therefore DB-016 provides:

```text
citizen_issues.process_sla_breaches(...)
```

The function is intended to be called by the application's scheduler/worker.

It:

1. Finds issues whose response or resolution SLA has expired.
2. Determines the applicable SLA configuration.
3. Determines the configured escalation chain.
4. Identifies the next escalation step.
5. Records the escalation event in the SLA escalation event/outbox table.
6. Prevents duplicate processing of the same escalation step.
7. Updates the issue's SLA-breach information.

The notification/message worker can then consume the durable escalation event and perform the actual notification.

## Operational recommendation

The scheduler should call the breach processor at a frequency appropriate to the required SLA precision.

For a requirement that escalation must occur within approximately one minute of a breach, run the processor at least once per minute.

---

# 8. Idempotent Escalation Events

SLA escalation events are persisted instead of relying only on an in-memory notification call.

This provides a durable hand-off between:

```text
SLA breach detection
        |
        v
SLA escalation event/outbox
        |
        v
Notification / messaging worker
```

The event identity and uniqueness constraints prevent the same issue and escalation step from being repeatedly created during retries.

This supports reliable processing when the worker is restarted or a database transaction is retried.

---

# 9. Compliance Profiles

The existing table:

`compliance_mode.compliance_profiles`

is reused and extended.

Each profile is identified by:

```text
organization_id
name
version
```

The combination:

```text
organization_id + name + version
```

is unique.

A new version should be created instead of changing the contents of a profile version that has already been activated.

---

# 10. Compliance Controls

Each compliance profile contains the following controls:

### Feature availability

```text
feature_availability JSONB
```

Defines features that are enabled, disabled, or restricted under the profile.

### Retention policy

```text
retention_policy JSONB
```

Defines retention-related rules applicable while the profile is active.

### Mandatory disclaimers

```text
mandatory_disclaimers JSONB
```

Stores disclaimers that must be applied under the profile.

### Approval requirements

```text
approval_requirements JSONB
```

Defines actions that require additional approval.

### Export restrictions

```text
export_restrictions JSONB
```

Defines restrictions applicable to data export.

### Audit granularity

```text
audit_granularity TEXT
```

Supported values:

```text
standard
detailed
maximum
```

---

# 11. Compliance Profile Activation

Activation is performed through:

```text
compliance_mode.activate_profile(...)
```

The operation is transactional.

The activation process:

1. Verifies that the profile belongs to the tenant.
2. Prevents a second active profile for the same tenant.
3. Creates a complete snapshot of the profile contents.
4. Creates the activation record.
5. Records the activation in immutable activation history.
6. Updates the tenant's active compliance profile reference.
7. Creates the corresponding audit event.

The profile contents in force at activation are therefore preserved independently of later profile changes.

---

# 12. Compliance Profile Deactivation

Deactivation is performed through:

```text
compliance_mode.deactivate_profile(...)
```

The operation:

1. Locks the activation record.
2. Verifies that the activation is currently active.
3. Records the deactivation timestamp and actor.
4. Copies the original profile snapshot into the immutable history.
5. Creates the corresponding audit event.

---

# 13. CMP-02 Historical Defensibility

The table:

`compliance_mode.profile_activation_history`

is append-only.

It stores:

```text
organization_id
profile_id
profile_name
profile_version
action
profile_contents
activated_at
deactivated_at
action_at
action_by
source_activation_id
```

The `profile_contents` column contains the complete profile snapshot in force for that activation.

This allows historical queries to determine which named/versioned compliance profile was active and what its configuration contained.

The database prevents normal `UPDATE` and `DELETE` operations against this history through an append-only trigger.

---

# 14. One Active Profile Per Tenant

DB-016 creates a partial unique index so that a tenant can have at most one active compliance profile:

```text
organization_id
WHERE deactivated_at IS NULL
```

This prevents overlapping active compliance profiles.

---

# 15. Audit Integration

Compliance activation and deactivation use the existing:

```text
audit_trail.append_audit_event(...)
```

function.

The audit payload contains the relevant compliance-profile information so the activation/deactivation is recorded together with the existing append-only, hash-chained audit infrastructure.

DB-016 therefore does not create a second audit mechanism.

---

# 16. Tenant Isolation

DB-016 tenant-owned tables use:

```text
ENABLE ROW LEVEL SECURITY
FORCE ROW LEVEL SECURITY
```

Tenant isolation uses the existing authenticated session context:

```text
app.organization_id
```

The implementation uses:

```text
app.current_organization_id()
```

for RLS policies.

The tenant ID must come from the authenticated database session context rather than a request parameter.

---

# 17. Important Cross-Tenant Protection

DB-016 uses tenant-scoped relationships where required.

For example, SLA configuration and escalation chains are linked using both:

```text
organization_id
id
```

rather than relying only on the object UUID.

This prevents an object belonging to one tenant from being referenced by an SLA configuration belonging to another tenant.

The same tenant-scoped relationship principle is applied to compliance profiles and activation history.

---

# 18. Execution Order

DB-016 depends on earlier schema objects.

Run the existing schema/migration sequence first, including:

1. Tenant/configuration
2. Identity/authentication
3. Citizen issue schema
4. Compliance mode
5. Audit infrastructure

Then run:

```text
db016_sla_compliance.sql
```

After the migration completes, run:

```text
db016_sla_compliance_tests.sql
```

The test script is intended as a verification script and uses `ROLLBACK` so that its verification transaction does not persist changes.

---

# 19. Application/Scheduler Dependency

The database cannot autonomously execute a function when a timestamp expires.

Therefore:

```text
process_sla_breaches(...)
```

must be invoked by a scheduler, worker, or job system.

Recommended architecture:

```text
             PostgreSQL
                 |
       SLA deadline reached
                 |
                 v
      process_sla_breaches()
                 |
                 v
       SLA escalation event
                 |
                 v
       Notification worker
                 |
                 v
      SMS / Email / Voice /
      In-app / Webhook
```

The database remains responsible for authoritative SLA state and durable escalation-event creation.

---

# 20. Verification Queries

Useful checks after deployment:

### SLA configuration

```sql
SELECT *
FROM citizen_issues.sla_config
ORDER BY organization_id, category, priority;
```

### Escalation chains

```sql
SELECT *
FROM citizen_issues.sla_escalation_chains
ORDER BY organization_id, name, version;
```

### Escalation steps

```sql
SELECT *
FROM citizen_issues.sla_escalation_chain_steps
ORDER BY organization_id, escalation_chain_id, step_no;
```

### Compliance profiles

```sql
SELECT
    organization_id,
    id,
    name,
    version,
    audit_granularity,
    created_at
FROM compliance_mode.compliance_profiles
ORDER BY organization_id, name, version;
```

### Active compliance profiles

```sql
SELECT
    organization_id,
    profile_id,
    activated_at,
    activated_by
FROM compliance_mode.compliance_profile_activations
WHERE deactivated_at IS NULL;
```

### Compliance history

```sql
SELECT
    organization_id,
    profile_name,
    profile_version,
    action,
    action_at,
    action_by
FROM compliance_mode.profile_activation_history
ORDER BY organization_id, action_at;
```

### RLS status

```sql
SELECT
    schemaname,
    tablename,
    rowsecurity,
    forcerowsecurity
FROM pg_tables
WHERE (schemaname, tablename) IN
(
    ('citizen_issues', 'sla_config'),
    ('citizen_issues', 'sla_escalation_chains'),
    ('citizen_issues', 'sla_escalation_chain_steps'),
    ('citizen_issues', 'sla_escalation_events'),
    ('compliance_mode', 'compliance_profiles'),
    ('compliance_mode', 'compliance_profile_activations'),
    ('compliance_mode', 'profile_activation_history')
)
ORDER BY schemaname, tablename;
```

---

# 21. Review Checklist

### CIT-13

- [x] SLA response target configurable by tenant/category/priority
- [x] SLA resolution target configurable by tenant/category/priority
- [x] Escalation chain configurable per SLA
- [x] Escalation chain has ordered steps
- [x] SLA breach processing function provided
- [x] Escalation events persisted durably
- [x] Duplicate escalation processing prevented
- [x] Tenant isolation enabled

### CMP-01

- [x] Named compliance profiles
- [x] Versioned compliance profiles
- [x] Feature availability configuration
- [x] Retention configuration
- [x] Mandatory disclaimers configuration
- [x] Approval requirements configuration
- [x] Export restrictions configuration
- [x] Audit granularity configuration
- [x] One active profile per tenant
- [x] Atomic activation/deactivation

### CMP-02

- [x] Activation recorded
- [x] Deactivation recorded
- [x] Complete profile snapshot retained
- [x] Actor recorded
- [x] Activation/deactivation timestamps retained
- [x] Append-only history enforced
- [x] Audit event generated
- [x] Historical profile contents remain available

---

# 22. Limitations / Operational Notes

DB-016 provides the database-side SLA breach processor and durable escalation event mechanism.

Actual delivery of an escalation through SMS, email, voice, webhook, or another notification provider remains the responsibility of the existing notification/messaging infrastructure.

Similarly, the JSONB compliance controls are the authoritative configuration stored by the database. Individual application features must read and enforce those controls when performing the corresponding operation.

---

## 23. Commit Message

Recommended Git commit:

```text
feat(db-016): complete SLA escalation and compliance mode controls
```

## 24. Related Requirements

- `DB-016`
- `CIT-13`
- `CMP-01`
- `CMP-02`
