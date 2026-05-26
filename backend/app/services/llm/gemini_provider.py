from __future__ import annotations

import asyncio
import logging
from typing import Any

import requests

from app.core.config import settings
from app.services.llm.base import LLMProvider, LLMUnavailable

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def is_available(self) -> bool:
        return bool(settings.gemini_api_key)

    async def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        if not self.is_available():
            raise LLMUnavailable("Gemini API key is not configured")

        def _request() -> str:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
                params={"key": settings.gemini_api_key},
                json={
                    "system_instruction": {"parts": [{"text": system_prompt or "You are GhostWriter AI."}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2},
                },
                timeout=30,
            )
            if response.status_code >= 400:
                logger.warning("Gemini provider failed with status %s", response.status_code)
                raise LLMUnavailable("Gemini provider request failed")
            data: dict[str, Any] = response.json()
            candidates = data.get("candidates") or []
            parts = ((candidates[0] if candidates else {}).get("content") or {}).get("parts") or []
            text = "".join(str(part.get("text") or "") for part in parts).strip()
            if not text:
                raise LLMUnavailable("Gemini returned empty response")
            return text

        try:
            return await asyncio.to_thread(_request)
        except LLMUnavailable:
            raise
        except Exception as exc:
            logger.warning("Gemini provider unavailable: %s", exc.__class__.__name__)
            raise LLMUnavailable("Gemini provider unavailable") from exc
