from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import execute, fetch_one
from app.schemas.common import ChatMessageRequest
from app.services.chat.action_executor import complete_steps, execute_action
from app.services.chat.context_builder import load_chat_context
from app.services.chat.intent_detector import detect_chat_intent
from app.services.lifecycle_service import build_lifecycle


ACTION_REQUIRED_BY_LIFECYCLE = {
    "complete_onboarding": "complete_profile",
    "continue_onboarding": "complete_profile",
    "confirm_profile": "confirm_profile",
    "find_trends": "find_trends",
    "create_content_plan": "create_content_plan",
    "approve_content_plan": "approve_content_plan",
    "generate_posts": "generate_posts",
    "review_posts": "review_posts",
    "schedule_posts": "schedule_posts",
    "publish_posts": "publish_posts",
    "add_metrics": "add_metrics",
}


def visible_messages(messages: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    seen_assistant_texts: set[str] = set()
    for message in messages:
        text = str(message.get("text") or "").strip()
        if message.get("role") == "assistant" and text in seen_assistant_texts:
            continue
        if message.get("role") == "assistant":
            seen_assistant_texts.add(text)
        visible.append(message)
    return visible[-limit:]


async def save_dialogues(session: AsyncSession, user_id: str, raw_answers: dict[str, Any], dialogues: list[dict[str, Any]]) -> dict[str, Any] | None:
    raw_answers["chat_dialogues"] = dialogues
    await execute(
        session,
        "UPDATE user_profiles SET raw_answers = CAST(:raw_answers AS JSONB) WHERE user_id = :user_id",
        {"raw_answers": raw_answers, "user_id": user_id},
    )
    return await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user_id})


async def run_chat_pipeline(session: AsyncSession, user: dict[str, Any], payload: ChatMessageRequest) -> dict[str, Any]:
    user_id = str(user["id"])
    context = await load_chat_context(session, user_id)
    profile = context["profile"]
    raw_answers = context["raw_answers"] or {}
    dialogues = list(context["messages"] or [])

    user_message = {
        "role": "user",
        "text": payload.message,
        "ts": datetime.now(timezone.utc).isoformat(),
        "context": payload.context,
    }
    dialogues.append(user_message)

    intent, detector_provider = await detect_chat_intent(payload.message, {**context, "messages": dialogues})
    result = await execute_action(session, user, profile, intent, payload.message, dialogues)
    if result.get("profile"):
        profile = result["profile"]

    action = result.get("action") or {}
    action["steps"] = complete_steps(intent.name)
    lifecycle = await build_lifecycle(session, user_id)
    next_action_type = (lifecycle.get("next_action") or {}).get("type")
    if not action.get("action_required") and next_action_type in ACTION_REQUIRED_BY_LIFECYCLE:
        action["action_required"] = ACTION_REQUIRED_BY_LIFECYCLE[next_action_type]
    action["lifecycle"] = lifecycle
    if settings.debug_chat:
        action["detector_provider"] = detector_provider
    else:
        action.pop("detector_provider", None)
        action.pop("provider", None)
        action.pop("context", None)
        action.pop("errors", None)

    response = {
        "role": "assistant",
        "text": result["text"],
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
    }
    if settings.debug_chat:
        response["intent"] = intent.name
        response["steps"] = action["steps"]
    dialogues.append(response)

    latest_profile = profile or await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user_id})
    latest_raw_answers = (latest_profile or {}).get("raw_answers") or raw_answers
    latest_profile = await save_dialogues(session, user_id, latest_raw_answers, dialogues)
    await session.commit()

    return {
        "messages": visible_messages(dialogues),
        "reply": response,
        "profile": latest_profile,
        "lifecycle": lifecycle,
        "intent": intent.name,
        "action": action,
        "steps": action["steps"],
    }
