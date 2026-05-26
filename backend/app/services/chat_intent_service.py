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
    "platforms": ["платформ", "соцсет", "соцсеть", "platform", "social"],
    "audience": ["аудитор", "audience"],
    "goal": ["цел", "goal"],
    "profession": ["профес", "работ", "job", "profession"],
    "niche": ["ниш", "niche"],
    "avoid": ["избег", "нельзя", "не используй", "убери", "исключи", "avoid"],
    "user_values": ["ценност", "values"],
}

CHANGE_WORDS = [
    "измени",
    "изменить",
    "обнови",
    "обновить",
    "поменяй",
    "поменять",
    "исправь",
    "исправить",
    "запиши",
    "укажи",
    "теперь",
    "change",
    "update",
    "set",
]

PROFILE_FIELD_WORDS = {
    "goal": ["цель", "цели", "целю", "goal"],
    "audience": ["аудитория", "аудиторию", "аудитории", "audience"],
    "niche": ["ниша", "нишу", "ниши", "niche"],
    "profession": ["профессия", "профессию", "профессии", "profession", "job"],
    "tone": ["тон", "стиль", "tone", "style"],
    "platforms": ["платформа", "платформу", "платформы", "соцсеть", "соцсети", "platform"],
    "avoid": ["избегать", "нельзя", "не используй", "убери", "исключи", "avoid"],
    "user_values": ["ценности", "ценность", "values"],
}

PROFILE_DIRECT_RE = re.compile(
    r"^(?:теперь\s+)?(?:моя|мой|мои)\s+"
    r"(?P<field>цель|аудитория|ниша|профессия|тон|стиль|платформа|платформы|соцсеть|соцсети|ценности)"
    r"\s*(?:[-—:]\s*|это\s+)?(?P<value>.+)$",
    flags=re.IGNORECASE,
)


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


def _field_from_text(text: str) -> str | None:
    for field, aliases in PROFILE_FIELD_PATTERNS.items():
        if any(alias in text for alias in aliases):
            return field
    return None


def _field_from_word(word: str) -> str | None:
    lowered = word.lower()
    for field, variants in PROFILE_FIELD_WORDS.items():
        if lowered in variants:
            return field
    return None


def _intent_for_profile_field(field: str) -> str:
    return {
        "tone": "change_tone",
        "platforms": "update_platforms",
        "audience": "edit_audience_profile",
    }.get(field, "edit_profile")


def _clean_profile_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" .,:;—-")
    return cleaned or None


def _tone_value_from_text(text: str) -> str | None:
    if any(word in text for word in ["дружелюб", "теплее", "friendly", "warmer"]):
        return "дружелюбный"
    if any(word in text for word in ["эксперт", "профессиональ", "expert", "professional"]):
        return "экспертный"
    if any(word in text for word in ["живее", "человеч", "human"]):
        return "живой"
    if any(word in text for word in ["официаль", "formal"]):
        return "официальный"
    if any(word in text for word in ["проще", "simple"]):
        return "простой"
    return None


def _extract_profile_value(message: str, field: str, text: str) -> str | None:
    if field == "tone":
        return _tone_value_from_text(text) or _clean_profile_value(_extract_value(message))
    if field == "platforms":
        return _platform_from_text(text) or _clean_profile_value(_extract_value(message))
    if field == "avoid":
        avoid_match = re.search(
            r"(?:убери|исключи|не\s+используй|избегай|нельзя)\s+(.+?)(?:\s+из\s+тем|\s+в\s+темах|\s+в\s+постах|\s*$)",
            message,
            flags=re.IGNORECASE,
        )
        if avoid_match:
            value = _clean_profile_value(avoid_match.group(1))
            return {"политику": "политика"}.get((value or "").lower(), value)
    direct = PROFILE_DIRECT_RE.search(message.strip())
    if direct and _field_from_word(direct.group("field")) == field:
        return _clean_profile_value(direct.group("value"))
    change_match = re.search(
        r"(?:измени|изменить|обнови|обновить|поменяй|поменять|исправь|исправить|запиши|укажи|change|update|set)"
        r".+?\s+(?:на|to|as)\s+(.+)$",
        message,
        flags=re.IGNORECASE,
    )
    if change_match:
        return _clean_profile_value(change_match.group(1))
    return _clean_profile_value(_extract_value(message))


