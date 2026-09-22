from __future__ import annotations

import re
import uuid
from typing import Dict, List

from app.schemas.content_scanner import (
    ContentScanRequest,
    ContentScanResponse,
    ScanMatch,
    ScanSeverity,
)


class ContentScannerService:
    """
    Deterministic prohibited-attribute scanner.

    This implementation flags explicitly configured prohibited
    attributes and creates an alert when a match is found.
    """

    PROHIBITED_PATTERNS: Dict[str, tuple[str, ScanSeverity, str]] = {
        "religion": (
            r"\b(religion|religious|muslim|hindu|christian|sikh|jewish)\b",
            ScanSeverity.HIGH,
            "Religious attribute detected",
        ),
        "caste": (
            r"\b(caste|dalit|brahmin|rajput)\b",
            ScanSeverity.HIGH,
            "Caste attribute detected",
        ),
        "political_affiliation": (
            r"\b(political\s+party|party\s+member|political\s+affiliation)\b",
            ScanSeverity.HIGH,
            "Political affiliation detected",
        ),
        "sexual_orientation": (
            r"\b(sexual\s+orientation|gay|lesbian|bisexual)\b",
            ScanSeverity.HIGH,
            "Sexual orientation attribute detected",
        ),
        "health_condition": (
            r"\b(health\s+condition|medical\s+condition|disability)\b",
            ScanSeverity.HIGH,
            "Sensitive health attribute detected",
        ),
        "biometric": (
            r"\b(biometric|fingerprint|facial\s+recognition)\b",
            ScanSeverity.CRITICAL,
            "Biometric attribute detected",
        ),
    }

    def __init__(self):
        self._alerts: List[dict] = []

    def scan(
        self,
        request: ContentScanRequest,
    ) -> ContentScanResponse:
        scan_id = f"scan_{uuid.uuid4().hex}"

        matches: List[ScanMatch] = []

        for attribute, (
            pattern,
            severity,
            reason,
        ) in self.PROHIBITED_PATTERNS.items():

            match = re.search(
                pattern,
                request.content,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            matches.append(
                ScanMatch(
                    attribute=attribute,
                    matched_text=match.group(0),
                    severity=severity,
                    reason=reason,
                )
            )

        alert_created = bool(matches)

        if alert_created:
            self._alerts.append(
                {
                    "scan_id": scan_id,
                    "tenant_id": request.tenant_id,
                    "source": request.source,
                    "matches": matches,
                }
            )

        return ContentScanResponse(
            scan_id=scan_id,
            tenant_id=request.tenant_id,
            safe=not bool(matches),
            matches=matches,
            alert_created=alert_created,
        )

    def list_alerts(
        self,
        tenant_id: str,
    ) -> List[dict]:
        return [
            alert
            for alert in self._alerts
            if alert["tenant_id"] == tenant_id
        ]

    def get_alert(
        self,
        tenant_id: str,
        scan_id: str,
    ) -> dict:
        for alert in self._alerts:
            if alert["scan_id"] != scan_id:
                continue

            if alert["tenant_id"] != tenant_id:
                raise PermissionError(
                    "Cross-tenant alert access denied"
                )

            return alert

        raise KeyError("Content scan alert not found")


content_scanner_service = ContentScannerService()