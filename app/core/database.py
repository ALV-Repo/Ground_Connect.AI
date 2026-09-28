from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import psycopg

from app.core.config import settings


class DatabaseConfigurationError(RuntimeError):
    """Raised when PostgreSQL configuration is missing or invalid."""


def _get_database_url() -> str:
    """Return the configured PostgreSQL connection URL."""
    if not settings.database_enabled:
        raise DatabaseConfigurationError(
            "PostgreSQL persistence is disabled."
        )

    if not settings.database_url:
        raise DatabaseConfigurationError(
            "DATABASE_URL is required when PostgreSQL persistence is enabled."
        )

    return settings.database_url


@contextmanager
def get_db_connection() -> Generator[psycopg.Connection, None, None]:
    """
    Open a PostgreSQL connection for one operation.

    The caller owns the transaction through the returned connection.
    The connection is always closed when the context exits.
    """
    connection = psycopg.connect(_get_database_url())

    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def check_database_connection() -> bool:
    """Return True when PostgreSQL is reachable."""
    try:
        with get_db_connection() as connection:
            connection.execute("SELECT 1")
        return True
    except Exception:
        return False