from __future__ import annotations

import asyncio
import logging

import requests

from app.core.config import settings
from app.services.llm.base import LLMProvider, LLMUnavailable

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    name = "ollama"

    @property
    def base_url(self) -> str:
        return (settings.ollama_host or settings.ollama_base_url or "http://localhost:11434").rstrip("/")

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return response.status_code < 400
        except Exception:
            return False

    async def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        def _request() -> str:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "system": system_prompt or "You are GhostWriter AI.",
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=60,
            )
            if response.status_code >= 400:
                logger.warning("Ollama provider failed with status %s", response.status_code)
                raise LLMUnavailable("Ollama provider request failed")
            return str(response.json().get("response") or "").strip()

        try:
            text = await asyncio.to_thread(_request)
            if not text:
                raise LLMUnavailable("Ollama returned empty response")
            return text
        except LLMUnavailable:
            raise
        except Exception as exc:
            logger.warning("Ollama provider unavailable: %s", exc.__class__.__name__)
            raise LLMUnavailable("Ollama provider unavailable") from exc
