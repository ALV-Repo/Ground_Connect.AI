from __future__ import annotations

from datetime import datetime, timezone
from math import radians, sin, cos, sqrt, atan2
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.schemas.citizen import (
    CitizenIssueCreateRequest,
    CitizenIssueClassificationRequest,
    ClusterConfirmRequest,
    ClusterMergeRequest,
    ClusterSplitRequest,
)


class CitizenService:
    """
    BE-018 — Citizen Issue Intake & Clustering

    Responsibilities:
    - Citizen issue intake
    - Text / voice / photo / video submissions
    - Consent receipt
    - AI classification proposal
    - Human classification correction/confirmation
    - Issue clustering suggestions
    - Human-confirmable clustering
    - Reversible split / merge
    - Distinct citizen corroboration counting
    - Tenant isolation
    """

    def __init__(self) -> None:
        self._issues: Dict[str, Dict[str, Any]] = {}
        self._clusters: Dict[str, Dict[str, Any]] = {}

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:12]}"

    @staticmethod
    def _reference_number() -> str:
        return f"GC-{uuid4().hex[:10].upper()}"

    @staticmethod
    def _distance_km(
        first_lat: float,
        first_lon: float,
        second_lat: float,
        second_lon: float,
    ) -> float:
        """
        Haversine distance between two coordinates.
        """

        earth_radius_km = 6371.0

        lat1 = radians(first_lat)
        lat2 = radians(second_lat)

        delta_lat = radians(second_lat - first_lat)
        delta_lon = radians(second_lon - first_lon)

        a = (
            sin(delta_lat / 2) ** 2
            + cos(lat1)
            * cos(lat2)
            * sin(delta_lon / 2) ** 2
        )

        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return earth_radius_km * c

    @staticmethod
    def _tenant_check(
        resource: Optional[Dict[str, Any]],
        tenant_id: str,
    ) -> None:
        if resource is None:
            raise KeyError("Resource not found")

        if resource.get("tenant_id") != tenant_id:
            raise PermissionError(
                "Cross-tenant citizen data access denied"
            )

    @staticmethod
    def _token_similarity(
        first_text: Optional[str],
        second_text: Optional[str],
    ) -> float:
        """
        Lightweight deterministic semantic-similarity approximation.

        This keeps BE-018 functional without requiring an external
        embedding/AI provider.
        """

        if not first_text or not second_text:
            return 0.0

        first_tokens = {
            token.strip(".,!?;:()[]{}").lower()
            for token in first_text.split()
            if token.strip()
        }

        second_tokens = {
            token.strip(".,!?;:()[]{}").lower()
            for token in second_text.split()
            if token.strip()
        }

        if not first_tokens or not second_tokens:
            return 0.0

        intersection = len(first_tokens & second_tokens)
        union = len(first_tokens | second_tokens)

        return intersection / union if union else 0.0

    def _get_issue(
        self,
        *,
        issue_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:

        issue = self._issues.get(issue_id)

        if issue is None:
            raise KeyError("Citizen issue not found")

        if issue["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant citizen issue access denied"
            )

        return issue

    def _get_cluster(
        self,
        *,
        cluster_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:

        cluster = self._clusters.get(cluster_id)

        if cluster is None:
            raise KeyError("Citizen cluster not found")

        if cluster["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant citizen cluster access denied"
            )

        return cluster

    # =========================================================
    # Issue Intake
    # =========================================================

    def create_issue(
        self,
        *,
        request: CitizenIssueCreateRequest,
    ) -> Dict[str, Any]:
        """
        CIT-01:
        Accept text, voice, photo, video and location.

        A voice-only submission is valid.
        """

        if not request.text and not request.media:
            raise ValueError(
                "Issue requires text or at least one media attachment"
            )

        issue_id = self._new_id("issue")
        now = self._now()

        issue = {
            "issue_id": issue_id,
            "reference_number": self._reference_number(),
            "tenant_id": request.tenant_id,
            "citizen_id": request.citizen_id,
            "text": request.text,
            "media": [
                media.model_dump()
                for media in request.media
            ],
            "location": (
                request.location.model_dump()
                if request.location
                else None
            ),
            "consent": request.consent.model_dump(),
            "ai_proposal": None,
            "category": None,
            "priority": None,
            "classification_status": "pending_human_review",
            "cluster_id": None,
            "created_at": now,
            "updated_at": now,
            "history": [
                {
                    "action": "created",
                    "actor": request.citizen_id,
                    "timestamp": now,
                }
            ],
        }

        self._issues[issue_id] = issue

        issue["ai_proposal"] = self._generate_ai_proposal(
            issue
        )

        issue["history"].append(
            {
                "action": "ai_proposal_created",
                "actor": "system",
                "timestamp": self._now(),
            }
        )

        return dict(issue)

    # =========================================================
    # AI Proposal
    # =========================================================

    def _generate_ai_proposal(
        self,
        issue: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Lightweight proposal generator.

        The proposal is NEVER treated as final classification.
        Human confirmation remains mandatory.
        """

        text = str(issue.get("text") or "").lower()

        category = "general"

        category_keywords = {
            "road": [
                "road",
                "pothole",
                "street",
                "traffic",
            ],
            "water": [
                "water",
                "pipeline",
                "leak",
                "supply",
            ],
            "electricity": [
                "electricity",
                "electric",
                "power",
                "transformer",
            ],
            "waste": [
                "garbage",
                "waste",
                "trash",
                "cleaning",
            ],
            "drainage": [
                "drain",
                "drainage",
                "sewer",
            ],
        }

        for candidate, keywords in category_keywords.items():
            if any(keyword in text for keyword in keywords):
                category = candidate
                break

        priority = "normal"

        urgent_keywords = [
            "emergency",
            "danger",
            "accident",
            "fire",
            "flood",
            "life threatening",
        ]

        high_keywords = [
            "urgent",
            "critical",
            "severe",
        ]

        if any(keyword in text for keyword in urgent_keywords):
            priority = "urgent"
        elif any(keyword in text for keyword in high_keywords):
            priority = "high"

        return {
            "category": category,
            "location": issue.get("location"),
            "priority": priority,
            "proposed_at": self._now(),
            "model_version": "deterministic-be018-v1",
            "human_confirmed": False,
        }

    # =========================================================
    # Get Issue
    # =========================================================

    def get_issue(
        self,
        *,
        issue_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:

        issue = self._get_issue(
            issue_id=issue_id,
            tenant_id=tenant_id,
        )

        return dict(issue)

    # =========================================================
    # Human Classification
    # =========================================================

    def classify_issue(
        self,
        *,
        request: CitizenIssueClassificationRequest,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """
        CIT-04:
        Human can correct every AI-proposed classification value.

        AI proposal is never final until this method is called.
        """

        issue = self._get_issue(
            issue_id=request.issue_id,
            tenant_id=tenant_id,
        )

        proposal = issue.get("ai_proposal") or {}

        category = (
            request.category
            if request.category is not None
            else proposal.get("category")
        )

        location = (
            request.location.model_dump()
            if request.location is not None
            else proposal.get("location")
        )

        priority = (
            request.priority
            if request.priority is not None
            else proposal.get("priority")
        )

        if not category:
            raise ValueError(
                "Category is required for human confirmation"
            )

        if not priority:
            raise ValueError(
                "Priority is required for human confirmation"
            )

        now = self._now()

        corrected = (
            category != proposal.get("category")
            or location != proposal.get("location")
            or priority != proposal.get("priority")
        )

        issue["category"] = category
        issue["priority"] = priority
        issue["location"] = location
        issue["classification_status"] = "human_confirmed"

        proposal["human_confirmed"] = True

        issue["history"].append(
            {
                "action": (
                    "ai_classification_corrected"
                    if corrected
                    else "ai_classification_confirmed"
                ),
                "actor": request.corrected_by,
                "timestamp": now,
                "reason": request.reason,
                "previous_proposal": {
                    "category": proposal.get("category"),
                    "location": proposal.get("location"),
                    "priority": proposal.get("priority"),
                },
                "final_classification": {
                    "category": category,
                    "location": location,
                    "priority": priority,
                },
            }
        )

        issue["updated_at"] = now

        return dict(issue)

    # =========================================================
    # Cluster Suggestion
    # =========================================================

    def suggest_clusters(
        self,
        *,
        issue_id: str,
        tenant_id: str,
        proximity_km: float = 1.0,
        similarity_threshold: float = 0.25,
    ) -> List[Dict[str, Any]]:
        """
        CIT-07:
        Suggest clustering using:
        - category
        - geographic proximity
        - semantic/text similarity

        Suggestions do not automatically merge issues.
        """

        issue = self._get_issue(
            issue_id=issue_id,
            tenant_id=tenant_id,
        )

        suggestions: List[Dict[str, Any]] = []

        for candidate in self._issues.values():

            if candidate["issue_id"] == issue_id:
                continue

            if candidate["tenant_id"] != tenant_id:
                continue

            if (
                issue.get("category")
                and candidate.get("category")
                and issue["category"] != candidate["category"]
            ):
                continue

            issue_location = issue.get("location")
            candidate_location = candidate.get("location")

            if issue_location and candidate_location:
                distance = self._distance_km(
                    issue_location["latitude"],
                    issue_location["longitude"],
                    candidate_location["latitude"],
                    candidate_location["longitude"],
                )

                if distance > proximity_km:
                    continue
            else:
                distance = None

            similarity = self._token_similarity(
                issue.get("text"),
                candidate.get("text"),
            )

            if (
                similarity < similarity_threshold
                and distance is not None
                and distance > proximity_km / 2
            ):
                continue

            suggestions.append(
                {
                    "issue_id": candidate["issue_id"],
                    "reference_number": candidate[
                        "reference_number"
                    ],
                    "category": candidate.get("category"),
                    "distance_km": distance,
                    "semantic_similarity": similarity,
                }
            )

        return suggestions

    # =========================================================
    # Create / Confirm Cluster
    # =========================================================

    def confirm_cluster(
        self,
        *,
        request: ClusterConfirmRequest,
        tenant_id: str,
    ) -> Dict[str, Any]:

        cluster = self._get_cluster(
            cluster_id=request.cluster_id,
            tenant_id=tenant_id,
        )

        cluster["clustering_status"] = "human_confirmed"

        now = self._now()

        cluster["history"].append(
            {
                "action": "cluster_confirmed",
                "actor": request.confirmed_by,
                "timestamp": now,
            }
        )

        cluster["updated_at"] = now

        return dict(cluster)

    def create_cluster(
        self,
        *,
        issue_id: str,
        tenant_id: str,
        created_by: str,
        issue_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a canonical cluster after human/system selection.

        All selected issues are retained in the canonical cluster.
        Their citizens are automatically registered as corroborators.
        """

        issue = self._get_issue(
            issue_id=issue_id,
            tenant_id=tenant_id,
        )

        selected_issue_ids = list(
            dict.fromkeys(
                [issue_id] + list(issue_ids or [])
            )
        )

        selected_issues: List[Dict[str, Any]] = []

        for selected_id in selected_issue_ids:
            selected_issues.append(
                self._get_issue(
                    issue_id=selected_id,
                    tenant_id=tenant_id,
                )
            )

        cluster_id = self._new_id("cluster")
        now = self._now()

        cluster = {
            "cluster_id": cluster_id,
            "tenant_id": tenant_id,
            "canonical_issue_id": issue_id,
            "category": issue.get("category"),
            "location": issue.get("location"),
            "issue_ids": selected_issue_ids,
            "corroborators": [],
            "corroboration_count": 0,
            "distinct_citizen_count": 0,
            "clustering_status": "suggested",
            "created_at": now,
            "updated_at": now,
            "history": [
                {
                    "action": "cluster_created",
                    "actor": created_by,
                    "timestamp": now,
                    "issue_ids": list(selected_issue_ids),
                }
            ],
        }

        self._clusters[cluster_id] = cluster

        for selected_issue in selected_issues:
            selected_issue["cluster_id"] = cluster_id
            selected_issue["updated_at"] = now

        # Automatically register each selected citizen as a
        # corroborator for their corresponding issue.
        for selected_issue in selected_issues:
            self._add_corroboration_record(
                cluster=cluster,
                issue=selected_issue,
                citizen_id=selected_issue["citizen_id"],
                timestamp=now,
            )

        self._recalculate_corroboration(cluster)

        return dict(cluster)

    # =========================================================
    # Corroboration
    # =========================================================

    def _add_corroboration_record(
        self,
        *,
        cluster: Dict[str, Any],
        issue: Dict[str, Any],
        citizen_id: str,
        timestamp: datetime,
    ) -> bool:
        """
        Add one corroboration record.

        Returns:
            True  -> new record added
            False -> duplicate record already existed
        """

        existing = next(
            (
                item
                for item in cluster["corroborators"]
                if item["issue_id"] == issue["issue_id"]
                and item["citizen_id"] == citizen_id
            ),
            None,
        )

        if existing is not None:
            return False

        cluster["corroborators"].append(
            {
                "citizen_id": citizen_id,
                "issue_id": issue["issue_id"],
                "status": "reported",
                "notifications_enabled": True,
                "closure_confirmation": None,
                "added_at": timestamp,
            }
        )

        return True

    def add_corroboration(
        self,
        *,
        cluster_id: str,
        issue_id: str,
        citizen_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """
        Register a citizen's corroboration.

        The same citizen cannot be registered twice for the
        same issue.

        Multiple issues from the same citizen may exist, but
        distinct_citizen_count counts that citizen only once.
        """

        cluster = self._get_cluster(
            cluster_id=cluster_id,
            tenant_id=tenant_id,
        )

        issue = self._get_issue(
            issue_id=issue_id,
            tenant_id=tenant_id,
        )

        if issue["cluster_id"] != cluster_id:
            raise ValueError(
                "Issue does not belong to this cluster"
            )

        # Keep the corroborating citizen consistent with the
        # actual issue owner. This prevents one citizen from
        # claiming another citizen's issue.
        if issue["citizen_id"] != citizen_id:
            raise PermissionError(
                "Citizen can only corroborate their own issue"
            )

        now = self._now()

        self._add_corroboration_record(
            cluster=cluster,
            issue=issue,
            citizen_id=citizen_id,
            timestamp=now,
        )

        self._recalculate_corroboration(cluster)

        cluster["updated_at"] = now

        cluster["history"].append(
            {
                "action": "corroboration_added",
                "actor": citizen_id,
                "timestamp": now,
                "issue_id": issue_id,
            }
        )

        return dict(cluster)

    def _recalculate_corroboration(
        self,
        cluster: Dict[str, Any],
    ) -> None:

        corroborators = cluster.get(
            "corroborators",
            [],
        )

        cluster["corroboration_count"] = len(
            corroborators
        )

        cluster["distinct_citizen_count"] = len(
            {
                item["citizen_id"]
                for item in corroborators
            }
        )

    # =========================================================
    # Cluster Split
    # =========================================================

    def split_cluster(
        self,
        *,
        request: ClusterSplitRequest,
        tenant_id: str,
    ) -> Dict[str, Any]:

        cluster = self._get_cluster(
            cluster_id=request.cluster_id,
            tenant_id=tenant_id,
        )

        selected_issue_ids = set(request.issue_ids)

        if not selected_issue_ids.issubset(
            set(cluster["issue_ids"])
        ):
            raise ValueError(
                "Split issue list contains an issue "
                "outside the cluster"
            )

        if len(selected_issue_ids) == len(
            cluster["issue_ids"]
        ):
            raise ValueError(
                "At least one issue must remain in the original cluster"
            )

        now = self._now()

        cluster["issue_ids"] = [
            issue_id
            for issue_id in cluster["issue_ids"]
            if issue_id not in selected_issue_ids
        ]

        # Remove corroboration records belonging to
        # issues moved out of this cluster.
        cluster["corroborators"] = [
            item
            for item in cluster["corroborators"]
            if item["issue_id"] not in selected_issue_ids
        ]

        for issue_id in selected_issue_ids:
            self._issues[issue_id]["cluster_id"] = None
            self._issues[issue_id]["updated_at"] = now

        cluster["history"].append(
            {
                "action": "cluster_split",
                "actor": request.requested_by,
                "timestamp": now,
                "removed_issue_ids": list(
                    selected_issue_ids
                ),
                "reason": request.reason,
            }
        )

        self._recalculate_corroboration(cluster)

        cluster["updated_at"] = now

        return dict(cluster)

    # =========================================================
    # Cluster Merge
    # =========================================================

    def merge_clusters(
        self,
        *,
        request: ClusterMergeRequest,
        tenant_id: str,
    ) -> Dict[str, Any]:

        source = self._get_cluster(
            cluster_id=request.cluster_id,
            tenant_id=tenant_id,
        )

        target = self._get_cluster(
            cluster_id=request.target_cluster_id,
            tenant_id=tenant_id,
        )

        if source["cluster_id"] == target["cluster_id"]:
            raise ValueError(
                "Cannot merge a cluster with itself"
            )

        now = self._now()

        target_issue_ids = list(
            dict.fromkeys(
                target["issue_ids"]
                + source["issue_ids"]
            )
        )

        target["issue_ids"] = target_issue_ids

        # Merge corroboration records without creating
        # duplicate citizen + issue combinations.
        for source_record in source.get(
            "corroborators",
            [],
        ):
            existing = next(
                (
                    item
                    for item in target["corroborators"]
                    if item["citizen_id"]
                    == source_record["citizen_id"]
                    and item["issue_id"]
                    == source_record["issue_id"]
                ),
                None,
            )

            if existing is None:
                target["corroborators"].append(
                    dict(source_record)
                )

        self._recalculate_corroboration(target)

        for issue_id in target_issue_ids:
            self._issues[issue_id]["cluster_id"] = (
                target["cluster_id"]
            )
            self._issues[issue_id]["updated_at"] = now

        target["history"].append(
            {
                "action": "cluster_merged",
                "actor": request.requested_by,
                "timestamp": now,
                "source_cluster_id": source["cluster_id"],
                "source_history": list(
                    source.get("history", [])
                ),
                "reason": request.reason,
            }
        )

        target["updated_at"] = now

        source["clustering_status"] = "merged"
        source["merged_into"] = target["cluster_id"]
        source["updated_at"] = now

        source["history"].append(
            {
                "action": "merged_into_cluster",
                "actor": request.requested_by,
                "timestamp": now,
                "target_cluster_id": target["cluster_id"],
                "reason": request.reason,
            }
        )

        return dict(target)

    # =========================================================
    # Cluster Lookup
    # =========================================================

    def get_cluster(
        self,
        *,
        cluster_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:

        cluster = self._get_cluster(
            cluster_id=cluster_id,
            tenant_id=tenant_id,
        )

        return dict(cluster)

    # =========================================================
    # List Issues
    # =========================================================

    def list_issues(
        self,
        *,
        tenant_id: str,
    ) -> List[Dict[str, Any]]:

        return [
            dict(issue)
            for issue in self._issues.values()
            if issue["tenant_id"] == tenant_id
        ]

    # =========================================================
    # List Clusters
    # =========================================================

    def list_clusters(
        self,
        *,
        tenant_id: str,
    ) -> List[Dict[str, Any]]:

        return [
            dict(cluster)
            for cluster in self._clusters.values()
            if cluster["tenant_id"] == tenant_id
        ]


# =============================================================
# Singleton Service
# =============================================================

citizen_service = CitizenService()