def _style_update_intent(text: str) -> ChatIntent | None:
    if any(phrase in text for phrase in ["пиши дружелюбнее", "пиши теплее", "write friendlier", "warmer voice"]):
        return ChatIntent(
            "update_style",
            params={
                "field": "voice",
                "value": "более дружелюбный тон",
                "confirmation": "Готово, я обновил стиль: более дружелюбный тон.",
            },
        )
    if any(phrase in text for phrase in ["сделай стиль экспертнее", "пиши экспертнее", "more expert style"]):
        return ChatIntent(
            "update_style",
            params={
                "field": "voice",
                "value": "более экспертный, уверенный и практичный тон",
                "confirmation": "Готово, я обновил стиль: более экспертная подача.",
            },
        )
    if any(phrase in text for phrase in ["меньше формально", "менее формально", "less formal"]):
        return ChatIntent(
            "update_style",
            params={
                "field": "writing_style",
                "value": "менее формально, проще, живее и ближе к разговорной подаче",
                "confirmation": "Готово, я обновил стиль: меньше формальности, больше живой подачи.",
            },
        )
    if any(phrase in text for phrase in ["больше кейсов", "more case studies", "more cases"]):
        return ChatIntent(
            "update_style",
            params={
                "field": "preferred_structure",
                "value": ["case", "practical_example"],
                "confirmation": "Готово, я обновил стиль: буду чаще использовать кейсы и практические примеры.",
            },
        )
    if any(phrase in text for phrase in ["пиши как я", "write like me"]):
        return ChatIntent(
            "update_style",
            params={
                "field": "writing_style",
                "value": "ориентироваться на мои утверждённые и отредактированные посты, если есть достаточно примеров",
                "confirmation": "Готово, я обновил стиль: буду ориентироваться на ваши сохранённые удачные посты, когда примеров достаточно.",
            },
        )
    if any(phrase in text for phrase in ["не используй слишком много теории", "меньше теории", "less theory"]):
        return ChatIntent(
            "update_style",
            params={
                "field": "avoid_phrases",
                "value": ["слишком много теории"],
                "confirmation": "Готово, я обновил стиль: буду избегать слишком теоретичной подачи.",
            },
        )
    if any(phrase in text for phrase in ["добавь больше практических примеров", "more practical examples"]):
        return ChatIntent(
            "update_style",
            params={
                "field": "preferred_structure",
                "value": ["practical_example"],
                "confirmation": "Готово, я обновил стиль: добавлю больше практических примеров.",
            },
        )
    return None


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

    style_intent = _style_update_intent(text)
    if style_intent:
        return style_intent

    direct_profile_match = PROFILE_DIRECT_RE.search(message.strip())
    if direct_profile_match:
        field = _field_from_word(direct_profile_match.group("field") or "")
        if field:
            value = _extract_profile_value(message, field, text)
            return ChatIntent(_intent_for_profile_field(field), params={"field": field, "value": value})

    if any(word in text for word in ["убери", "исключи", "не используй", "избегай"]):
        value = _extract_profile_value(message, "avoid", text)
        if value:
            return ChatIntent("edit_profile", params={"field": "avoid", "value": value})

    if "пиши" in text and any(
        word in text for word in ["дружелюб", "эксперт", "человеч", "живее", "официаль", "проще", "теплее"]
    ):
        return ChatIntent("change_tone", params={"field": "tone", "value": _extract_profile_value(message, "tone", text)})

    if platform and any(
        phrase in text
        for phrase in ["добавь", "добавить", "платформа", "платформу", "соцсеть", "соцсети", "пиши в", "публикуй в"]
    ):
        return ChatIntent("update_platforms", params={"field": "platforms", "value": platform})

    if any(word in text for word in CHANGE_WORDS):
        field = _field_from_text(text)
        if field:
            value = _extract_profile_value(message, field, text)
            return ChatIntent(_intent_for_profile_field(field), params={"field": field, "value": value})

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
    ) or (
        any(word in text for word in ["короче", "экспертнее", "живее", "человечнее", "хуком", "hook"])
        and any(word in text for word in ["пост", "текст", "этот", "его", "it"])
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

    return ChatIntent("general_chat", confidence=0.5)
