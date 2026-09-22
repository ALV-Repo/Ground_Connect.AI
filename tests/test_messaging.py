import pytest

from app.services.messaging import MessagingService


@pytest.fixture
def messaging_service():
    return MessagingService()


@pytest.fixture
def sample_members():
    return [
        {
            "member_id": "member-001",
            "tenant_id": "tenant-001",
            "branch_id": "branch-001",
        },
        {
            "member_id": "member-002",
            "tenant_id": "tenant-001",
            "branch_id": "branch-001",
        },
    ]


def create_sample_message(service, members):
    return service.create_message(
        message_id="message-001",
        tenant_id="tenant-001",
        subject="Test Ground Message",
        body="This is a test message.",
        created_by="test-admin",
        recipients=members,
        priority="normal",
        metadata={},
    )


def test_create_message(messaging_service, sample_members):
    result = create_sample_message(
        messaging_service,
        sample_members,
    )

    assert result["message_id"] == "message-001"
    assert result["tenant_id"] == "tenant-001"
    assert result["subject"] == "Test Ground Message"
    assert result["status"] == "created"
    assert result["delivered_count"] == 0
    assert result["failed_count"] == 0
    assert result["pending_count"] == 2


def test_duplicate_message_rejected(messaging_service, sample_members):
    create_sample_message(
        messaging_service,
        sample_members,
    )

    with pytest.raises(ValueError):
        create_sample_message(
            messaging_service,
            sample_members,
        )


def test_get_message(messaging_service, sample_members):
    create_sample_message(
        messaging_service,
        sample_members,
    )

    result = messaging_service.get_message(
        message_id="message-001",
        tenant_id="tenant-001",
    )

    assert result["message_id"] == "message-001"
    assert result["tenant_id"] == "tenant-001"


def test_get_message_tenant_isolation(
    messaging_service,
    sample_members,
):
    create_sample_message(
        messaging_service,
        sample_members,
    )

    with pytest.raises(PermissionError):
        messaging_service.get_message(
            message_id="message-001",
            tenant_id="tenant-002",
        )


def test_propagate_message(messaging_service, sample_members):
    create_sample_message(
        messaging_service,
        sample_members,
    )

    result = messaging_service.propagate_message(
        message_id="message-001",
        tenant_id="tenant-001",
        requested_by="test-admin",
        stage="initial",
        batch_size=2,
    )

    assert result["success"] is True
    assert result["message_id"] == "message-001"
    assert result["status"] == "completed"
    assert result["total_recipients"] == 2
    assert result["processed"] == 2
    assert result["delivered"] == 2
    assert result["failed"] == 0


def test_propagation_tenant_isolation(
    messaging_service,
    sample_members,
):
    create_sample_message(
        messaging_service,
        sample_members,
    )

    with pytest.raises(PermissionError):
        messaging_service.propagate_message(
            message_id="message-001",
            tenant_id="tenant-002",
            requested_by="test-admin",
            stage="initial",
            batch_size=2,
        )


def test_propagation_with_batch_size(
    messaging_service,
    sample_members,
):
    create_sample_message(
        messaging_service,
        sample_members,
    )

    first = messaging_service.propagate_message(
        message_id="message-001",
        tenant_id="tenant-001",
        requested_by="test-admin",
        stage="initial",
        batch_size=1,
    )

    assert first["processed"] == 1
    assert first["delivered"] == 1

    second = messaging_service.propagate_message(
        message_id="message-001",
        tenant_id="tenant-001",
        requested_by="test-admin",
        stage="initial",
        batch_size=1,
    )

    assert second["processed"] == 1
    assert second["delivered"] == 1
    assert second["status"] == "completed"


def test_delivery_events(messaging_service, sample_members):
    create_sample_message(
        messaging_service,
        sample_members,
    )

    messaging_service.propagate_message(
        message_id="message-001",
        tenant_id="tenant-001",
        requested_by="test-admin",
        stage="initial",
        batch_size=2,
    )

    events = messaging_service.delivery_events(
        message_id="message-001",
        tenant_id="tenant-001",
    )

    assert isinstance(events, list)
    assert len(events) > 0


def test_search_messages(messaging_service, sample_members):
    create_sample_message(
        messaging_service,
        sample_members,
    )

    result = messaging_service.search_messages(
        tenant_id="tenant-001",
        query="Test Ground",
        page=1,
        page_size=50,
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["message_id"] == "message-001"
def test_blast_radius_blocks_recipients_over_limit():
    service = MessagingService()

    result = service.calculate_blast_radius(
        tenant_id="tenant-001",
        recipient_ids=["m1", "m2", "m3", "m4"],
        max_recipients=2,
    )

    assert result["success"] is False
    assert result["requested_count"] == 4
    assert result["allowed_count"] == 2
    assert result["blocked_count"] == 2
    assert result["affected_members"] == ["m1", "m2"]
    assert result["blocked_members"] == ["m3", "m4"]


def test_blast_radius_removes_duplicate_recipients():
    service = MessagingService()

    result = service.calculate_blast_radius(
        tenant_id="tenant-001",
        recipient_ids=["m1", "m1", "m2", "m2"],
        max_recipients=10,
    )

    assert result["success"] is True
    assert result["requested_count"] == 4
    assert result["allowed_count"] == 2
    assert result["blocked_count"] == 0
    assert result["affected_members"] == ["m1", "m2"]
