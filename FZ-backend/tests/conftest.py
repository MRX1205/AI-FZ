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


@pytest.fixture(autouse=True)
def fake_alipay(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.alipay import AlipayNotification, AlipayTradeQueryResult, alipay_client

    monkeypatch.setattr(settings, "alipay_app_id", "test-app-id")
    monkeypatch.setattr(settings, "frontend_public_base_url", "https://front.example.com")
    monkeypatch.setattr(settings, "backend_public_base_url", "https://back.example.com")

    async def create_page_pay_url(**kwargs) -> str:
        return f"https://example.com/alipay/page/{kwargs['order_no']}"

    async def create_wap_pay_url(**kwargs) -> str:
        return f"https://example.com/alipay/wap/{kwargs['order_no']}"

    async def query_trade(*, order_no: str) -> AlipayTradeQueryResult:
        return AlipayTradeQueryResult(status="not_found")

    def verify_notification(raw_params: dict[str, str]) -> AlipayNotification:
        return AlipayNotification(
            app_id="test-app-id",
            out_trade_no=raw_params.get("out_trade_no", ""),
            trade_no=raw_params.get("trade_no", "2088TESTTRADE"),
            trade_status=raw_params.get("trade_status", "TRADE_SUCCESS"),
            total_amount=raw_params.get("total_amount", "2999.00"),
            seller_id=raw_params.get("seller_id"),
            notify_time=None,
        )

    monkeypatch.setattr(alipay_client, "create_page_pay_url", create_page_pay_url)
    monkeypatch.setattr(alipay_client, "create_wap_pay_url", create_wap_pay_url)
    monkeypatch.setattr(alipay_client, "query_trade", query_trade)
    monkeypatch.setattr(alipay_client, "verify_notification", verify_notification)
