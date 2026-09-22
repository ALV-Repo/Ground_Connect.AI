from __future__ import annotations

import uuid
from typing import Dict, List

from app.schemas.notification_provider import (
    NotificationChannel,
    NotificationSendRequest,
    NotificationSendResponse,
    ProviderCreate,
    ProviderResponse,
    ProviderStatus,
)


class NotificationProviderService:
    def __init__(self):
        self._providers: Dict[str, ProviderResponse] = {}

    def register_provider(
        self,
        request: ProviderCreate,
    ) -> ProviderResponse:
        provider_id = f"provider_{uuid.uuid4().hex}"

        provider = ProviderResponse(
            provider_id=provider_id,
            tenant_id=request.tenant_id,
            provider_name=request.provider_name,
            channel=request.channel,
            priority=request.priority,
            status=(
                ProviderStatus.ACTIVE
                if request.enabled
                else ProviderStatus.DISABLED
            ),
            enabled=request.enabled,
        )

        self._providers[provider_id] = provider

        return provider

    def list_providers(
        self,
        tenant_id: str,
        channel: NotificationChannel,
    ) -> List[ProviderResponse]:
        providers = [
            provider
            for provider in self._providers.values()
            if provider.tenant_id == tenant_id
            and provider.channel == channel
        ]

        return sorted(
            providers,
            key=lambda provider: provider.priority,
        )

    def get_provider(
        self,
        tenant_id: str,
        provider_id: str,
    ) -> ProviderResponse:
        provider = self._providers.get(provider_id)

        if not provider:
            raise KeyError("Notification provider not found")

        if provider.tenant_id != tenant_id:
            raise PermissionError(
                "Cross-tenant provider access denied"
            )

        return provider

    def set_provider_status(
        self,
        tenant_id: str,
        provider_id: str,
        status: ProviderStatus,
    ) -> ProviderResponse:
        provider = self.get_provider(
            tenant_id=tenant_id,
            provider_id=provider_id,
        )

        updated = provider.model_copy(
            update={
                "status": status,
                "enabled": status != ProviderStatus.DISABLED,
            }
        )

        self._providers[provider_id] = updated

        return updated

    def _send_with_provider(
        self,
        provider: ProviderResponse,
        request: NotificationSendRequest,
    ) -> bool:
        """
        Provider adapter boundary.

        In the current backend implementation this is a deterministic
        in-memory adapter. A real SMS/email provider can be plugged in
        behind this method without changing the public service contract.
        """

        if provider.status != ProviderStatus.ACTIVE:
            return False

        # Deterministic failure hook for tests/provider failover.
        if provider.provider_name.lower().startswith("fail"):
            return False

        if not request.recipient.strip():
            return False

        if not request.message.strip():
            return False

        return True

    def send(
        self,
        request: NotificationSendRequest,
    ) -> NotificationSendResponse:
        providers = self.list_providers(
            tenant_id=request.tenant_id,
            channel=request.channel,
        )

        if not providers:
            raise LookupError(
                f"No providers configured for {request.channel.value}"
            )

        notification_id = f"notification_{uuid.uuid4().hex}"

        attempts = 0
        failed_providers: List[str] = []

        for provider in providers:
            if provider.status != ProviderStatus.ACTIVE:
                continue

            attempts += 1

            success = self._send_with_provider(
                provider=provider,
                request=request,
            )

            if success:
                return NotificationSendResponse(
                    notification_id=notification_id,
                    tenant_id=request.tenant_id,
                    channel=request.channel,
                    status="sent",
                    provider_id=provider.provider_id,
                    attempts=attempts,
                    failed_providers=failed_providers,
                )

            failed_providers.append(provider.provider_id)

            # Mark failed provider so subsequent sends can fail over
            # to the next configured provider.
            self._providers[provider.provider_id] = provider.model_copy(
                update={
                    "status": ProviderStatus.FAILED,
                    "enabled": True,
                }
            )

        raise RuntimeError(
            f"All {request.channel.value} providers failed"
        )


notification_provider_service = NotificationProviderService()