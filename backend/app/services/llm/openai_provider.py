from __future__ import annotations

import asyncio
import logging
from typing import Any

import requests

from app.core.config import settings
from app.services.llm.base import LLMProvider, LLMUnavailable

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def is_available(self) -> bool:
        return bool(settings.openai_api_key)

    async def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        if not self.is_available():
            raise LLMUnavailable("OpenAI API key is not configured")

        def _request() -> str:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openai_model,
                    "messages": [
                        {"role": "system", "content": system_prompt or "You are GhostWriter AI."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
                timeout=30,
            )
            if response.status_code >= 400:
                logger.warning("OpenAI provider failed with status %s", response.status_code)
                raise LLMUnavailable("OpenAI provider request failed")
            data: dict[str, Any] = response.json()
            return str(data["choices"][0]["message"]["content"]).strip()

        try:
            return await asyncio.to_thread(_request)
        except LLMUnavailable:
            raise
        except Exception as exc:
            logger.warning("OpenAI provider unavailable: %s", exc.__class__.__name__)
            raise LLMUnavailable("OpenAI provider unavailable") from exc
