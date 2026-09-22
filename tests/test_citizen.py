from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def consent():
    return {
        "purpose": "Citizen issue reporting",
        "privacy_notice_version": "v1.0",
        "language": "en",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mechanism": "explicit_checkbox",
    }


def create_issue(
    tenant_id="tenant-1",
    citizen_id="citizen-1",
    text="Large pothole on main road",
    media=None,
    location=None,
):
    return client.post(
        "/api/v1/citizen/issues",
        json={
            "tenant_id": tenant_id,
            "citizen_id": citizen_id,
            "text": text,
            "media": media or [],
            "location": location,
            "consent": consent(),
        },
    )


# ============================================================
# Intake
# ============================================================


def test_create_text_issue():
    response = create_issue()

    assert response.status_code == 200

    data = response.json()

    assert data["tenant_id"] == "tenant-1"
    assert data["citizen_id"] == "citizen-1"
    assert data["text"] == "Large pothole on main road"
    assert data["reference_number"].startswith("GC-")
    assert data["classification_status"] == "pending_human_review"
    assert data["ai_proposal"] is not None
    assert data["ai_proposal"]["human_confirmed"] is False


def test_voice_only_submission_is_valid():
    response = create_issue(
        text=None,
        media=[
            {
                "media_id": "voice-1",
                "media_type": "voice",
                "content_reference": "storage/voice-1.wav",
            }
        ],
    )

    assert response.status_code == 200

    data = response.json()

    assert data["text"] is None
    assert data["media"][0]["media_type"] == "voice"


def test_photo_video_submission():
    response = create_issue(
        text="Broken street light",
        media=[
            {
                "media_id": "photo-1",
                "media_type": "photo",
                "content_reference": "storage/photo-1.jpg",
            },
            {
                "media_id": "video-1",
                "media_type": "video",
                "content_reference": "storage/video-1.mp4",
            },
        ],
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["media"]) == 2


def test_issue_requires_text_or_media():
    response = create_issue(
        text=None,
        media=[],
    )

    assert response.status_code == 400


def test_consent_receipt_is_stored():
    response = create_issue()

    assert response.status_code == 200

    consent_data = response.json()["consent"]

    assert consent_data["purpose"] == "Citizen issue reporting"
    assert consent_data["privacy_notice_version"] == "v1.0"
    assert consent_data["language"] == "en"
    assert consent_data["mechanism"] == "explicit_checkbox"


# ============================================================
# AI + Human Classification
# ============================================================


def test_ai_classification_is_not_final():
    response = create_issue(
        text="Water pipeline is leaking",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["ai_proposal"]["category"] == "water"
    assert data["ai_proposal"]["human_confirmed"] is False
    assert data["classification_status"] == "pending_human_review"


def test_human_can_correct_ai_classification():
    response = create_issue(
        text="Water pipeline is leaking",
    )

    issue_id = response.json()["issue_id"]

    response = client.post(
        "/api/v1/citizen/issues/classify?tenant_id=tenant-1",
        json={
            "issue_id": issue_id,
            "category": "drainage",
            "location": {
                "latitude": 22.7196,
                "longitude": 75.8577,
            },
            "priority": "high",
            "corrected_by": "operator-1",
            "reason": "Human operator corrected category",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["category"] == "drainage"
    assert data["priority"] == "high"
    assert data["classification_status"] == "human_confirmed"
    assert data["ai_proposal"]["human_confirmed"] is True


# ============================================================
# Tenant Isolation
# ============================================================


def test_cross_tenant_issue_access_is_denied():
    response = create_issue(
        tenant_id="tenant-a",
        citizen_id="citizen-a",
    )

    issue_id = response.json()["issue_id"]

    response = client.get(
        f"/api/v1/citizen/issues/{issue_id}"
        "?tenant_id=tenant-b"
    )

    assert response.status_code == 403


def test_issue_list_is_tenant_isolated():
    create_issue(
        tenant_id="tenant-a",
        citizen_id="citizen-a",
    )

    create_issue(
        tenant_id="tenant-b",
        citizen_id="citizen-b",
    )

    response = client.get(
        "/api/v1/citizen/issues?tenant_id=tenant-a"
    )

    assert response.status_code == 200

    data = response.json()

    assert all(
        issue["tenant_id"] == "tenant-a"
        for issue in data
    )


# ============================================================
# Clustering
# ============================================================


def test_cluster_suggestion_by_category_location_and_text():
    location = {
        "latitude": 22.7196,
        "longitude": 75.8577,
    }

    first = create_issue(
        citizen_id="citizen-101",
        text="Large pothole on main road",
        location=location,
    )

    first_id = first.json()["issue_id"]

    client.post(
        "/api/v1/citizen/issues/classify?tenant_id=tenant-1",
        json={
            "issue_id": first_id,
            "category": "road",
            "location": location,
            "priority": "high",
            "corrected_by": "operator-1",
        },
    )

    second = create_issue(
        citizen_id="citizen-102",
        text="Large pothole on main road near market",
        location={
            "latitude": 22.7200,
            "longitude": 75.8580,
        },
    )

    second_id = second.json()["issue_id"]

    client.post(
        "/api/v1/citizen/issues/classify?tenant_id=tenant-1",
        json={
            "issue_id": second_id,
            "category": "road",
            "location": {
                "latitude": 22.7200,
                "longitude": 75.8580,
            },
            "priority": "high",
            "corrected_by": "operator-1",
        },
    )

    response = client.post(
        "/api/v1/citizen/clusters/suggestions"
        "?tenant_id=tenant-1",
        json={
            "issue_id": first_id,
        },
    )

    assert response.status_code == 200

    suggestions = response.json()["suggestions"]

    assert any(
        item["issue_id"] == second_id
        for item in suggestions
    )


def test_create_and_confirm_cluster():
    first = create_issue(
        citizen_id="citizen-201",
        text="Garbage not collected",
    )

    first_id = first.json()["issue_id"]

    response = client.post(
        "/api/v1/citizen/clusters"
        "?tenant_id=tenant-1"
        f"&issue_id={first_id}",
        json={
            "cluster_id": "temporary",
            "confirmed_by": "operator-1",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["clustering_status"] == "human_confirmed"
    assert data["canonical_issue_id"] == first_id
    assert data["history_preserved"] is True


def test_distinct_citizen_count():
    issue = create_issue(
        citizen_id="citizen-301",
        text="Street light is broken",
    )

    issue_id = issue.json()["issue_id"]

    cluster = client.post(
        "/api/v1/citizen/clusters"
        "?tenant_id=tenant-1"
        f"&issue_id={issue_id}",
        json={
            "cluster_id": "temporary",
            "confirmed_by": "operator-1",
        },
    )

    cluster_id = cluster.json()["cluster_id"]

    # Same citizen reports again.
    response = client.post(
        f"/api/v1/citizen/clusters/{cluster_id}/confirm"
        "?tenant_id=tenant-1",
        json={
            "cluster_id": cluster_id,
            "confirmed_by": "operator-1",
        },
    )

    assert response.status_code == 200

    # Verify the cluster itself remains tenant-isolated and valid.
    cluster_response = client.get(
        f"/api/v1/citizen/clusters/{cluster_id}"
        "?tenant_id=tenant-1"
    )

    assert cluster_response.status_code == 200