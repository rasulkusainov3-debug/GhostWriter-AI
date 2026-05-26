from __future__ import annotations

from typing import Any

from app.services.chat_intent_service import ChatIntent, detect_intent
from app.services.llm.base import LLMUnavailable
from app.services.llm.factory import classify_intent_with_fallback

ALLOWED_INTENTS = {
    "general_chat",
    "find_new_trends",
    "refresh_trends",
    "show_current_trends",
    "create_content_plan",
    "edit_content_plan",
    "generate_posts",
    "regenerate_post",
    "edit_post",
    "edit_profile",
    "edit_audience_profile",
    "change_tone",
    "update_platforms",
    "explain_profile",
    "explain_trend",
    "content_plan_analytics",
    "recommendations",
}


async def detect_chat_intent(message: str, context: dict[str, Any]) -> tuple[ChatIntent, str]:
    rule_intent = detect_intent(message, context)
    if rule_intent.name != "general_chat":
        return rule_intent, "rules"
    try:
        parsed, provider = await classify_intent_with_fallback(message, context)
        intent_name = str(parsed.get("intent") or "").strip()
        if intent_name in ALLOWED_INTENTS:
            confidence = float(parsed.get("confidence") or 0.75)
            params = parsed.get("params") if isinstance(parsed.get("params"), dict) else {}
            return ChatIntent(intent_name, confidence=confidence, params=params), provider
    except (LLMUnavailable, ValueError, TypeError):
        pass
    return rule_intent, "rules"
