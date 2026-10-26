from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from app.core.config import settings
import app.repositories.citizen_repository as repository_module


def test_citizen_submission_persists_in_postgres(monkeypatch):
    assert settings.database_url, "DATABASE_URL is not configured"

    # Explicitly target only the isolated test database.
    parsed = urlsplit(settings.database_url)
    current_db = parsed.path.lstrip("/")

    assert current_db == "groundconnect_test", (
    "Integration test must use groundconnect_test only."
    )

    test_url = urlunsplit(
        parsed._replace(path="/groundconnect_test")
    )

    tenant_slug = f"it-test-{uuid4().hex}"
    now = datetime.now(timezone.utc)

    with psycopg.connect(test_url) as connection:
        try:
            tenant = connection.execute(
                """
                INSERT INTO tenant_and_configuration.tenants (slug, name)
                VALUES (%s, %s)
                RETURNING id
                """,
                (tenant_slug, "Integration Test Tenant"),
            ).fetchone()

            assert tenant is not None
            tenant_id = tenant[0]

            connection.execute(
                """
                INSERT INTO consent_privacy_erasure.privacy_notices (
                    organization_id, version, language, content, effective_from
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    "it-test-v1",
                    "en",
                    "TEST ONLY - not a production privacy notice.",
                    now - timedelta(days=1),
                ),
            )

            @contextmanager
            def shared_connection():
                # Reuse the outer transaction; repository transactions
                # become nested savepoints.
                yield connection

            monkeypatch.setattr(
                repository_module, "get_db_connection", shared_connection
            )

            result = repository_module.citizen_repository.create_submission(
                tenant_id=tenant_slug,
                citizen_id="integration-test-citizen",
                text="PostgreSQL integration test submission",
                media=[],
                consent={
                    "purpose": "grievance_resolution",
                    "privacy_notice_version": "it-test-v1",
                    "language": "en",
                    "timestamp": now,
                    "mechanism": "in_app_tap",
                },
            )

            assert result["organization_id"] == tenant_id
            assert result["text"] == "PostgreSQL integration test submission"
            assert result["ref_number"].startswith("GC-")
            assert result["consent_receipt_id"] is not None

        finally:
            # Undo the tenant, notice, receipt, and submission together.
            connection.rollback()
