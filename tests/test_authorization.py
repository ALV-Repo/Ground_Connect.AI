from app.core.authorization import AuthorizationEngine
from app.schemas.authorization import AuthorizationRequest


def make_engine():
    return AuthorizationEngine()


def test_identity_registration():
    engine = make_engine()

    result = engine.register_identity(
        subject_id="user-001",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    assert result["subject_id"] == "user-001"
    assert result["tenant_id"] == "tenant-001"
    assert result["branch_id"] == "branch-001"
    assert result["role"] == "member"
    assert result["active"] is True


def test_unknown_identity_is_denied():
    engine = make_engine()

    request = AuthorizationRequest(
        subject_id="unknown-user",
        tenant_id="tenant-001",
        resource_type="message",
        resource_id="msg-001",
        action="READ",
        branch_id="branch-001",
    )

    decision = engine.authorize(request)

    assert decision.allowed is False
    assert decision.failing_rule == "IDENTITY_EXISTS"


def test_inactive_identity_is_denied():
    engine = make_engine()

    engine.register_identity(
        subject_id="user-002",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    engine.deactivate_identity("user-002")

    request = AuthorizationRequest(
        subject_id="user-002",
        tenant_id="tenant-001",
        resource_type="message",
        resource_id="msg-001",
        action="READ",
        branch_id="branch-001",
    )

    decision = engine.authorize(request)

    assert decision.allowed is False
    assert decision.failing_rule == "IDENTITY_ACTIVE"


def test_cross_tenant_access_is_denied():
    engine = make_engine()

    engine.register_identity(
        subject_id="user-003",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    request = AuthorizationRequest(
        subject_id="user-003",
        tenant_id="tenant-002",
        resource_type="message",
        resource_id="msg-001",
        action="READ",
        branch_id="branch-001",
    )

    decision = engine.authorize(request)

    assert decision.allowed is False
    assert decision.failing_rule == "TENANT_ISOLATION"


def test_cross_branch_access_is_denied():
    engine = make_engine()

    engine.register_identity(
        subject_id="user-004",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    request = AuthorizationRequest(
        subject_id="user-004",
        tenant_id="tenant-001",
        resource_type="message",
        resource_id="msg-001",
        action="READ",
        branch_id="branch-002",
    )

    decision = engine.authorize(request)

    assert decision.allowed is False
    assert decision.failing_rule == "BRANCH_ISOLATION"


def test_role_based_authorization():
    engine = make_engine()

    engine.register_identity(
        subject_id="user-005",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    request = AuthorizationRequest(
        subject_id="user-005",
        tenant_id="tenant-001",
        resource_type="message",
        resource_id="msg-001",
        action="READ",
        branch_id="branch-001",
    )

    decision = engine.authorize(request)

    assert decision.allowed is True


def test_unauthorized_role_action_is_denied():
    engine = make_engine()

    engine.register_identity(
        subject_id="user-006",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    request = AuthorizationRequest(
        subject_id="user-006",
        tenant_id="tenant-001",
        resource_type="message",
        resource_id="msg-001",
        action="DELETE",
        branch_id="branch-001",
    )

    decision = engine.authorize(request)

    assert decision.allowed is False
    assert decision.failing_rule == "ROLE_PERMISSION"


def test_explicit_grant_allows_action():
    engine = make_engine()

    engine.register_identity(
        subject_id="user-007",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    engine.add_grant(
        subject_id="user-007",
        tenant_id="tenant-001",
        resource_type="message",
        resource_id="msg-001",
        action="DELETE",
        branch_id="branch-001",
    )

    request = AuthorizationRequest(
        subject_id="user-007",
        tenant_id="tenant-001",
        resource_type="message",
        resource_id="msg-001",
        action="DELETE",
        branch_id="branch-001",
    )

    decision = engine.authorize(request)

    assert decision.allowed is True


def test_grant_cannot_cross_tenant():
    engine = make_engine()

    engine.register_identity(
        subject_id="user-008",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    try:
        engine.add_grant(
            subject_id="user-008",
            tenant_id="tenant-002",
            resource_type="message",
            resource_id="msg-001",
            action="DELETE",
            branch_id="branch-001",
        )
        assert False, "Cross-tenant grant should be rejected"
    except PermissionError:
        pass


def test_authorization_cache():
    engine = make_engine()

    engine.register_identity(
        subject_id="user-009",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    request = AuthorizationRequest(
        subject_id="user-009",
        tenant_id="tenant-001",
        resource_type="message",
        resource_id="msg-001",
        action="READ",
        branch_id="branch-001",
    )

    first = engine.authorize(request)
    second = engine.authorize(request)

    assert first.allowed is True
    assert second.allowed is True
    assert second.cache_hit is True


def test_grant_change_invalidates_cache():
    engine = make_engine()

    engine.register_identity(
        subject_id="user-010",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    request = AuthorizationRequest(
        subject_id="user-010",
        tenant_id="tenant-001",
        resource_type="message",
        resource_id="msg-001",
        action="DELETE",
        branch_id="branch-001",
    )

    first = engine.authorize(request)
    assert first.allowed is False

    engine.add_grant(
        subject_id="user-010",
        tenant_id="tenant-001",
        resource_type="message",
        resource_id="msg-001",
        action="DELETE",
        branch_id="branch-001",
    )

    second = engine.authorize(request)

    assert second.allowed is True
    assert second.cache_hit is False


def test_deactivated_identity_invalidates_cache():
    engine = make_engine()

    engine.register_identity(
        subject_id="user-011",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    request = AuthorizationRequest(
        subject_id="user-011",
        tenant_id="tenant-001",
        resource_type="message",
        resource_id="msg-001",
        action="READ",
        branch_id="branch-001",
    )

    first = engine.authorize(request)
    assert first.allowed is True

    engine.deactivate_identity("user-011")

    second = engine.authorize(request)

    assert second.allowed is False
    assert second.cache_hit is False
    assert second.failing_rule == "IDENTITY_ACTIVE"

def test_authorization_cache_expires_after_ttl(monkeypatch):
    engine = make_engine()

    engine.register_identity(
        subject_id="user-012",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    request = AuthorizationRequest(
        subject_id="user-012",
        tenant_id="tenant-001",
        resource_type="message",
        resource_id="msg-001",
        action="READ",
        branch_id="branch-001",
    )

    current_time = [1000.0]
    monkeypatch.setattr(
        "app.core.authorization.time.time",
        lambda: current_time[0],
    )

    first = engine.authorize(request)
    assert first.allowed is True
    assert first.cache_hit is False

    current_time[0] = 1059.0

    second = engine.authorize(request)
    assert second.allowed is True
    assert second.cache_hit is True

    current_time[0] = 1061.0

    third = engine.authorize(request)
    assert third.allowed is True
    assert third.cache_hit is False

def test_field_policy_allows_authorized_field():
    from app.services.authorization import AuthorizationService

    service = AuthorizationService()

    service.register_identity(
        identity_id="field-user-001",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    service.create_field_policy(
        role="member",
        resource_type="task",
        field="status",
        actions=["READ"],
    )

    result = service.check_fields(
        subject_id="field-user-001",
        tenant_id="tenant-001",
        branch_id="branch-001",
        resource_type="task",
        resource_id="task-001",
        action="READ",
        fields=["status"],
    )

    assert result["allowed"] is True
    assert result["allowed_fields"] == ["status"]
    assert result["denied_fields"] == []


def test_field_policy_denies_unauthorized_field():
    from app.services.authorization import AuthorizationService

    service = AuthorizationService()

    service.register_identity(
        identity_id="field-user-002",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    service.create_field_policy(
        role="member",
        resource_type="task",
        field="status",
        actions=["READ"],
    )

    result = service.check_fields(
        subject_id="field-user-002",
        tenant_id="tenant-001",
        branch_id="branch-001",
        resource_type="task",
        resource_id="task-001",
        action="READ",
        fields=["status", "internal_notes"],
    )

    assert result["allowed"] is False
    assert result["allowed_fields"] == ["status"]
    assert result["denied_fields"] == ["internal_notes"]


def test_field_access_denies_cross_tenant():
    from app.services.authorization import AuthorizationService

    service = AuthorizationService()

    service.register_identity(
        identity_id="field-user-003",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    service.create_field_policy(
        role="member",
        resource_type="task",
        field="status",
        actions=["READ"],
    )

    try:
        service.check_fields(
            subject_id="field-user-003",
            tenant_id="tenant-002",
            branch_id="branch-001",
            resource_type="task",
            resource_id="task-001",
            action="READ",
            fields=["status"],
        )
        assert False, "Cross-tenant field access should be denied"
    except PermissionError:
        pass


def test_field_cache_hit():
    from app.services.authorization import AuthorizationService

    service = AuthorizationService()

    service.register_identity(
        identity_id="field-user-004",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    service.create_field_policy(
        role="member",
        resource_type="task",
        field="status",
        actions=["READ"],
    )

    first = service.check_fields(
        subject_id="field-user-004",
        tenant_id="tenant-001",
        branch_id="branch-001",
        resource_type="task",
        resource_id="task-001",
        action="READ",
        fields=["status"],
    )

    second = service.check_fields(
        subject_id="field-user-004",
        tenant_id="tenant-001",
        branch_id="branch-001",
        resource_type="task",
        resource_id="task-001",
        action="READ",
        fields=["status"],
    )

    assert first["allowed"] is True
    assert second["allowed"] is True
    assert second["cache_hit"] is True


def test_field_policy_change_invalidates_cache():
    from app.services.authorization import AuthorizationService

    service = AuthorizationService()

    service.register_identity(
        identity_id="field-user-005",
        tenant_id="tenant-001",
        branch_id="branch-001",
        role="member",
    )

    service.create_field_policy(
        role="member",
        resource_type="task",
        field="status",
        actions=["READ"],
    )

    first = service.check_fields(
        subject_id="field-user-005",
        tenant_id="tenant-001",
        branch_id="branch-001",
        resource_type="task",
        resource_id="task-001",
        action="READ",
        fields=["status"],
    )

    assert first["allowed"] is True

    service.create_field_policy(
        role="member",
        resource_type="task",
        field="status",
        actions=["UPDATE"],
    )

    second = service.check_fields(
        subject_id="field-user-005",
        tenant_id="tenant-001",
        branch_id="branch-001",
        resource_type="task",
        resource_id="task-001",
        action="READ",
        fields=["status"],
    )

    assert second["allowed"] is False
    assert second["denied_fields"] == ["status"]
