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
    "tone": ["тон", "стиль", "tone"],
    "platforms": ["платформ", "соцсет", "platform"],
    "audience": ["аудитор", "audience"],
    "goal": ["цель", "goal"],
    "profession": ["профес", "работ", "job", "profession"],
    "niche": ["ниша", "niche"],
    "avoid": ["избег", "нельзя", "avoid"],
    "user_values": ["ценност", "values"],
}


def _extract_value(message: str) -> str | None:
    match = re.search(r"(?:на|to|as|:)\s*(.+)$", message, flags=re.IGNORECASE)
    return match.group(1).strip(" .") if match else None


def detect_intent(message: str, context: dict[str, Any] | None = None) -> ChatIntent:
    text = message.lower().strip()
    if any(phrase in text for phrase in ["что улучшить", "что работает лучше", "почему такой план", "какие рекомендации", "рекомендации", "what should i improve", "what works better", "why this plan", "recommendations"]):
        return ChatIntent("recommendations")
    if any(phrase in text for phrase in ["сохрани этот вариант", "сохрани пост", "save this post", "save variant"]):
        return ChatIntent("edit_post", params={"action": "save"})
    if any(phrase in text for phrase in ["одобри этот пост", "утверди этот пост", "approve this post"]):
        return ChatIntent("edit_post", params={"status": "approved"})
    if any(phrase in text for phrase in ["отклони этот пост", "reject this post"]):
        return ChatIntent("edit_post", params={"status": "rejected"})
    if any(phrase in text for phrase in ["запланируй позже", "schedule later"]):
        return ChatIntent("edit_post", params={"status": "scheduled"})
    if any(phrase in text for phrase in ["переделай этот пост", "regenerate this post", "rewrite this post"]):
        return ChatIntent("regenerate_post")
    if any(phrase in text for phrase in ["добавь в контент-план", "добавить в контент-план", "add to content plan"]):
        return ChatIntent("create_content_plan", params={"action": "add_trend_to_plan"})
    if any(phrase in text for phrase in ["создай контент-план", "сделай контент-план", "контент-план", "контент план", "план по найденным трендам", "общий план", "content plan"]):
        if any(word in text for word in ["измени", "редакт", "edit"]):
            return ChatIntent("edit_content_plan")
        return ChatIntent("create_content_plan")
    if any(phrase in text for phrase in ["создай пост", "сделай пост", "напиши пост", "пост по этому тренду", "по второму тренду", "по первому тренду", "по третьему тренду", "generate post", "write post"]):
        return ChatIntent("generate_posts")

    if any(word in text for word in ["тренд", "trend"]):
        if any(word in text for word in ["обнов", "refresh", "again"]):
            return ChatIntent("refresh_trends")
        if any(word in text for word in ["найди", "найти", "find", "поиск", "ищи"]):
            return ChatIntent("find_new_trends")
        if any(word in text for word in ["покажи", "show", "current", "текущ"]):
            return ChatIntent("show_current_trends")

    if any(phrase in text for phrase in ["найди новые тренды", "find new trends", "новые тренды"]):
        return ChatIntent("find_new_trends")
    if any(phrase in text for phrase in ["обнови тренды", "refresh trends", "перепроверь тренды"]):
        return ChatIntent("refresh_trends")
    if any(phrase in text for phrase in ["покажи тренды", "show current trends", "текущие тренды"]):
        return ChatIntent("show_current_trends")
    if any(phrase in text for phrase in ["контент-план", "контент план", "content plan", "план на неделю"]):
        if any(word in text for word in ["измени", "редакт", "edit"]):
            return ChatIntent("edit_content_plan")
        return ChatIntent("create_content_plan")
    if any(phrase in text for phrase in ["перегенер", "regenerate"]):
        return ChatIntent("regenerate_post")
    if any(phrase in text for phrase in ["сгенерируй пост", "напиши пост", "сделай пост", "generate post", "write post"]):
        return ChatIntent("generate_posts")
    if any(phrase in text for phrase in ["покажи профиль", "объясни профиль", "explain profile", "что знаешь"]):
        return ChatIntent("explain_profile")
    if any(phrase in text for phrase in ["объясни тренд", "explain trend", "почему тренд"]):
        return ChatIntent("explain_trend")

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
