import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.core.config import settings


class AlipayNotConfiguredError(RuntimeError):
    pass


class AlipayError(RuntimeError):
    pass


class AlipayVerificationError(AlipayError):
    pass


@dataclass(slots=True)
class AlipayTradeQueryResult:
    status: str
    trade_status: str | None = None
    trade_no: str | None = None
    total_amount: str | None = None


@dataclass(slots=True)
class AlipayNotification:
    app_id: str
    out_trade_no: str
    trade_no: str
    trade_status: str
    total_amount: str
    seller_id: str | None
    notify_time: datetime | None


class AlipayClient:
    def _require(self, value: str, message: str) -> str:
        if not value.strip():
            raise AlipayNotConfiguredError(message)
        return value.strip()

    def _gateway_url(self) -> str:
        return self._require(settings.alipay_gateway_url, "支付宝支付网关未配置")

    def _app_id(self) -> str:
        return self._require(settings.alipay_app_id, "支付宝应用未配置")

    def _private_key_bytes(self) -> bytes:
        key_path = Path(self._require(settings.alipay_app_private_key_path, "支付宝应用私钥未配置"))
        return key_path.read_bytes()

    def _alipay_public_key_bytes(self) -> bytes:
        key_path = Path(
            self._require(settings.alipay_alipay_public_key_path, "支付宝公钥未配置")
        )
        return key_path.read_bytes()

    def _private_key(self):
        try:
            return serialization.load_pem_private_key(self._private_key_bytes(), password=None)
        except FileNotFoundError as error:
            raise AlipayNotConfiguredError("支付宝应用私钥文件不存在") from error
        except ValueError as error:
            raise AlipayNotConfiguredError("支付宝应用私钥文件格式错误") from error

    def _alipay_public_key(self):
        try:
            return serialization.load_pem_public_key(self._alipay_public_key_bytes())
        except FileNotFoundError as error:
            raise AlipayNotConfiguredError("支付宝公钥文件不存在") from error
        except ValueError as error:
            raise AlipayNotConfiguredError("支付宝公钥文件格式错误") from error

    def _sign(self, content: str) -> str:
        signature = self._private_key().sign(
            content.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def _verify(self, content: str, signature: str) -> bool:
        try:
            self._alipay_public_key().verify(
                base64.b64decode(signature),
                content.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except Exception:
            return False
        return True

    def _signed_content(self, params: Mapping[str, str]) -> str:
        parts = []
        for key in sorted(params):
            value = params[key]
            if value == "":
                continue
            parts.append(f"{key}={value}")
        return "&".join(parts)

    def _signed_params(
        self,
        method: str,
        biz_content: Mapping[str, str],
        *,
        notify_url: str | None = None,
        return_url: str | None = None,
    ) -> dict[str, str]:
        params = {
            "app_id": self._app_id(),
            "method": method,
            "charset": "utf-8",
            "sign_type": "RSA2",
            "timestamp": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "biz_content": json.dumps(biz_content, ensure_ascii=False, separators=(",", ":")),
        }
        if notify_url:
            params["notify_url"] = notify_url
        if return_url:
            params["return_url"] = return_url

        params["sign"] = self._sign(self._signed_content(params))
        return params

    def _pay_url(
        self,
        method: str,
        biz_content: Mapping[str, str],
        *,
        notify_url: str,
        return_url: str,
    ) -> str:
        params = self._signed_params(
            method,
            biz_content,
            notify_url=notify_url,
            return_url=return_url,
        )
        return f"{self._gateway_url()}?{urlencode(params)}"

    async def create_page_pay_url(
        self,
        *,
        order_no: str,
        amount_yuan: str,
        subject: str,
        notify_url: str,
        return_url: str,
    ) -> str:
        return self._pay_url(
            "alipay.trade.page.pay",
            {
                "out_trade_no": order_no,
                "product_code": "FAST_INSTANT_TRADE_PAY",
                "total_amount": amount_yuan,
                "subject": subject,
                "timeout_express": settings.alipay_timeout_express,
            },
            notify_url=notify_url,
            return_url=return_url,
        )

    async def create_wap_pay_url(
        self,
        *,
        order_no: str,
        amount_yuan: str,
        subject: str,
        notify_url: str,
        return_url: str,
    ) -> str:
        return self._pay_url(
            "alipay.trade.wap.pay",
            {
                "out_trade_no": order_no,
                "product_code": "QUICK_WAP_WAY",
                "total_amount": amount_yuan,
                "subject": subject,
                "timeout_express": settings.alipay_timeout_express,
            },
            notify_url=notify_url,
            return_url=return_url,
        )

    async def query_trade(self, *, order_no: str) -> AlipayTradeQueryResult:
        params = self._signed_params(
            "alipay.trade.query",
            {
                "out_trade_no": order_no,
            },
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self._gateway_url(), data=params)
            response.raise_for_status()
            payload = response.json()
        except AlipayNotConfiguredError:
            raise
        except httpx.HTTPError as error:
            raise AlipayError("支付宝查单失败，请稍后重试") from error
        except ValueError as error:
            raise AlipayError("支付宝查单返回异常") from error

        body = payload.get("alipay_trade_query_response") or {}
        code = str(body.get("code") or "")
        if code == "10000":
            return AlipayTradeQueryResult(
                status="success",
                trade_status=body.get("trade_status"),
                trade_no=body.get("trade_no"),
                total_amount=body.get("total_amount"),
            )
        if body.get("sub_code") == "ACQ.TRADE_NOT_EXIST":
            return AlipayTradeQueryResult(status="not_found")
        raise AlipayError(body.get("sub_msg") or "支付宝查单失败，请稍后重试")

    def verify_notification(self, raw_params: Mapping[str, str]) -> AlipayNotification:
        params = {key: str(value) for key, value in raw_params.items()}
        signature = params.pop("sign", "")
        params.pop("sign_type", None)
        if not signature or not self._verify(self._signed_content(params), signature):
            raise AlipayVerificationError("支付宝通知验签失败")
        notify_time_raw = params.get("notify_time")
        notify_time = None
        if notify_time_raw:
            try:
                notify_time = datetime.strptime(
                    notify_time_raw,
                    "%Y-%m-%d %H:%M:%S",
                ).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
            except ValueError:
                notify_time = None
        return AlipayNotification(
            app_id=params.get("app_id", ""),
            out_trade_no=params.get("out_trade_no", ""),
            trade_no=params.get("trade_no", ""),
            trade_status=params.get("trade_status", ""),
            total_amount=params.get("total_amount", ""),
            seller_id=params.get("seller_id"),
            notify_time=notify_time,
        )


def append_query_params(url: str, **params: str) -> str:
    parts = urlsplit(url)
    existing = []
    if parts.query:
        existing.append(parts.query)
    encoded = urlencode(params)
    if encoded:
        existing.append(encoded)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "&".join(existing), parts.fragment))


alipay_client = AlipayClient()
