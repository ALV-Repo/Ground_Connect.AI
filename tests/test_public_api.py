import pytest

from app.schemas.public_api import (
    CredentialScope,
    PublicCredentialCreate,
    WebhookCreate,
    WebhookEventRequest,
)
from app.services.public_api import PublicAPIService


def make_credential(
    tenant_id="tenant-1",
    scopes=None,
    rate_limit=60,
):
    if scopes is None:
        scopes = [
            CredentialScope.ISSUES_READ,
            CredentialScope.ISSUES_WRITE,
        ]

    return PublicCredentialCreate(
        tenant_id=tenant_id,
        name="Test Public Credential",
        scopes=scopes,
        rate_limit_per_minute=rate_limit,
    )


def make_webhook(tenant_id="tenant-1"):
    return WebhookCreate(
        tenant_id=tenant_id,
        url="https://example.com/webhook",
        events=["issue.created", "issue.updated"],
        secret="super-secret-key-123",
    )


def test_create_public_credential():
    service = PublicAPIService()

    result = service.create_credential(
        make_credential()
    )

    assert result.credential_id.startswith("cred_")
    assert result.tenant_id == "tenant-1"
    assert result.active is True
    assert CredentialScope.ISSUES_READ in result.scopes


def test_scope_is_enforced():
    service = PublicAPIService()

    credential = service.create_credential(
        make_credential(
            scopes=[CredentialScope.ISSUES_READ]
        )
    )

    assert service.check_scope(
        tenant_id="tenant-1",
        credential_id=credential.credential_id,
        required_scope=CredentialScope.ISSUES_READ,
    )

    with pytest.raises(PermissionError):
        service.check_scope(
            tenant_id="tenant-1",
            credential_id=credential.credential_id,
            required_scope=CredentialScope.ISSUES_WRITE,
        )


def test_cross_tenant_credential_access_is_blocked():
    service = PublicAPIService()

    credential = service.create_credential(
        make_credential(tenant_id="tenant-1")
    )

    with pytest.raises(PermissionError):
        service.get_credential(
            tenant_id="tenant-2",
            credential_id=credential.credential_id,
        )


def test_per_scope_rate_limit():
    service = PublicAPIService()

    credential = service.create_credential(
        make_credential(rate_limit=2)
    )

    service.check_rate_limit(
        tenant_id="tenant-1",
        credential_id=credential.credential_id,
        scope=CredentialScope.ISSUES_READ,
    )

    service.check_rate_limit(
        tenant_id="tenant-1",
        credential_id=credential.credential_id,
        scope=CredentialScope.ISSUES_READ,
    )

    with pytest.raises(PermissionError):
        service.check_rate_limit(
            tenant_id="tenant-1",
            credential_id=credential.credential_id,
            scope=CredentialScope.ISSUES_READ,
        )


def test_rate_limit_is_per_scope():
    service = PublicAPIService()

    credential = service.create_credential(
        make_credential(rate_limit=1)
    )

    service.check_rate_limit(
        tenant_id="tenant-1",
        credential_id=credential.credential_id,
        scope=CredentialScope.ISSUES_READ,
    )

    # Different scope has its own rate-limit window.
    assert service.check_rate_limit(
        tenant_id="tenant-1",
        credential_id=credential.credential_id,
        scope=CredentialScope.ISSUES_WRITE,
    )


def test_create_webhook():
    service = PublicAPIService()

    result = service.create_webhook(
        make_webhook()
    )

    assert result.webhook_id.startswith("wh_")
    assert result.tenant_id == "tenant-1"
    assert result.active is True
    assert "issue.created" in result.events


def test_cross_tenant_webhook_access_is_blocked():
    service = PublicAPIService()

    webhook = service.create_webhook(
        make_webhook(tenant_id="tenant-1")
    )

    with pytest.raises(PermissionError):
        service.get_webhook(
            tenant_id="tenant-2",
            webhook_id=webhook.webhook_id,
        )


def test_signed_webhook_delivery():
    service = PublicAPIService()

    service.create_webhook(
        make_webhook()
    )

    deliveries = service.deliver_event(
        WebhookEventRequest(
            tenant_id="tenant-1",
            event_type="issue.created",
            payload={
                "issue_id": "issue-123",
                "status": "new",
            },
            event_id="event-001",
        )
    )

    assert len(deliveries) == 1
    assert deliveries[0].signature.startswith("sha256=")
    assert deliveries[0].attempt == 1
    assert deliveries[0].status == "pending"


def test_unsubscribed_event_is_not_delivered():
    service = PublicAPIService()

    service.create_webhook(
        make_webhook()
    )

    deliveries = service.deliver_event(
        WebhookEventRequest(
            tenant_id="tenant-1",
            event_type="task.created",
            payload={"task_id": "task-123"},
            event_id="event-002",
        )
    )

    assert deliveries == []


def test_webhook_event_is_tenant_scoped():
    service = PublicAPIService()

    service.create_webhook(
        make_webhook(tenant_id="tenant-1")
    )

    deliveries = service.deliver_event(
        WebhookEventRequest(
            tenant_id="tenant-2",
            event_type="issue.created",
            payload={"issue_id": "issue-123"},
            event_id="event-003",
        )
    )

    assert deliveries == []


def test_replay_protection():
    service = PublicAPIService()

    service.create_webhook(
        make_webhook()
    )

    request = WebhookEventRequest(
        tenant_id="tenant-1",
        event_type="issue.created",
        payload={"issue_id": "issue-123"},
        event_id="event-replay",
    )

    first = service.deliver_event(request)

    assert len(first) == 1

    with pytest.raises(ValueError, match="Replay detected"):
        service.deliver_event(request)


def test_webhook_retry():
    service = PublicAPIService()

    service.create_webhook(
        make_webhook()
    )

    deliveries = service.deliver_event(
        WebhookEventRequest(
            tenant_id="tenant-1",
            event_type="issue.created",
            payload={"issue_id": "issue-123"},
            event_id="event-retry",
        )
    )

    delivery = deliveries[0]

    result = service.retry_delivery(
        tenant_id="tenant-1",
        delivery_id=delivery.delivery_id,
    )

    assert result.delivery_id == delivery.delivery_id
    assert result.attempt == 2
    assert result.status == "retrying"


def test_delivery_is_tenant_scoped():
    service = PublicAPIService()

    service.create_webhook(
        make_webhook(tenant_id="tenant-1")
    )

    deliveries = service.deliver_event(
        WebhookEventRequest(
            tenant_id="tenant-1",
            event_type="issue.created",
            payload={"issue_id": "issue-123"},
            event_id="event-tenant",
        )
    )

    delivery = deliveries[0]

    with pytest.raises(PermissionError):
        service.get_delivery(
            tenant_id="tenant-2",
            delivery_id=delivery.delivery_id,
        )