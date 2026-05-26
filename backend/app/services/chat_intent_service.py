from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatIntent:
    name: str
    confidence: float = 1.0
    params: dict[str, Any] = field(default_factory=dict)


PROFILE_FIELD_PATTERNS = {
    "tone": ["тон", "стиль", "tone", "style"],
    "platforms": ["платформ", "соцсет", "platform", "social"],
    "audience": ["аудитор", "audience"],
    "goal": ["цель", "goal"],
    "profession": ["профес", "работ", "job", "profession"],
    "niche": ["ниша", "niche"],
    "avoid": ["избег", "нельзя", "avoid"],
    "user_values": ["ценност", "values"],
}


def _platform_from_text(text: str) -> str | None:
    normalized = f" {text.lower()} "
    if any(word in normalized for word in ["linkedin", "linked in", "линкедин", "линкедын"]):
        return "LinkedIn"
    if any(word in normalized for word in ["telegram", "телеграм", " tg "]):
        return "Telegram"
    if any(word in normalized for word in ["instagram", "инстаграм"]):
        return "Instagram"
    if any(word in normalized for word in ["twitter", "твиттер", "x/twitter", " x "]):
        return "X"
    return None


def _trend_index_from_text(text: str) -> int | None:
    normalized = text.lower()
    if re.search(r"(?:\bвтор\w*|\b2\b|\bsecond\b)", normalized):
        return 1
    if re.search(r"(?:\bперв\w*|\b1\b|\bfirst\b)", normalized):
        return 0
    if re.search(r"(?:\bтрет\w*|\b3\b|\bthird\b)", normalized):
        return 2
    return None


def _extract_value(message: str) -> str | None:
    match = re.search(r"(?:на|to|as|:|—|-)\s*(.+)$", message, flags=re.IGNORECASE)
    return match.group(1).strip(" .") if match else None


def _with_post_params(platform: str | None, trend_index: int | None) -> ChatIntent:
    params: dict[str, Any] = {}
    if platform:
        params["platform"] = platform
    if trend_index is not None:
        params["trend_index"] = trend_index
    return ChatIntent("generate_posts", params=params)


def detect_intent(message: str, context: dict[str, Any] | None = None) -> ChatIntent:
    text = message.lower().strip()
    platform = _platform_from_text(text)
    trend_index = _trend_index_from_text(text)

    if any(
        phrase in text
        for phrase in [
            "что улучшить",
            "что работает лучше",
            "почему такой план",
            "какие рекомендации",
            "рекомендации",
            "what should i improve",
            "what works better",
            "why this plan",
            "recommendations",
        ]
    ):
        return ChatIntent("recommendations")

    if any(phrase in text for phrase in ["сохрани этот вариант", "сохрани пост", "save this post", "save variant"]):
        return ChatIntent("edit_post", params={"action": "save"})
    if any(phrase in text for phrase in ["одобри этот пост", "утверди этот пост", "approve this post"]):
        return ChatIntent("edit_post", params={"status": "approved"})
    if any(phrase in text for phrase in ["отклони этот пост", "reject this post"]):
        return ChatIntent("edit_post", params={"status": "rejected"})
    if any(phrase in text for phrase in ["запланируй позже", "schedule later"]):
        return ChatIntent("edit_post", params={"status": "scheduled"})

    if any(
        phrase in text
        for phrase in [
            "перегенерируй",
            "переделай",
            "сделай заново",
            "сделай короче",
            "сделай экспертнее",
            "сделай живее",
            "более человечно",
            "усиль начало",
            "сильнее hook",
            "stronger hook",
            "regenerate",
            "regenerate this post",
            "rewrite this post",
            "make it shorter",
            "make it more expert",
        ]
    ):
        return ChatIntent("regenerate_post")

    if any(phrase in text for phrase in ["добавь в контент-план", "добавить в контент-план", "add to content plan"]):
        return ChatIntent("create_content_plan", params={"action": "add_trend_to_plan"})

    if any(
        phrase in text
        for phrase in [
            "создай контент-план",
            "сделай контент-план",
            "контент-план",
            "контент план",
            "план по найденным трендам",
            "общий план",
            "создай план публикаций",
            "сделай план по трендам",
            "content plan",
        ]
    ) or (("сделай" in text or "создай" in text) and "план" in text):
        if any(word in text for word in ["измени", "редакт", "edit"]):
            return ChatIntent("edit_content_plan")
        return ChatIntent("create_content_plan")

    if any(
        phrase in text
        for phrase in [
            "создай пост",
            "сделай пост",
            "напиши пост",
            "сгенерируй пост",
            "пост по этому тренду",
            "по второму тренду",
            "по первому тренду",
            "по третьему тренду",
            "generate post",
            "write post",
        ]
    ) or (platform and ("пост" in text or "post" in text)):
        return _with_post_params(platform, trend_index)

    if "тренд" in text or "trend" in text or "актуальные темы" in text:
        if any(word in text for word in ["обнов", "перепроверь", "refresh", "again"]):
            return ChatIntent("refresh_trends")
        if any(word in text for word in ["найди", "найти", "поищи", "ищи", "поиск", "find", "search"]):
            return ChatIntent("find_new_trends")
        if any(word in text for word in ["покажи", "текущ", "show", "current"]):
            return ChatIntent("show_current_trends")

    if any(phrase in text for phrase in ["найди актуальные темы", "поищи актуальные темы", "find relevant topics"]):
        return ChatIntent("find_new_trends")

    if any(
        phrase in text
        for phrase in [
            "кто я",
            "кто я по профилю",
            "покажи профиль",
            "объясни профиль",
            "что знаешь",
            "что ты знаешь обо мне",
            "explain profile",
        ]
    ):
        return ChatIntent("explain_profile")
    if any(phrase in text for phrase in ["объясни тренд", "почему тренд", "explain trend"]):
        return ChatIntent("explain_trend")

    profile_match = re.search(r"^(моя|мой|мои)\s+(цель|аудитория|ниша|профессия)\s*[-—:]", text)
    if profile_match:
        field_map = {
            "цель": "goal",
            "аудитория": "audience",
            "ниша": "niche",
            "профессия": "profession",
        }
        field = field_map.get(profile_match.group(2))
        name = "edit_audience_profile" if field == "audience" else "edit_profile"
        return ChatIntent(name, params={"field": field, "value": _extract_value(message)})

    if platform and any(phrase in text for phrase in ["платформа", "пиши в", "публикуй в"]):
        return ChatIntent("update_platforms", params={"field": "platforms", "value": platform})

    if "пиши" in text and any(
        word in text for word in ["дружелюб", "эксперт", "человеч", "живее", "официаль", "проще"]
    ):
        return ChatIntent("change_tone", params={"field": "tone", "value": _extract_value(message) or message})

    if any(word in text for word in ["измени", "обнови", "поменяй", "исправь", "change", "update", "set"]):
        for field, aliases in PROFILE_FIELD_PATTERNS.items():
            if any(alias in text for alias in aliases):
                name = {
                    "tone": "change_tone",
                    "platforms": "update_platforms",
                    "audience": "edit_audience_profile",
                }.get(field, "edit_profile")
                return ChatIntent(name, params={"field": field, "value": _extract_value(message)})

    return ChatIntent("general_chat", confidence=0.5)
