from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.services.llm.base import LLMProvider, LLMUnavailable
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.groq_provider import GroqProvider
from app.services.llm.ollama_provider import OllamaProvider
from app.services.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

AI_UNAVAILABLE_MESSAGE = "Сейчас AI-модель недоступна. Попробуйте позже или проверьте настройки LLM."


def _provider_map() -> dict[str, LLMProvider]:
    return {
        "openai": OpenAIProvider(),
        "groq": GroqProvider(),
        "gemini": GeminiProvider(),
        "ollama": OllamaProvider(),
    }


def provider_status() -> list[dict[str, Any]]:
    providers = _provider_map()
    return [
        {"id": "openai", "name": "OpenAI", "configured": providers["openai"].is_available(), "local": False, "detail": settings.openai_model},
        {"id": "groq", "name": "Groq", "configured": providers["groq"].is_available(), "local": False, "detail": settings.groq_model},
        {"id": "gemini", "name": "Gemini", "configured": providers["gemini"].is_available(), "local": False, "detail": settings.gemini_model},
        {"id": "ollama", "name": "Ollama", "configured": providers["ollama"].is_available(), "local": True, "detail": settings.ollama_model},
    ]


def _ordered_providers() -> list[LLMProvider]:
    providers = _provider_map()
    primary = (settings.llm_provider or "openai").lower()
    order: list[str] = []
    if primary in providers:
        order.append(primary)
    for name in ("openai", "groq", "gemini", "ollama"):
        if name not in order:
            order.append(name)
    return [providers[name] for name in order]


async def generate_text_with_fallback(prompt: str, system_prompt: str | None = None) -> tuple[str, str]:
    attempted: list[str] = []
    for provider in _ordered_providers():
        try:
            if provider.name in {"openai", "groq", "gemini"} and not provider.is_available():
                continue
            attempted.append(provider.name)
            text = await provider.generate_text(prompt, system_prompt=system_prompt)
            return text, provider.name
        except LLMUnavailable:
            logger.info("LLM provider %s unavailable; trying fallback", provider.name)
    logger.warning("All LLM providers failed. Attempted providers: %s", ", ".join(attempted) or "none")
    raise LLMUnavailable(AI_UNAVAILABLE_MESSAGE)


def parse_json_object(raw: str) -> dict[str, Any] | None:
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                return None
    return None


async def classify_intent_with_fallback(message: str, context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    system_prompt = (
        "You classify GhostWriter AI chat intents. Return JSON only. "
        "Allowed intents: general_chat, find_new_trends, refresh_trends, show_current_trends, "
        "create_content_plan, edit_content_plan, generate_posts, regenerate_post, edit_post, "
        "edit_profile, edit_audience_profile, change_tone, update_platforms, explain_profile, "
        "explain_trend, content_plan_analytics, recommendations. "
        "Use params.field and params.value for profile edits when possible."
    )
    profile = context.get("profile") or {}
    trends = context.get("trends") or []
    prompt = (
        f"Message: {message}\n"
        f"Profile fields: {profile}\n"
        f"Active trend count: {len(trends)}\n"
        "Return compact JSON like {\"intent\":\"find_new_trends\",\"confidence\":0.9,\"params\":{}}."
    )
    text, provider = await generate_text_with_fallback(prompt, system_prompt=system_prompt)
    parsed = parse_json_object(text)
    if not parsed:
        raise LLMUnavailable("Intent classifier returned non-JSON")
    return parsed, provider
