import json

from app.core.audit import AuditService


def make_service(tmp_path):
    return AuditService(
        audit_file=tmp_path / "authorization_decisions.jsonl"
    )


def test_record_allow_and_deny(tmp_path):
    service = make_service(tmp_path)

    allow = service.record_decision(
        subject_id="user-1",
        action="READ",
        resource_type="task",
        resource_id="task-1",
        allowed=True,
        reason="Role permits READ",
        rules_evaluated=["role_permission"],
        tenant_id="tenant-1",
        branch_id="branch-1",
    )

    deny = service.record_decision(
        subject_id="user-2",
        action="DELETE",
        resource_type="task",
        resource_id="task-1",
        allowed=False,
        reason="Action not permitted",
        rules_evaluated=["role_permission"],
        failing_rule="role_permission",
        tenant_id="tenant-1",
        branch_id="branch-1",
    )

    assert allow["decision"] == "ALLOW"
    assert deny["decision"] == "DENY"
    assert allow["record_id"]
    assert deny["record_id"]
    assert allow["tenant_id"] == "tenant-1"


def test_required_adr_fields_are_present(tmp_path):
    service = make_service(tmp_path)

    record = service.record_decision(
        subject_id="user-1",
        action="READ",
        resource_type="message",
        resource_id="msg-1",
        allowed=True,
        reason="Allowed",
    )

    required = {
        "record_id",
        "timestamp",
        "subject_id",
        "action",
        "resource_type",
        "resource_id",
        "decision",
        "reason",
        "rules_evaluated",
        "failing_rule",
    }

    assert required.issubset(record.keys())


def test_query_filters_records(tmp_path):
    service = make_service(tmp_path)

    service.record_decision(
        subject_id="user-1",
        action="READ",
        resource_type="task",
        resource_id="task-1",
        allowed=True,
        reason="Allowed",
        tenant_id="tenant-1",
    )

    service.record_decision(
        subject_id="user-2",
        action="WRITE",
        resource_type="message",
        resource_id="msg-1",
        allowed=False,
        reason="Denied",
        tenant_id="tenant-2",
    )

    records = service.list_records(
        tenant_id="tenant-1",
        action="READ",
    )

    assert len(records) == 1
    assert records[0]["subject_id"] == "user-1"
    assert records[0]["resource_id"] == "task-1"


def test_sensitive_values_are_redacted(tmp_path):
    service = make_service(tmp_path)

    record = service.record_decision(
        subject_id="user-1",
        action="READ",
        resource_type="message",
        resource_id="message_content=secret-message",
        allowed=True,
        reason="email=user@example.com token=secret-token",
    )

    assert "secret-message" not in json.dumps(record)
    assert "user@example.com" not in json.dumps(record)
    assert "secret-token" not in json.dumps(record)


def test_records_persist_to_disk(tmp_path):
    audit_file = tmp_path / "authorization_decisions.jsonl"

    service = AuditService(audit_file=audit_file)

    service.record_decision(
        subject_id="user-1",
        action="READ",
        resource_type="task",
        resource_id="task-1",
        allowed=True,
        reason="Allowed",
    )

    assert audit_file.exists()

    lines = audit_file.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1

    stored = json.loads(lines[0])

    assert stored["subject_id"] == "user-1"
    assert stored["decision"] == "ALLOW"


def test_reload_persisted_records(tmp_path):
    audit_file = tmp_path / "authorization_decisions.jsonl"

    service1 = AuditService(audit_file=audit_file)

    created = service1.record_decision(
        subject_id="user-1",
        action="READ",
        resource_type="task",
        resource_id="task-1",
        allowed=True,
        reason="Allowed",
    )

    service2 = AuditService(audit_file=audit_file)

    loaded = service2.get_record(created["record_id"])

    assert loaded is not None
    assert loaded["subject_id"] == "user-1"


def test_who_can_access(tmp_path):
    service = make_service(tmp_path)

    service.record_decision(
        subject_id="user-1",
        action="READ",
        resource_type="task",
        resource_id="task-1",
        allowed=True,
        reason="Allowed",
        tenant_id="tenant-1",
    )

    service.record_decision(
        subject_id="user-2",
        action="READ",
        resource_type="task",
        resource_id="task-1",
        allowed=True,
        reason="Allowed",
        tenant_id="tenant-1",
    )

    subjects = service.who_can_access(
        resource_type="task",
        resource_id="task-1",
        action="READ",
        tenant_id="tenant-1",
    )

    assert set(subjects) == {"user-1", "user-2"}


def test_what_can_access(tmp_path):
    service = make_service(tmp_path)

    service.record_decision(
        subject_id="user-1",
        action="READ",
        resource_type="task",
        resource_id="task-1",
        allowed=True,
        reason="Allowed",
    )

    service.record_decision(
        subject_id="user-1",
        action="WRITE",
        resource_type="message",
        resource_id="msg-1",
        allowed=True,
        reason="Allowed",
    )

    records = service.what_can_access(
        subject_id="user-1",
        decision="ALLOW",
    )

    assert len(records) == 2
    assert all(record["decision"] == "ALLOW" for record in records)


def test_list_denials(tmp_path):
    service = make_service(tmp_path)

    service.record_decision(
        subject_id="user-1",
        action="DELETE",
        resource_type="task",
        resource_id="task-1",
        allowed=False,
        reason="Not permitted",
        tenant_id="tenant-1",
    )

    denials = service.list_denials(
        subject_id="user-1",
        tenant_id="tenant-1",
    )

    assert len(denials) == 1
    assert denials[0]["decision"] == "DENY"
    assert denials[0]["action"] == "DELETE"
