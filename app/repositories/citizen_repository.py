
from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from app.core.database import get_db_connection


class CitizenRepository:
    """PostgreSQL persistence for citizen intake and consent."""

    @staticmethod
    def _resolve_organization(connection, tenant_id: str) -> UUID:
        row = connection.execute(
            """
            SELECT id
            FROM tenant_and_configuration.tenants
            WHERE id::text = %(tenant_id)s OR slug = %(tenant_id)s
            LIMIT 1
            """,
            {"tenant_id": tenant_id},
        ).fetchone()

        if row is None:
            raise ValueError(
                f"Tenant '{tenant_id}' does not exist in the database."
            )

        return row[0]

    def create_submission(
        self,
        *,
        tenant_id: str,
        citizen_id: str,
        text: str | None,
        consent: dict[str, Any],
        media: list[dict[str, Any]] | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        anonymous: bool = False,
    ) -> dict[str, Any]:
        if not text and not media:
            raise ValueError("Text or at least one media attachment is required.")

        if (latitude is None) != (longitude is None):
            raise ValueError("Latitude and longitude must be supplied together.")

        if latitude is not None and not -90 <= latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90.")

        if longitude is not None and not -180 <= longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180.")

        purpose_map = {
            "grievance_resolution": "grievance_resolution",
            "grievance resolution": "grievance_resolution",
            "service_notification": "service_notification",
            "service notification": "service_notification",
            "internal_comms": "internal_comms",
            "internal communications": "internal_comms",
        }
        mechanism_map = {
            "in_app_tap": "in_app_tap",
            "in_app": "in_app_tap",
            "voice_confirm": "voice_confirm",
            "voice": "voice_confirm",
            "sms_reply": "sms_reply",
            "sms": "sms_reply",
        }

        raw_purpose = str(consent.get("purpose", "")).strip().lower()
        raw_mechanism = str(consent.get("mechanism", "")).strip().lower()

        purpose = purpose_map.get(raw_purpose)
        mechanism = mechanism_map.get(raw_mechanism)

        if purpose is None:
            raise ValueError(
                "Consent purpose must map to a supported database purpose."
            )

        if mechanism is None:
            raise ValueError(
                "Consent mechanism must map to a supported database mechanism."
            )

        language = str(consent.get("language", "")).strip().lower()
        version = str(consent.get("privacy_notice_version", "")).strip()
        consented_at = consent.get("timestamp")

        if not language or not version or consented_at is None:
            raise ValueError(
                "Consent requires language, privacy notice version and timestamp."
            )

        media_items = media or []
        voice_keys = [
            item["content_reference"]
            for item in media_items
            if item.get("media_type") == "voice"
        ]
        photo_keys = [
            item["content_reference"]
            for item in media_items
            if item.get("media_type") == "photo"
        ]
        video_keys = [
            item["content_reference"]
            for item in media_items
            if item.get("media_type") == "video"
        ]

        with get_db_connection() as connection:
            with connection.transaction():
                organization_id = self._resolve_organization(
                    connection, tenant_id
                )

                notice = connection.execute(
                    """
                    SELECT id
                    FROM consent_privacy_erasure.privacy_notices
                    WHERE organization_id = %s
                      AND version = %s
                      AND lower(language) = %s
                      AND effective_from <= %s
                      AND (
                          superseded_at IS NULL
                          OR superseded_at > %s
                      )
                    ORDER BY effective_from DESC
                    LIMIT 1
                    """,
                    (
                        organization_id,
                        version,
                        language,
                        consented_at,
                        consented_at,
                    ),
                ).fetchone()

                if notice is None:
                    raise ValueError(
                        "No matching effective privacy notice exists for "
                        "this tenant, version and language."
                    )

                receipt = connection.execute(
                    """
                    INSERT INTO consent_privacy_erasure.consent_receipts (
                        organization_id,
                        citizen_handle,
                        purpose,
                        privacy_notice_id,
                        language_shown,
                        mechanism,
                        consented_at,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
                    RETURNING id
                    """,
                    (
                        organization_id,
                        None if anonymous else citizen_id,
                        purpose,
                        notice[0],
                        language,
                        mechanism,
                        consented_at,
                    ),
                ).fetchone()

                if receipt is None:
                    raise RuntimeError("Consent receipt creation failed.")

                reference_number = f"GC-{uuid4().hex[:10].upper()}"

                row = connection.execute(
                    """
                    INSERT INTO citizen_issues.citizen_submissions (
                        organization_id,
                        ref_number,
                        anonymous,
                        citizen_handle,
                        text,
                        voice_storage_key,
                        photo_keys,
                        video_keys,
                        location,
                        consent_receipt_id,
                        submitted_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        CASE
                            WHEN %s IS NULL THEN NULL
                            ELSE ST_SetSRID(
                                ST_MakePoint(%s, %s), 4326
                            )::geography
                        END,
                        %s, NOW()
                    )
                    RETURNING
                        id, organization_id, ref_number,
                        anonymous, citizen_handle, text,
                        voice_storage_key, photo_keys, video_keys,
                        consent_receipt_id, submitted_at
                    """,
                    (
                        organization_id,
                        reference_number,
                        anonymous,
                        None if anonymous else citizen_id,
                        text,
                        voice_keys[0] if voice_keys else None,
                        photo_keys,
                        video_keys,
                        latitude,
                        longitude,
                        latitude,
                        receipt[0],
                    ),
                ).fetchone()

                if row is None:
                    raise RuntimeError("Citizen submission creation failed.")

                columns = (
                    "id",
                    "organization_id",
                    "ref_number",
                    "anonymous",
                    "citizen_handle",
                    "text",
                    "voice_storage_key",
                    "photo_keys",
                    "video_keys",
                    "consent_receipt_id",
                    "submitted_at",
                )
                return dict(zip(columns, row))


citizen_repository = CitizenRepository()
