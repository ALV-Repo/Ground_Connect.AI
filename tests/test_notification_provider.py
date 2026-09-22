import pytest

from app.schemas.notification_provider import (
    NotificationChannel,
    NotificationSendRequest,
    ProviderCreate,
    ProviderStatus,
)
from app.services.notification_provider import NotificationProviderService


def make_provider(
    tenant_id="tenant-1",
    name="Primary SMS",
    channel=NotificationChannel.SMS,
    priority=1,
    enabled=True,
):
    return ProviderCreate(
        tenant_id=tenant_id,
        provider_name=name,
        channel=channel,
        priority=priority,
        enabled=enabled,
    )


def make_request(
    tenant_id="tenant-1",
    channel=NotificationChannel.SMS,
):
    return NotificationSendRequest(
        tenant_id=tenant_id,
        channel=channel,
        recipient="+919999999999",
        message="Test notification",
    )


def test_register_provider():
    service = NotificationProviderService()

    result = service.register_provider(
        make_provider()
    )

    assert result.provider_id.startswith("provider_")
    assert result.tenant_id == "tenant-1"
    assert result.channel == NotificationChannel.SMS
    assert result.status == ProviderStatus.ACTIVE
    assert result.enabled is True


def test_list_providers_sorted_by_priority():
    service = NotificationProviderService()

    service.register_provider(
        make_provider(
            name="Secondary",
            priority=2,
        )
    )

    service.register_provider(
        make_provider(
            name="Primary",
            priority=1,
        )
    )

    providers = service.list_providers(
        tenant_id="tenant-1",
        channel=NotificationChannel.SMS,
    )

    assert len(providers) == 2
    assert providers[0].provider_name == "Primary"
    assert providers[1].provider_name == "Secondary"


def test_provider_is_tenant_scoped():
    service = NotificationProviderService()

    provider = service.register_provider(
        make_provider()
    )

    with pytest.raises(PermissionError):
        service.get_provider(
            tenant_id="tenant-2",
            provider_id=provider.provider_id,
        )


def test_provider_status_can_be_changed():
    service = NotificationProviderService()

    provider = service.register_provider(
        make_provider()
    )

    result = service.set_provider_status(
        tenant_id="tenant-1",
        provider_id=provider.provider_id,
        status=ProviderStatus.DISABLED,
    )

    assert result.status == ProviderStatus.DISABLED
    assert result.enabled is False


def test_successful_notification_uses_primary_provider():
    service = NotificationProviderService()

    primary = service.register_provider(
        make_provider(
            name="Primary",
            priority=1,
        )
    )

    service.register_provider(
        make_provider(
            name="Secondary",
            priority=2,
        )
    )

    result = service.send(
        make_request()
    )

    assert result.status == "sent"
    assert result.provider_id == primary.provider_id
    assert result.attempts == 1
    assert result.failed_providers == []


def test_automatic_failover_to_secondary_provider():
    service = NotificationProviderService()

    primary = service.register_provider(
        make_provider(
            name="fail-primary",
            priority=1,
        )
    )

    secondary = service.register_provider(
        make_provider(
            name="secondary",
            priority=2,
        )
    )

    result = service.send(
        make_request()
    )

    assert result.status == "sent"
    assert result.provider_id == secondary.provider_id
    assert result.attempts == 2
    assert primary.provider_id in result.failed_providers


def test_failed_provider_is_marked_failed():
    service = NotificationProviderService()

    primary = service.register_provider(
        make_provider(
            name="fail-primary",
            priority=1,
        )
    )

    service.register_provider(
        make_provider(
            name="secondary",
            priority=2,
        )
    )

    service.send(
        make_request()
    )

    result = service.get_provider(
        tenant_id="tenant-1",
        provider_id=primary.provider_id,
    )

    assert result.status == ProviderStatus.FAILED


def test_all_failed_providers_raise_error():
    service = NotificationProviderService()

    service.register_provider(
        make_provider(
            name="fail-primary",
            priority=1,
        )
    )

    service.register_provider(
        make_provider(
            name="fail-secondary",
            priority=2,
        )
    )

    with pytest.raises(RuntimeError, match="All sms providers failed"):
        service.send(
            make_request()
        )


def test_no_provider_configured():
    service = NotificationProviderService()

    with pytest.raises(LookupError):
        service.send(
            make_request()
        )


def test_email_provider_is_supported():
    service = NotificationProviderService()

    provider = service.register_provider(
        make_provider(
            name="Email Provider",
            channel=NotificationChannel.EMAIL,
        )
    )

    result = service.send(
        make_request(
            channel=NotificationChannel.EMAIL,
        )
    )

    assert result.status == "sent"
    assert result.provider_id == provider.provider_id
    assert result.channel == NotificationChannel.EMAIL


def test_disabled_provider_is_skipped():
    service = NotificationProviderService()

    disabled = service.register_provider(
        make_provider(
            name="Disabled Provider",
            priority=1,
            enabled=False,
        )
    )

    active = service.register_provider(
        make_provider(
            name="Active Provider",
            priority=2,
        )
    )

    result = service.send(
        make_request()
    )

    assert result.provider_id == active.provider_id
    assert result.attempts == 1
    assert disabled.provider_id not in result.failed_providers


def test_cross_tenant_providers_are_not_used():
    service = NotificationProviderService()

    service.register_provider(
        make_provider(
            tenant_id="tenant-1",
            name="Tenant 1 Provider",
        )
    )

    with pytest.raises(LookupError):
        service.send(
            make_request(
                tenant_id="tenant-2",
            )
        )
        