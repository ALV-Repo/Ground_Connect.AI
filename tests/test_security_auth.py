from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_protected_endpoint_requires_authentication():
    response = client.post(
        "/api/v1/ai/summarize",
        json={
            "text": "Test authentication",
            "content_type": "general",
        },
    )

    assert response.status_code == 401