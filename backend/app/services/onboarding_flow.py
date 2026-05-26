from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import execute
from app.services.lifecycle_service import mark_audience_needs_confirmation, mark_profile_needs_confirmation
from app.services.social_analyzer_adapter import adapter
from app.services.trend_service import find_and_save_trends


async def finish_onboarding_flow(session: AsyncSession, user_id: str, answers: dict[str, Any], session_id: str) -> dict[str, Any]:
    profile = adapter.normalize_profile_answers(user_id, answers)
    await execute(
        session,
        """
        INSERT INTO user_profiles (user_id, name, niche, profession, goal, tone, audience, avoid, user_values, platforms, raw_answers)
        VALUES (:user_id, :name, :niche, :profession, :goal, :tone, :audience, :avoid, CAST(:user_values AS JSONB), CAST(:platforms AS JSONB), CAST(:raw_answers AS JSONB))
        ON CONFLICT (user_id) DO UPDATE SET
            name = EXCLUDED.name,
            niche = EXCLUDED.niche,
            profession = EXCLUDED.profession,
            goal = EXCLUDED.goal,
            tone = EXCLUDED.tone,
            audience = EXCLUDED.audience,
            avoid = EXCLUDED.avoid,
            user_values = EXCLUDED.user_values,
            platforms = EXCLUDED.platforms,
            raw_answers = user_profiles.raw_answers || EXCLUDED.raw_answers
        """,
        profile,
    )
    await execute(
        session,
        "UPDATE interview_sessions SET status = 'completed', finished_at = NOW() WHERE id = :id",
        {"id": session_id},
    )
    await mark_profile_needs_confirmation(session, user_id)
    await mark_audience_needs_confirmation(session, user_id)
    trend_result = await find_and_save_trends(session, user_id, profile, run_legacy=True)
    return {
        "status": "completed",
        "profile": profile,
        "flow": [
            {"step": "profile_created", "status": "completed"},
            {"step": "searching_trends", "status": "completed"},
            {"step": "trends_found", "status": trend_result["status"], "count": len(trend_result["trends"])},
        ],
        "trend_result": trend_result,
    }
