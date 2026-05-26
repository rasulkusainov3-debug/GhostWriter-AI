from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import fetch_all, fetch_one


def _latest_visible_trends(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for message in reversed(messages or []):
        action = message.get("action") if isinstance(message.get("action"), dict) else {}
        trends = action.get("trends") if isinstance(action, dict) else None
        if isinstance(trends, list) and trends:
            return trends
    return []


async def load_chat_context(session: AsyncSession, user_id: str) -> dict[str, Any]:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user_id})
    raw_answers = (profile or {}).get("raw_answers") or {}
    messages = raw_answers.get("chat_dialogues", [])
    trends = await fetch_all(
        session,
        """
        SELECT *
        FROM trends
        WHERE user_id = :user_id AND expires_at > NOW()
        ORDER BY final_score DESC
        LIMIT 10
        """,
        {"user_id": user_id},
    )
    plan = await fetch_one(
        session,
        "SELECT * FROM content_plans WHERE user_id = :user_id ORDER BY created_at DESC LIMIT 1",
        {"user_id": user_id},
    )
    post = await fetch_one(
        session,
        "SELECT * FROM generated_posts WHERE user_id = :user_id ORDER BY generated_at DESC LIMIT 1",
        {"user_id": user_id},
    )
    return {
        "profile": profile,
        "raw_answers": raw_answers,
        "messages": messages,
        "trends": trends,
        "latest_visible_trends": _latest_visible_trends(messages),
        "selected_plan": plan,
        "selected_post": post,
    }
