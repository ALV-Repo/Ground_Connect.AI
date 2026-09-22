from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

from app.schemas.public_api import (
    CredentialScope,
    PublicCredentialCreate,
    PublicCredentialResponse,
    WebhookCreate,
    WebhookDeliveryResponse,
    WebhookEventRequest,
    WebhookResponse,
)


class PublicAPIService:
    def __init__(self):
        self._credentials = {}
        self._webhooks = {}
        self._deliveries = {}

        self._rate_windows = defaultdict(deque)
        self._used_event_ids = set()

    # ---------------------------------------------------------
    # Public API credentials
    # ---------------------------------------------------------

    def create_credential(
        self,
        request: PublicCredentialCreate,
    ) -> PublicCredentialResponse:
        credential_id = f"cred_{uuid.uuid4().hex}"

        credential = PublicCredentialResponse(
            credential_id=credential_id,
            tenant_id=request.tenant_id,
            name=request.name,
            scopes=request.scopes,
            rate_limit_per_minute=request.rate_limit_per_minute,
            active=True,
            created_at=datetime.now(timezone.utc),
        )

        self._credentials[credential_id] = credential

        return credential

    def get_credential(
        self,
        tenant_id: str,
        credential_id: str,
    ) -> PublicCredentialResponse:
        credential = self._credentials.get(credential_id)

        if not credential:
            raise KeyError("Public credential not found")

        if credential.tenant_id != tenant_id:
            raise PermissionError("Cross-tenant credential access denied")

        return credential

    def check_scope(
        self,
        tenant_id: str,
        credential_id: str,
        required_scope: CredentialScope,
    ) -> bool:
        credential = self.get_credential(
            tenant_id=tenant_id,
            credential_id=credential_id,
        )

        if not credential.active:
            raise PermissionError("Public credential is inactive")

        if required_scope not in credential.scopes:
            raise PermissionError(
                f"Required scope missing: {required_scope.value}"
            )

        return True

    # ---------------------------------------------------------
    # Per-scope rate limiting
    # ---------------------------------------------------------

    def check_rate_limit(
        self,
        tenant_id: str,
        credential_id: str,
        scope: CredentialScope,
    ) -> bool:
        credential = self.get_credential(
            tenant_id=tenant_id,
            credential_id=credential_id,
        )

        self.check_scope(
            tenant_id=tenant_id,
            credential_id=credential_id,
            required_scope=scope,
        )

        key = f"{tenant_id}:{credential_id}:{scope.value}"
        now = time.monotonic()

        window = self._rate_windows[key]

        while window and now - window[0] >= 60:
            window.popleft()

        if len(window) >= credential.rate_limit_per_minute:
            raise PermissionError("Rate limit exceeded")

        window.append(now)

        return True

    # ---------------------------------------------------------
    # Webhooks
    # ---------------------------------------------------------

    def create_webhook(
        self,
        request: WebhookCreate,
    ) -> WebhookResponse:
        webhook_id = f"wh_{uuid.uuid4().hex}"

        webhook = WebhookResponse(
            webhook_id=webhook_id,
            tenant_id=request.tenant_id,
            url=str(request.url),
            events=request.events,
            active=True,
            created_at=datetime.now(timezone.utc),
        )

        self._webhooks[webhook_id] = {
            "webhook": webhook,
            "secret": request.secret,
        }

        return webhook

    def get_webhook(
        self,
        tenant_id: str,
        webhook_id: str,
    ) -> WebhookResponse:
        record = self._webhooks.get(webhook_id)

        if not record:
            raise KeyError("Webhook not found")

        webhook = record["webhook"]

        if webhook.tenant_id != tenant_id:
            raise PermissionError("Cross-tenant webhook access denied")

        return webhook

    # ---------------------------------------------------------
    # Signed webhook delivery
    # ---------------------------------------------------------

    def deliver_event(
        self,
        request: WebhookEventRequest,
    ) -> list[WebhookDeliveryResponse]:
        event_id = request.event_id or f"evt_{uuid.uuid4().hex}"

        if event_id in self._used_event_ids:
            raise ValueError("Replay detected: event has already been processed")

        self._used_event_ids.add(event_id)

        deliveries = []

        for webhook_id, record in self._webhooks.items():
            webhook = record["webhook"]

            if webhook.tenant_id != request.tenant_id:
                continue

            if not webhook.active:
                continue

            if request.event_type not in webhook.events:
                continue

            secret = record["secret"]

            timestamp = str(int(time.time()))

            payload_text = str(request.payload)

            signing_value = (
                f"{event_id}.{timestamp}.{payload_text}"
            )

            signature = hmac.new(
                secret.encode("utf-8"),
                signing_value.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            delivery_id = f"delivery_{uuid.uuid4().hex}"

            delivery = WebhookDeliveryResponse(
                delivery_id=delivery_id,
                webhook_id=webhook_id,
                event_type=request.event_type,
                signature=f"sha256={signature}",
                attempt=1,
                status="pending",
            )

            self._deliveries[delivery_id] = {
                "delivery": delivery,
                "event_id": event_id,
                "timestamp": timestamp,
                "payload": request.payload,
            }

            deliveries.append(delivery)

        return deliveries

    # ---------------------------------------------------------
    # Retry
    # ---------------------------------------------------------

    def retry_delivery(
        self,
        tenant_id: str,
        delivery_id: str,
    ) -> WebhookDeliveryResponse:
        record = self._deliveries.get(delivery_id)

        if not record:
            raise KeyError("Webhook delivery not found")

        delivery = record["delivery"]

        self.get_webhook(
            tenant_id=tenant_id,
            webhook_id=delivery.webhook_id,
        )

        updated = delivery.model_copy(
            update={
                "attempt": delivery.attempt + 1,
                "status": "retrying",
            }
        )

        self._deliveries[delivery_id]["delivery"] = updated

        return updated

    def get_delivery(
        self,
        tenant_id: str,
        delivery_id: str,
    ) -> WebhookDeliveryResponse:
        record = self._deliveries.get(delivery_id)

        if not record:
            raise KeyError("Webhook delivery not found")

        delivery = record["delivery"]

        self.get_webhook(
            tenant_id=tenant_id,
            webhook_id=delivery.webhook_id,
        )

        return delivery


public_api_service = PublicAPIService()