from dataclasses import dataclass

import httpx

from app.core.config import settings

DEEPSEEK_SYSTEM_PROMPT = """你是高翠AI，专业翡翠找货助手。
请用简洁、自然的中文回复用户。
如果用户在咨询翡翠需求，请围绕预算、品类、尺寸、品相、用途继续追问或分析。
如果用户的问题和翡翠无关，请礼貌说明你主要帮助找翡翠，并给出可询问示例。
当前阶段不要承诺已经找到具体商品，也不要输出商品卡片。"""

DEEPSEEK_ERROR_REPLY = "AI服务暂时不可用，请稍后再试。"
DEEPSEEK_BALANCE_ERROR_REPLY = "DeepSeek 账户余额不足，请充值后再试。"


@dataclass(frozen=True)
class JadeAgentResult:
    content: str
    matched_products: None = None


class JadeAgent:
    async def reply(self, content: str, history: list[dict[str, str]]) -> JadeAgentResult:
        # 商品匹配暂时关闭；DeepSeek 只负责聊天文本，后续再在这里接商品召回。
        if not settings.deepseek_api_key.strip():
            return JadeAgentResult(content="DeepSeek API Key 未配置，请先在后端环境文件中填写。")

        messages = [{"role": "system", "content": DEEPSEEK_SYSTEM_PROMPT}, *history]
        if not history or history[-1]["role"] != "user" or history[-1]["content"] != content:
            messages.append({"role": "user", "content": content})

        try:
            async with httpx.AsyncClient(timeout=40) as client:
                response = await client.post(
                    f"{settings.deepseek_base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.deepseek_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.deepseek_model,
                        "messages": messages,
                        "thinking": {"type": "disabled"},
                        "stream": False,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 402:
                return JadeAgentResult(content=DEEPSEEK_BALANCE_ERROR_REPLY)
            return JadeAgentResult(content=DEEPSEEK_ERROR_REPLY)
        except httpx.HTTPError:
            return JadeAgentResult(content=DEEPSEEK_ERROR_REPLY)

        data = response.json()
        reply = data["choices"][0]["message"]["content"].strip()
        return JadeAgentResult(content=reply or DEEPSEEK_ERROR_REPLY)


jade_agent = JadeAgent()
