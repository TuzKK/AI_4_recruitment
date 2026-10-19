"""Unified LLM client – wraps OpenAI-compatible APIs."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI, APITimeoutError, APIConnectionError, APIStatusError

load_dotenv()
logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around the OpenAI SDK.

    Supports any OpenAI-compatible endpoint (GPT-4o, DeepSeek, etc.)
    by setting OPENAI_BASE_URL in .env.
    """

    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        # Keep the wrapper identity stable for modules using `from ... import llm`.
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout=60.0,
            max_retries=0,
        )
        self._settings = (client, os.getenv("OPENAI_MODEL", "gpt-4o"))

    @property
    def client(self):
        return self._settings[0]

    @property
    def model(self):
        return self._settings[1]

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Send a single-turn chat and return the assistant message."""
        client, model = self._settings
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        return content.strip()

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Chat and parse the response as JSON.

        The system prompt should instruct the model to reply in JSON.
        """
        raw = self.chat(
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # Strip markdown code fences if present
        cleaned = raw
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last fence lines
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON: %s", raw[:500])
            return {"error": "Invalid JSON from LLM", "raw": raw}


def model_error_message(exc: Exception) -> str:
    if isinstance(exc, APITimeoutError):
        return '模型服务连接或响应超时，请检查网络和模型服务地址后重试；本次未创建岗位或启动招聘任务。'
    if isinstance(exc, APIConnectionError):
        return '无法连接模型服务，请检查网络、代理和模型服务地址。'
    if isinstance(exc, APIStatusError):
        if exc.status_code in (401, 403):
            return '模型 API Key 无效或没有访问权限，请检查系统设置。'
        if exc.status_code == 429:
            return '模型服务额度不足或请求过于频繁，请检查额度并稍后重试。'
        return f'模型服务返回错误（HTTP {exc.status_code}），请检查所选模型与服务配置。'
    return str(exc)


# Singleton
llm = LLMClient()
