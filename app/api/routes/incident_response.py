from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.security import incident_response_service
from app.schemas.security import (
    IncidentEvidenceRequest,
    IncidentRouteCreateRequest,
)


router = APIRouter(
    prefix="/incident-response",
    tags=["Incident Response"],
)


# ============================================================
# BE-013: Incident Response
# ============================================================


@router.post("/incidents")
def create_incident(
    payload: IncidentRouteCreateRequest,
):
    """
    Create a security incident.
    """
    try:
        title = payload.title or payload.incident_type

        if not title:
            raise ValueError("title is required")

        if not payload.description:
            raise ValueError("description is required")

        if not payload.severity:
            raise ValueError("severity is required")

        return incident_response_service.create_incident(
            title=title,
            description=payload.description,
            severity=payload.severity,
            assigned_to=payload.assigned_to,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/incidents/{incident_id}")
def get_incident(
    incident_id: str,
):
    """
    Get incident details.
    """
    incident = incident_response_service.get_incident(
        incident_id
    )

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail=f"Incident '{incident_id}' not found.",
        )

    return incident


@router.post("/incidents/{incident_id}/acknowledge")
def acknowledge_incident(
    incident_id: str,
    acknowledged_by: str = Query(...),
):
    """
    Acknowledge a security incident.

    The IncidentStatus model does not have a separate
    ACKNOWLEDGED state, so acknowledgement moves the
    incident into INVESTIGATING.
    """
    try:
        return incident_response_service.update_status(
            incident_id=incident_id,
            status="INVESTIGATING",
            notes=f"Acknowledged by {acknowledged_by}",
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/incidents/{incident_id}/contain")
def contain_incident(
    incident_id: str,
    contained_by: str = Query(...),
    action: Optional[str] = Query(None),
):
    """
    Mark an incident as contained.
    """
    try:
        notes = f"Contained by {contained_by}"

        if action:
            notes = f"{notes}. Action: {action}"

        return incident_response_service.update_status(
            incident_id=incident_id,
            status="CONTAINED",
            notes=notes,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/incidents/{incident_id}/resolve")
def resolve_incident(
    incident_id: str,
    resolved_by: str = Query(...),
    resolution: Optional[str] = Query(None),
):
    """
    Resolve a security incident.
    """
    try:
        notes = f"Resolved by {resolved_by}"

        if resolution:
            notes = f"{notes}. Resolution: {resolution}"

        return incident_response_service.update_status(
            incident_id=incident_id,
            status="RESOLVED",
            notes=notes,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/incidents")
def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
    ),
):
    """
    List security incidents.
    """
    try:
        incidents = incident_response_service.list_incidents(
            status=status,
            severity=severity,
        )

        return {
            "items": incidents[:limit],
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Incident Assignment & Escalation
# ============================================================


@router.post("/incidents/{incident_id}/assign")
def assign_incident(
    incident_id: str,
    assignee: str = Query(...),
):
    """
    Assign an incident to a responsible person.
    """
    try:
        return incident_response_service.assign_incident(
            incident_id=incident_id,
            assignee=assignee,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/incidents/{incident_id}/escalate")
def escalate_incident(
    incident_id: str,
):
    """
    Escalate an incident to the next escalation level.
    """
    try:
        return incident_response_service.escalate(
            incident_id=incident_id,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Evidence Preservation
# ============================================================


@router.post("/incidents/{incident_id}/evidence")
def preserve_evidence(
    incident_id: str,
    payload: IncidentEvidenceRequest,
):
    """
    Preserve incident evidence.

    The evidence string is encoded as UTF-8 bytes and
    integrity-protected using SHA-256 by the service.
    """
    try:
        return incident_response_service.preserve_evidence(
            incident_id=incident_id,
            evidence_type=payload.evidence_type,
            evidence_bytes=payload.evidence.encode("utf-8"),
            captured_by=payload.captured_by,
            location_reference=payload.location_reference,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/evidence/{evidence_id}")
def get_evidence(
    evidence_id: str,
):
    """
    Get preserved evidence metadata.
    """
    evidence = incident_response_service.get_evidence(
        evidence_id
    )

    if evidence is None:
        raise HTTPException(
            status_code=404,
            detail=f"Evidence '{evidence_id}' not found.",
        )

    return evidence


# ============================================================
# Security Responsibilities
# ============================================================


@router.post("/responsibilities/{responsibility}")
def assign_responsibility(
    responsibility: str,
    person_id: str = Query(...),
):
    """
    Assign a security incident-response responsibility.
    """
    try:
        return incident_response_service.assign_responsibility(
            responsibility=responsibility,
            person_id=person_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/responsibilities")
def get_responsibilities():
    """
    Return currently assigned security responsibilities.
    """
    return incident_response_service.get_responsibilities()


# ============================================================
# Vulnerability Management
# ============================================================


@router.get("/vulnerability/sla")
def vulnerability_sla(
    severity: str = Query(...),
):
    """
    Return vulnerability remediation SLA for a severity.
    """
    try:
        return incident_response_service.vulnerability_sla(
            severity=severity,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Pentest Gate
# ============================================================


@router.get("/pentest/status")
def pentest_status():
    """
    Return current penetration-testing gate status.
    """
    return incident_response_service.production_release_check()


@router.post("/pentest/gate")
def update_pentest_gate(
    passed: bool,
    evidence: Optional[str] = None,
):
    """
    Record the pentest gate result.

    A passing gate records zero critical/high findings.
    A failed gate records a blocking critical finding.
    """
    try:
        if passed:
            critical_findings = 0
            high_findings = 0
        else:
            critical_findings = 1
            high_findings = 0

        result = incident_response_service.record_pentest(
            critical_findings=critical_findings,
            high_findings=high_findings,
            completed=True,
        )

        if evidence:
            result["evidence"] = evidence

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Security Readiness
# ============================================================


@router.get("/status")
def incident_response_status():
    """
    Return incident-response readiness information.
    """
    pentest = incident_response_service.production_release_check()

    return {
        "incident_response": {
            "service_available": True,
            "severity_classification": True,
            "incident_tracking": True,
            "escalation": True,
            "evidence_preservation": True,
            "responsibility_assignment": True,
            "vulnerability_sla": True,
        },
        "pentest": pentest,
    }