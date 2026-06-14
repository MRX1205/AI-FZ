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


@pytest.fixture(autouse=True)
def fake_supabase_otp(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.supabase_otp import SupabaseOtpInvalidError, supabase_otp_client

    async def send_email_code(email: str) -> None:
        return None

    async def verify_email_code(email: str, code: str) -> None:
        if code != "123456":
            raise SupabaseOtpInvalidError("验证码错误或已过期")

    monkeypatch.setattr(supabase_otp_client, "send_email_code", send_email_code)
    monkeypatch.setattr(supabase_otp_client, "verify_email_code", verify_email_code)
