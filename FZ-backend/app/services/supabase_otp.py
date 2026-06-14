import httpx

from app.core.config import settings


class SupabaseOtpNotConfiguredError(RuntimeError):
    pass


class SupabaseOtpError(RuntimeError):
    pass


class SupabaseOtpInvalidError(SupabaseOtpError):
    pass


class SupabaseOtpClient:
    def _auth_url(self, path: str) -> str:
        if not settings.supabase_url or not settings.supabase_anon_key:
            raise SupabaseOtpNotConfiguredError("邮箱验证码服务未配置")
        return f"{settings.supabase_url.rstrip('/')}/auth/v1/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {settings.supabase_anon_key}",
            "Content-Type": "application/json",
        }

    async def send_email_code(self, email: str) -> None:
        payload: dict[str, str | bool] = {"email": email, "create_user": True}
        if settings.supabase_email_redirect_to:
            payload["redirect_to"] = settings.supabase_email_redirect_to

        try:
            async with httpx.AsyncClient(timeout=settings.supabase_auth_timeout_seconds) as client:
                response = await client.post(
                    self._auth_url("otp"),
                    headers=self._headers(),
                    json=payload,
                )
            response.raise_for_status()
        except SupabaseOtpNotConfiguredError:
            raise
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 429:
                raise SupabaseOtpError("验证码发送过于频繁，请稍后再试") from error
            raise SupabaseOtpError("验证码发送失败，请稍后重试") from error
        except httpx.HTTPError as error:
            raise SupabaseOtpError("验证码发送失败，请稍后重试") from error

    async def verify_email_code(self, email: str, code: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=settings.supabase_auth_timeout_seconds) as client:
                response = await client.post(
                    self._auth_url("verify"),
                    headers=self._headers(),
                    json={"email": email, "token": code, "type": "email"},
                )
            response.raise_for_status()
        except SupabaseOtpNotConfiguredError:
            raise
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {400, 404, 410, 422}:
                raise SupabaseOtpInvalidError("验证码错误或已过期") from error
            raise SupabaseOtpError("验证码校验失败，请稍后重试") from error
        except httpx.HTTPError as error:
            raise SupabaseOtpError("验证码校验失败，请稍后重试") from error


supabase_otp_client = SupabaseOtpClient()
