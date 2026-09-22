from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.citizen import (
    CitizenIssueCreateRequest,
    CitizenIssueResponse,
    CitizenIssueClassificationRequest,
    CitizenClusterResponse,
    ClusterSuggestionRequest,
    ClusterConfirmRequest,
    ClusterCorroborationRequest,
    ClusterSplitRequest,
    ClusterMergeRequest,
    ClusterActionResponse,
)

from app.services.citizen import citizen_service


router = APIRouter(
    prefix="/citizen",
    tags=["Citizen Issues"],
)


# ============================================================
# Citizen Issue Intake
# ============================================================

@router.post(
    "/issues",
    response_model=CitizenIssueResponse,
)
def create_citizen_issue(
    request: CitizenIssueCreateRequest,
):
    try:
        return citizen_service.create_issue(
            request=request,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Get Citizen Issue
# ============================================================

@router.get(
    "/issues/{issue_id}",
    response_model=CitizenIssueResponse,
)
def get_citizen_issue(
    issue_id: str,
    tenant_id: str = Query(...),
):
    try:
        return citizen_service.get_issue(
            issue_id=issue_id,
            tenant_id=tenant_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


# ============================================================
# List Citizen Issues
# ============================================================

@router.get(
    "/issues",
    response_model=list[CitizenIssueResponse],
)
def list_citizen_issues(
    tenant_id: str = Query(...),
):
    return citizen_service.list_issues(
        tenant_id=tenant_id,
    )


# ============================================================
# Human Classification / Correction
# ============================================================

@router.post(
    "/issues/classify",
    response_model=CitizenIssueResponse,
)
def classify_citizen_issue(
    request: CitizenIssueClassificationRequest,
    tenant_id: str = Query(...),
):
    try:
        return citizen_service.classify_issue(
            request=request,
            tenant_id=tenant_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Cluster Suggestions
# ============================================================

@router.post(
    "/clusters/suggestions",
)
def suggest_clusters(
    request: ClusterSuggestionRequest,
    tenant_id: str = Query(...),
    proximity_km: float = Query(
        default=1.0,
        gt=0,
        le=100,
    ),
    similarity_threshold: float = Query(
        default=0.25,
        ge=0,
        le=1,
    ),
):
    try:
        return {
            "issue_id": request.issue_id,
            "suggestions": citizen_service.suggest_clusters(
                issue_id=request.issue_id,
                tenant_id=tenant_id,
                proximity_km=proximity_km,
                similarity_threshold=similarity_threshold,
            ),
        }
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


# ============================================================
# Create Cluster
# ============================================================

@router.post(
    "/clusters",
    response_model=CitizenClusterResponse,
)
def create_cluster(
    request: ClusterConfirmRequest,
    issue_id: str = Query(...),
    tenant_id: str = Query(...),
    issue_ids: list[str] = Query(default=[]),
):
    try:
        cluster = citizen_service.create_cluster(
            issue_id=issue_id,
            tenant_id=tenant_id,
            created_by=request.confirmed_by,
            issue_ids=issue_ids,
        )

        return citizen_service.confirm_cluster(
            request=request.model_copy(
                update={
                    "cluster_id": cluster["cluster_id"],
                }
            ),
            tenant_id=tenant_id,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Corroborate Cluster
# ============================================================

@router.post(
    "/clusters/{cluster_id}/corroborate",
    response_model=CitizenClusterResponse,
)
def corroborate_cluster(
    cluster_id: str,
    request: ClusterCorroborationRequest,
    tenant_id: str = Query(...),
):
    try:
        return citizen_service.add_corroboration(
            cluster_id=cluster_id,
            issue_id=request.issue_id,
            citizen_id=request.citizen_id,
            tenant_id=tenant_id,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Confirm Existing Cluster
# ============================================================

@router.post(
    "/clusters/{cluster_id}/confirm",
    response_model=CitizenClusterResponse,
)
def confirm_cluster(
    cluster_id: str,
    request: ClusterConfirmRequest,
    tenant_id: str = Query(...),
):
    try:
        request = request.model_copy(
            update={
                "cluster_id": cluster_id,
            }
        )

        return citizen_service.confirm_cluster(
            request=request,
            tenant_id=tenant_id,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


# ============================================================
# Split Cluster
# ============================================================

@router.post(
    "/clusters/{cluster_id}/split",
    response_model=ClusterActionResponse,
)
def split_cluster(
    cluster_id: str,
    request: ClusterSplitRequest,
    tenant_id: str = Query(...),
):
    try:
        request = request.model_copy(
            update={
                "cluster_id": cluster_id,
            }
        )

        cluster = citizen_service.split_cluster(
            request=request,
            tenant_id=tenant_id,
        )

        return {
            "success": True,
            "cluster_id": cluster["cluster_id"],
            "action": "split",
            "canonical_issue_id": cluster.get(
                "canonical_issue_id"
            ),
            "issue_ids": cluster["issue_ids"],
            "history_preserved": True,
            "updated_at": cluster["updated_at"],
        }

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Merge Clusters
# ============================================================

@router.post(
    "/clusters/{cluster_id}/merge",
    response_model=ClusterActionResponse,
)
def merge_clusters(
    cluster_id: str,
    request: ClusterMergeRequest,
    tenant_id: str = Query(...),
):
    try:
        request = request.model_copy(
            update={
                "cluster_id": cluster_id,
            }
        )

        cluster = citizen_service.merge_clusters(
            request=request,
            tenant_id=tenant_id,
        )

        return {
            "success": True,
            "cluster_id": cluster["cluster_id"],
            "action": "merge",
            "canonical_issue_id": cluster.get(
                "canonical_issue_id"
            ),
            "issue_ids": cluster["issue_ids"],
            "history_preserved": True,
            "updated_at": cluster["updated_at"],
        }

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Get Cluster
# ============================================================

@router.get(
    "/clusters/{cluster_id}",
    response_model=CitizenClusterResponse,
)
def get_cluster(
    cluster_id: str,
    tenant_id: str = Query(...),
):
    try:
        return citizen_service.get_cluster(
            cluster_id=cluster_id,
            tenant_id=tenant_id,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


# ============================================================
# List Clusters
# ============================================================

@router.get(
    "/clusters",
    response_model=list[CitizenClusterResponse],
)
def list_clusters(
    tenant_id: str = Query(...),
):
    return citizen_service.list_clusters(
        tenant_id=tenant_id,
    )