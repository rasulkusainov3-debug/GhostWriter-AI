from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import execute, fetch_all, fetch_one
from app.services.analytics_context_service import build_analytics_context, build_generation_guidance, rank_trends_with_feedback
from app.services.content_planner_adapter import content_planner_adapter
from app.services.run_tracking_service import save_generation_run


RELEVANCE_PRIORITY = {"high": 0, "medium": 1, "low": 2}


def week_start(value: date | None = None) -> date:
    today = value or date.today()
    return today - timedelta(days=today.weekday())


def _as_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return date.today()


def _as_time(value: Any) -> time:
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time().replace(second=0, microsecond=0)
    if isinstance(value, str):
        return time.fromisoformat(value[:5])
    return time(hour=9)


def _trend_relevance(trend: dict[str, Any]) -> tuple[str, float]:
    insights = trend.get("youtube_insights") or {}
    level = trend.get("relevance_level") or insights.get("relevance_level") or "medium"
    score = trend.get("relevance_score") or insights.get("relevance_score") or trend.get("final_score") or 0
    try:
        score_value = float(score)
    except Exception:
        score_value = 0.0
    return str(level), score_value


async def latest_relevant_trends(session: AsyncSession, user_id: str, limit: int = 20, analytics_context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    trends = await fetch_all(
        session,
        """
        SELECT *
        FROM trends
        WHERE user_id = :user_id AND expires_at > NOW()
        ORDER BY final_score DESC
        LIMIT 80
        """,
        {"user_id": user_id},
    )
    if not trends:
        return []
    sorted_trends = sorted(
        trends,
        key=lambda trend: (
            RELEVANCE_PRIORITY.get(_trend_relevance(trend)[0], 1),
            -_trend_relevance(trend)[1],
            -(trend.get("posts_count") or 0),
        ),
    )
    relevant = [trend for trend in sorted_trends if _trend_relevance(trend)[0] in {"high", "medium"}]
    ranked = rank_trends_with_feedback(relevant or sorted_trends, analytics_context or {}) if analytics_context else (relevant or sorted_trends)
    return ranked[:limit]


def _unique(values: list[str], limit: int = 8) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        key = item.lower()
        if item and key not in seen:
            result.append(item)
            seen.add(key)
        if len(result) >= limit:
            break
    return result


def _keywords(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def build_plan_summary(profile: dict[str, Any], trends: list[dict[str, Any]], items: list[dict[str, Any]]) -> dict[str, Any]:
    platforms = _unique([str(item.get("platform")) for item in items] or [str(platform) for platform in profile.get("platforms") or []])
    top_topics = _unique([str(trend.get("topic")) for trend in trends], limit=5)
    pillar_keywords = _unique([keyword for trend in trends for keyword in _keywords(trend.get("keywords"))], limit=8)
    content_pillars = top_topics[:3] or pillar_keywords[:3]
    weekly_structure = [
        {
            "day": str(item.get("scheduled_date")),
            "time": str(item.get("scheduled_time") or "")[:5],
            "platform": item.get("platform"),
            "format": item.get("format"),
            "focus": item.get("trend_topic") or item.get("post_idea"),
        }
        for item in items
    ]
    trend_based_ideas = [
        {
            "trend": item.get("trend_topic"),
            "idea": item.get("post_idea"),
            "platform": item.get("platform"),
            "format": item.get("format"),
        }
        for item in items
    ]
    profession = profile.get("profession") or profile.get("niche") or "эксперт"
    goal = profile.get("goal") or "развивать контент"
    return {
        "direction": f"Развивать экспертный контент вокруг тем: {', '.join(content_pillars[:3]) or 'актуальные тренды ниши'}.",
        "audience": profile.get("audience") or "целевая аудитория профиля",
        "goal": goal,
        "platforms": platforms or ["LinkedIn"],
        "content_pillars": content_pillars,
        "weekly_structure": weekly_structure,
        "trend_based_ideas": trend_based_ideas,
        "suggested_formats": _unique([str(item.get("format")) for item in items], limit=6),
        "next_steps": [
            "Проверьте слоты и идеи постов.",
            "Отредактируйте форматы или платформы при необходимости.",
            "После утверждения сгенерируйте тексты постов.",
        ],
        "target_positioning": f"{profession}: связать найденные тренды с целью «{goal}».",
    }


async def create_weekly_content_plan(
    session: AsyncSession,
    user_id: str,
    profile: dict[str, Any],
    title: str = "Content plan",
    posts_per_week: int = 5,
    start: date | None = None,
) -> dict[str, Any]:
    if not profile or not profile.get("niche"):
        raise HTTPException(status_code=409, detail="Complete onboarding/profile before content generation")

    analytics_context = await build_analytics_context(session, user_id)
    analytics_feedback = build_generation_guidance(profile, analytics_context)
    planner_profile = {**profile, "analytics_feedback": analytics_feedback}
    trends = await latest_relevant_trends(session, user_id, limit=20, analytics_context=analytics_context)
    if not trends:
        raise HTTPException(status_code=409, detail="No active trends available. Run parser/trend generation first.")

    slots = content_planner_adapter.build_content_plan(trends, planner_profile, posts_per_week=posts_per_week)
    plan = await fetch_one(
        session,
        """
        INSERT INTO content_plans (user_id, title, week_start, status)
        VALUES (:user_id, :title, :week_start, 'draft')
        RETURNING *
        """,
        {"user_id": user_id, "title": title, "week_start": week_start(start)},
    )
    for index, slot in enumerate(slots):
        trend = slot.get("trend") or {}
        await execute(
            session,
            """
            INSERT INTO content_plan_items
                (plan_id, trend_id, platform, format, post_idea, scheduled_date, scheduled_time, slot_order, status)
            VALUES
                (:plan_id, :trend_id, :platform, :format, :post_idea, :scheduled_date, :scheduled_time, :slot_order, :status)
            """,
            {
                "plan_id": plan["id"],
                "trend_id": trend.get("id"),
                "platform": slot["platform"],
                "format": slot["format"],
                "post_idea": slot["post_idea"],
                "scheduled_date": _as_date(slot["date"]),
                "scheduled_time": _as_time(slot["time"]),
                "slot_order": index,
                "status": slot.get("status", "planned"),
            },
        )
    result = await get_content_plan(session, user_id, str(plan["id"]))
    result["summary"] = build_plan_summary(profile, trends, result["items"])
    result["analytics_feedback"] = analytics_feedback
    result["selected_trends"] = trends[:posts_per_week]
    await save_generation_run(
        session,
        user_id=user_id,
        run_type="content_plan",
        provider="template",
        agent_name="social_analyzer.agent2.content_planner",
        input_payload={
            "profile": profile,
            "analytics_context_summary": {
                "data_quality": analytics_context.get("data_quality"),
                "metrics_rows": analytics_context.get("metrics_rows"),
                "best_platforms": analytics_feedback.get("best_platforms", []),
                "best_formats": analytics_feedback.get("best_formats", []),
                "best_topics": analytics_feedback.get("best_topics", []),
            },
            "trend_ids": [trend.get("id") for trend in trends[:posts_per_week]],
            "posts_per_week": posts_per_week,
            "week_start": str(week_start(start)),
        },
        output_payload={
            "content_plan_id": str(result["plan"]["id"]),
            "item_ids": [str(item["id"]) for item in result["items"]],
            "items_count": len(result["items"]),
        },
        status="completed",
    )
    return result


async def get_content_plan(session: AsyncSession, user_id: str, plan_id: str) -> dict[str, Any]:
    plan = await fetch_one(session, "SELECT * FROM content_plans WHERE id = :id AND user_id = :user_id", {"id": plan_id, "user_id": user_id})
    if not plan:
        raise HTTPException(status_code=404, detail="Content plan not found")
    items = await fetch_all(
        session,
        """
        SELECT
            cpi.*,
            t.topic AS trend_topic,
            t.summary AS trend_summary,
            t.keywords AS trend_keywords,
            gp.id AS generated_post_id,
            gp.status AS generated_post_status,
            gp.generated_at AS generated_post_at
        FROM content_plan_items cpi
        LEFT JOIN trends t ON t.id = cpi.trend_id
        LEFT JOIN LATERAL (
            SELECT id, status, generated_at
            FROM generated_posts
            WHERE plan_item_id = cpi.id AND user_id = :user_id
            ORDER BY generated_at DESC
            LIMIT 1
        ) gp ON TRUE
        WHERE cpi.plan_id = :plan_id
        ORDER BY cpi.scheduled_date, cpi.scheduled_time, cpi.slot_order
        """,
        {"plan_id": plan_id, "user_id": user_id},
    )
    return {"plan": plan, "items": items}


async def latest_content_plan(session: AsyncSession, user_id: str) -> dict[str, Any] | None:
    plan = await fetch_one(session, "SELECT * FROM content_plans WHERE user_id = :user_id ORDER BY created_at DESC LIMIT 1", {"user_id": user_id})
    if not plan:
        return None
    return await get_content_plan(session, user_id, str(plan["id"]))


async def add_trend_to_draft_plan(session: AsyncSession, user_id: str, trend_id: int, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    trend = await fetch_one(
        session,
        "SELECT * FROM trends WHERE id = :id AND user_id = :user_id AND expires_at > NOW()",
        {"id": trend_id, "user_id": user_id},
    )
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    plan = await fetch_one(
        session,
        """
        SELECT *
        FROM content_plans
        WHERE user_id = :user_id AND status = 'draft'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"user_id": user_id},
    )
    if not plan:
        plan = await fetch_one(
            session,
            """
            INSERT INTO content_plans (user_id, title, week_start, status)
            VALUES (:user_id, :title, :week_start, 'draft')
            RETURNING *
            """,
            {"user_id": user_id, "title": "Content plan from selected trends", "week_start": week_start()},
        )
    existing = await fetch_one(
        session,
        """
        SELECT COUNT(*) AS count
        FROM content_plan_items
        WHERE plan_id = :plan_id
        """,
        {"plan_id": plan["id"]},
    )
    slot_order = int((existing or {}).get("count") or 0)
    platforms = (profile or {}).get("platforms") or ["LinkedIn"]
    platform = platforms[slot_order % len(platforms)] if platforms else "LinkedIn"
    scheduled_date = week_start() + timedelta(days=min(slot_order, 6))
    item = await fetch_one(
        session,
        """
        INSERT INTO content_plan_items
            (plan_id, trend_id, platform, format, post_idea, scheduled_date, scheduled_time, slot_order, status)
        VALUES
            (:plan_id, :trend_id, :platform, :format, :post_idea, :scheduled_date, :scheduled_time, :slot_order, 'planned')
        RETURNING *
        """,
        {
            "plan_id": plan["id"],
            "trend_id": trend["id"],
            "platform": platform,
            "format": "post",
            "post_idea": f"{trend.get('topic')}: {trend.get('summary') or ''}".strip(),
            "scheduled_date": scheduled_date,
            "scheduled_time": time(hour=9),
            "slot_order": slot_order,
        },
    )
    await save_generation_run(
        session,
        user_id=user_id,
        run_type="content_plan_edit",
        provider=None,
        agent_name="content_plan_service",
        input_payload={"trend_id": trend_id, "plan_id": str(plan["id"])},
        output_payload={"plan_id": str(plan["id"]), "item_id": str(item["id"]) if item else None},
        status="completed",
    )
    return {"plan": plan, "item": item, "trend": trend}
