from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMUnavailable(RuntimeError):
    pass


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        raise NotImplementedError

    async def classify_intent(self, message: str, context: dict[str, Any]) -> dict[str, Any]:
        system_prompt = (
            "You classify GhostWriter AI chat intent. Return compact JSON only. "
            "Allowed intents: general_chat, find_new_trends, refresh_trends, show_current_trends, "
            "create_content_plan, edit_content_plan, generate_posts, regenerate_post, edit_post, "
            "edit_profile, edit_audience_profile, change_tone, update_platforms, explain_profile, "
            "explain_trend, content_plan_analytics, recommendations. Include params when useful."
        )
        prompt = f"Message: {message}\nContext keys: {list(context.keys())}\nReturn JSON with intent, confidence, params."
        text = await self.generate_text(prompt, system_prompt=system_prompt)
        return {"raw": text}

    async def rewrite_text(self, text: str, instruction: str, context: dict[str, Any] | None = None) -> str:
        prompt = f"Instruction: {instruction}\nContext: {context or {}}\nText:\n{text}"
        return await self.generate_text(prompt)
