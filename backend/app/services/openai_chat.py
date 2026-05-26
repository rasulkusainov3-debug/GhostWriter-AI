from __future__ import annotations

import asyncio
from typing import Any

import requests

from app.core.config import settings


class OpenAIChatUnavailable(RuntimeError):
    pass


def _profile_context(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "Профиль клиента пока не создан."
    values = profile.get("user_values") or []
    platforms = profile.get("platforms") or []
    return "\n".join(
        [
            f"Имя: {profile.get('name') or 'не указано'}",
            f"Ниша: {profile.get('niche') or 'не указано'}",
            f"Профессия: {profile.get('profession') or 'не указано'}",
            f"Цель: {profile.get('goal') or 'не указано'}",
            f"Тон: {profile.get('tone') or 'не указано'}",
            f"Аудитория: {profile.get('audience') or 'не указано'}",
            f"Платформы: {', '.join(platforms) if platforms else 'не указано'}",
            f"Ценности: {', '.join(values) if values else 'не указано'}",
            f"Избегать: {profile.get('avoid') or 'не указано'}",
        ]
    )


def _history(messages: list[dict[str, Any]], limit: int = 8) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for message in messages[-limit:]:
        role = "assistant" if message.get("role") == "assistant" else "user"
        text = str(message.get("text") or "").strip()
        if text:
            result.append({"role": role, "content": text[:3000]})
    return result


def _call_openai(message: str, profile: dict[str, Any] | None, history: list[dict[str, Any]]) -> str:
    if not settings.openai_api_key:
        raise OpenAIChatUnavailable("OPENAI_API_KEY is not configured")

    system = (
        "Ты GhostWriter AI, рабочий AI-ассистент для анализа личного бренда, аудитории, "
        "контент-планирования и генерации постов. Отвечай по-русски, если пользователь пишет по-русски. "
        "Используй профиль клиента как источник правды. Не выдумывай сохранение в базу: если действие нужно сохранить, "
        "предложи пользователю команду вроде «создай контент-план» или «напиши пост про ...». "
        "Ты работаешь рядом с существующими агентами social_analyzer: onboarding/profile, planner, post generator. "
        "Давай конкретные вопросы, идеи, правки профиля, структуру постов и рекомендации."
    )
    payload = {
        "model": settings.openai_model,
        "temperature": 0.55,
        "max_tokens": 900,
        "messages": [
            {"role": "system", "content": system},
            {"role": "system", "content": f"Текущий профиль клиента:\n{_profile_context(profile)}"},
            *_history(history),
            {"role": "user", "content": message},
        ],
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=45,
    )
    if response.status_code >= 400:
        raise OpenAIChatUnavailable("OpenAI request failed")
    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        raise OpenAIChatUnavailable("OpenAI returned an empty response")
    return content.strip()


async def answer_with_openai(message: str, profile: dict[str, Any] | None, history: list[dict[str, Any]]) -> str:
    return await asyncio.to_thread(_call_openai, message, profile, history)
