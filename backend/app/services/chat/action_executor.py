from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat_action_service import execute_chat_intent
from app.services.chat_intent_service import ChatIntent


ACTION_STEPS = {
    "find_new_trends": ["building_queries", "searching_materials", "checking_relevance", "grouping_trends", "cleaning_keywords", "saving_result"],
    "refresh_trends": ["building_queries", "searching_materials", "checking_relevance", "grouping_trends", "cleaning_keywords", "saving_result"],
    "show_current_trends": ["loading_trends", "done"],
    "create_content_plan": ["loading_trends", "passing_to_planner", "creating_content_plan", "saving_content_plan"],
    "edit_content_plan": ["loading_content_plan", "done"],
    "generate_posts": ["generating_post", "saving_result"],
    "regenerate_post": ["regenerating_post", "saving_result"],
    "edit_post": ["updating_post", "saving_result"],
    "edit_profile": ["editing_profile", "saving_result"],
    "edit_audience_profile": ["editing_profile", "saving_result"],
    "change_tone": ["editing_profile", "saving_result"],
    "update_platforms": ["editing_profile", "saving_result"],
    "explain_profile": ["loading_profile", "done"],
    "explain_trend": ["loading_trends", "done"],
    "content_plan_analytics": ["analyzing_plan", "done"],
    "recommendations": ["generating_response", "done"],
    "general_chat": ["generating_response", "done"],
}


def pipeline_steps(intent_name: str) -> list[dict[str, str]]:
    keys = ["analyzing_request", "loading_profile", "detecting_intent", *ACTION_STEPS.get(intent_name, ["processing"]), "done"]
    deduped: list[str] = []
    for key in keys:
        if key not in deduped:
            deduped.append(key)
    return [{"key": key, "status": "pending"} for key in deduped]


def complete_steps(intent_name: str, failed: bool = False) -> list[dict[str, str]]:
    steps = pipeline_steps(intent_name)
    for step in steps:
        step["status"] = "done"
    if failed and steps:
        steps[-1]["status"] = "error"
    return steps


async def execute_action(
    session: AsyncSession,
    user: dict[str, Any],
    profile: dict[str, Any] | None,
    intent: ChatIntent,
    message: str,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    return await execute_chat_intent(session, user, profile, intent, message, history)
