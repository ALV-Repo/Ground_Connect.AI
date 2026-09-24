from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import auth_service


def create_authenticated_client():
    user_id = "test-user"
    device_id = "test-device"

    # Register test device
    auth_service.register_device(
        user_id=user_id,
        device_id=device_id,
    )

    # Create real session using existing auth service
    session = auth_service.create_session(
        user_id=user_id,
        device_id=device_id,
    )

    if not session["session_created"]:
        raise RuntimeError(
            "Failed to create authenticated test session."
        )

    access_token = session["access_token"]

    return TestClient(
        app,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )