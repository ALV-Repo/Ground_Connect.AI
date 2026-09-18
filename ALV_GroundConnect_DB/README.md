# Ground Connect — Database

## Overview

This database is the PostgreSQL data layer for a **secure, multi-tenant digital operating platform** designed for large hierarchical field organizations.

It manages the platform's core organizational, operational, security, communication, and audit data.

### Key Database Domains

* **Tenant & Configuration** — Multi-tenant organizations and configurable hierarchy levels.
* **Identity & Authentication** — Users, devices, sessions, OTP, and authentication controls.
* **Hierarchy & Bitemporal Model** — Organizational nodes, assignments, transfers, and historical validity.
* **Member Management** — Bulk member import and related processing.
* **Delegation** — Controlled delegation of responsibilities.
* **Two-Person Integrity** — Approval structures for sensitive operations.
* **Messaging & Notifications** — Policy-governed communication and notifications.
* **Prohibited Attribute Firewall** — Database structures supporting protection of prohibited attributes.
* **Tasks & Field Reports** — Field operations, reports, evidence/media, and location data.
* **Vendor Support Elevation** — Controlled vendor/support access.
* **Audit Trail** — Audit events and checkpoints for traceability and compliance.

### Database Technology

* PostgreSQL
* `pgcrypto`
* PostGIS

### Phase 1

The current Phase 1 baseline focuses on:

**Tables → Constraints → Foreign Keys → Indexes → Dependency Management**

The database modules are maintained in dependency order under `schema/`, while the complete deployable baseline is maintained under `migrations/`.

```text
database/
├── migrations/
│   ├── V001__mvp_phase1_baseline.sql
│   └── V001__mvp_phase1_baseline_down.sql
│
└── schema/
    ├── 01_tenant_and_configuration.sql
    ├── 02_identity_authentication_sessions.sql
    ├── 03_member_management_bulk_import.sql
    ├── 04_hierarchy_bitemporal_model.sql
    ├── 05_delegation.sql
    ├── 06_two_person_integrity.sql
    ├── 07_messaging.sql
    ├── 08_notifications.sql
    ├── 09_prohibited_attribute_firewall.sql
    ├── 10_tasks_field_reports.sql
    ├── 11_vendor_support_elevation.sql
    └── 12_audit_trail.sql
```
