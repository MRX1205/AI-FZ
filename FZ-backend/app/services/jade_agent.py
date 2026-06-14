from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

MIMO_SYSTEM_PROMPT = """你是高翠AI，专业翡翠找货助手。
请用简洁、自然的中文回复用户。
如果用户在咨询翡翠需求，请围绕预算、品类、尺寸、品相、用途继续追问或分析。
如果用户的问题和翡翠无关，请礼貌说明你主要帮助找翡翠，并给出可询问示例。
当前阶段不要承诺已经找到具体商品，也不要输出商品卡片。"""

MIMO_ERROR_REPLY = "AI服务暂时不可用，请稍后再试。"


class MimoCompletionError(Exception):
    pass


@dataclass(frozen=True)
class JadeAgentResult:
    content: str
    matched_products: None = None


class JadeAgent:
    async def reply(self, content: str, history: list[dict[str, str]]) -> JadeAgentResult:
        return await self.reply_text(content, history)

    async def reply_text(self, content: str, history: list[dict[str, str]]) -> JadeAgentResult:
        if not settings.mimo_api_key.strip():
            return JadeAgentResult(content="MiMo API Key 未配置，请先在后端环境文件中填写。")

        messages = [{"role": "system", "content": MIMO_SYSTEM_PROMPT}, *history]
        if not history or history[-1]["role"] != "user" or history[-1]["content"] != content:
            messages.append({"role": "user", "content": content})

        reply = await self._chat_completion(messages)
        return JadeAgentResult(content=reply or MIMO_ERROR_REPLY)

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        raise_on_error: bool = False,
    ) -> str:
        return await self._chat_completion(messages, raise_on_error=raise_on_error)

    async def _chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        raise_on_error: bool = False,
    ) -> str:
        api_key = settings.mimo_api_key.strip()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{settings.mimo_base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.mimo_model,
                        "messages": messages,
                        "thinking": {"type": "disabled"},
                        "stream": False,
                        "max_completion_tokens": 1024,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as error:
            if raise_on_error:
                raise MimoCompletionError(self._error_detail(error.response)) from error
            return MIMO_ERROR_REPLY
        except httpx.HTTPError as error:
            if raise_on_error:
                raise MimoCompletionError("AI服务连接失败，请稍后再试") from error
            return MIMO_ERROR_REPLY

        try:
            data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content") or message.get("reasoning_content")
        except (KeyError, IndexError, TypeError, ValueError) as error:
            if raise_on_error:
                raise MimoCompletionError("MiMo返回格式错误") from error
            return MIMO_ERROR_REPLY

        return str(content).strip()

    def _error_detail(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return f"MiMo调用失败：HTTP {response.status_code}"

        error = data.get("error") if isinstance(data, dict) else None
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return f"MiMo调用失败：{message.strip()}"
        if isinstance(error, str) and error.strip():
            return f"MiMo调用失败：{error.strip()}"
        detail = data.get("detail") if isinstance(data, dict) else None
        if isinstance(detail, str) and detail.strip():
            return f"MiMo调用失败：{detail.strip()}"
        message = data.get("message") if isinstance(data, dict) else None
        if isinstance(message, str) and message.strip():
            return f"MiMo调用失败：{message.strip()}"
        return f"MiMo调用失败：HTTP {response.status_code}"


jade_agent = JadeAgent()
