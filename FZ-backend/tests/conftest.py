from urllib.parse import urlparse

import pytest

from app.core.config import settings


def pytest_sessionstart(session: pytest.Session) -> None:
    database_name = urlparse(settings.sync_database_url).path.rsplit("/", 1)[-1]
    if "test" not in database_name.lower():
        raise pytest.UsageError(
            "Refusing to run destructive tests against non-test database. "
            "Set SYNC_DATABASE_URL/DATABASE_URL to a dedicated test database."
        )
