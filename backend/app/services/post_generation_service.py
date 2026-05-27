from __future__ import annotations

import re
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import execute, fetch_all, fetch_one
from app.services.analytics_context_service import build_analytics_context, build_generation_guidance
from app.services.content_plan_service import latest_content_plan
from app.services.post_generator_adapter import normalize_generation_mode, post_generator_adapter
from app.services.run_tracking_service import save_generation_run
from app.services.style_context_service import build_personality_brief, merge_personality_with_profile
from app.services.trend_service import active_trends


ALLOWED_POST_STATUSES = {"draft", "edited", "approved", "rejected", "scheduled", "published"}

def normalize_post_language(value: str | None) -> str:
    text = (value or "").strip().lower()

    if text in {"en", "english", "английский", "на английском", "in english"}:
        return "en"

    if text in {"kz", "kk", "kazakh", "казахский", "на казахском", "қазақша"}:
        return "kz"

    return "ru"

def _trend_slot_from_message(message: str) -> int | None:
    match = re.search(r"(?:втор|2|second)", message.lower())
    if match:
        return 1
    match = re.search(r"(?:перв|1|first)", message.lower())
    if match:
        return 0
    match = re.search(r"(?:треть|3|third)", message.lower())
    if match:
        return 2
    return None



def _slot_from_trend(trend: dict[str, Any], profile: dict[str, Any], message: str) -> dict[str, Any]:
    platforms = profile.get("platforms") or ["LinkedIn"]
    return {
        "slot_id": "chat_trend_post",
        "date": date.today().isoformat(),
        "time": "09:00",
        "platform": platforms[0],
        "format": "совет",
        "post_idea": message,
        "trend": trend,
    }


async def _feedback_payload(session: AsyncSession, user_id: str, profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    context = await build_analytics_context(session, user_id)
    feedback = build_generation_guidance(profile, context)
    return context, feedback


async def generate_posts_for_plan(
    session: AsyncSession,
    user_id: str,
    profile: dict[str, Any],
    plan_id: str,
    use_llm: bool = True,
    item_ids: set[str] | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    items = await fetch_all(
        session,
        """
        SELECT cpi.*, t.topic AS trend_topic, t.summary AS trend_summary, t.keywords AS trend_keywords
        FROM content_plan_items cpi
        JOIN content_plans cp ON cp.id = cpi.plan_id
        LEFT JOIN trends t ON t.id = cpi.trend_id
        WHERE cp.id = :plan_id AND cp.user_id = :user_id
        ORDER BY cpi.slot_order
        """,
        {"plan_id": plan_id, "user_id": user_id},
    )
    if item_ids:
        items = [item for item in items if str(item["id"]) in item_ids]
    created = []
    analytics_context, analytics_feedback = await _feedback_payload(session, user_id, profile)
    post_language = normalize_post_language(language)
    personality_brief = await build_personality_brief(session, user_id)
    generator_profile = merge_personality_with_profile({**profile, "analytics_feedback": analytics_feedback}, personality_brief)
    for item in items:
        slot = {
            "slot_id": str(item["id"]),
            "date": item["scheduled_date"].isoformat(),
            "time": str(item["scheduled_time"])[:5],
            "platform": item["platform"],
            "format": item["format"],
            "post_idea": item["post_idea"],
            "language": post_language,

            "trend": {
                "id": item["trend_id"],
                "topic": item.get("trend_topic"),
                "summary": item.get("trend_summary"),
                "keywords": item.get("trend_keywords") or [],
            },
            "analytics_feedback": analytics_feedback,
            "personality_brief": personality_brief,
        }
        generated = await post_generator_adapter.generate_post_async(
            slot,
            generator_profile,
            use_llm=use_llm,
            mode="create",
            language=post_language,
        )
        post = await fetch_one(
            session,
            """
            INSERT INTO generated_posts
                (user_id, plan_item_id, trend_id, platform, format, draft_text, final_text, status, llm_provider, stats)
            VALUES
                (:user_id, :plan_item_id, :trend_id, :platform, :format, :draft_text, :final_text, 'draft', :llm_provider, CAST(:stats AS JSONB))
            RETURNING *
            """,
            {
                "user_id": user_id,
                "plan_item_id": item["id"],
                "trend_id": item["trend_id"],
                "platform": item["platform"],
                "format": item["format"],
                **generated,
            },
        )
        await execute(session, "UPDATE content_plan_items SET status = 'generated' WHERE id = :id", {"id": item["id"]})
        created.append(post)
    await save_generation_run(
        session,
        user_id=user_id,
        run_type="post_generation",
        provider="llm" if use_llm else "template",
        agent_name="social_analyzer.agent2.post_generator",
        input_payload={
            "plan_id": plan_id,
            "item_ids": list(item_ids) if item_ids else None,
            "use_llm": use_llm,
            "mode": "create",
            "language": post_language,
            "analytics_context_summary": {
                "data_quality": analytics_context.get("data_quality"),
                "metrics_rows": analytics_context.get("metrics_rows"),
                "best_platforms": analytics_feedback.get("best_platforms", []),
                "best_formats": analytics_feedback.get("best_formats", []),
                "personality": {
                    "voice": personality_brief.get("voice"),
                    "writing_style": personality_brief.get("writing_style"),
                    "examples_used": personality_brief.get("examples_used"),
                },
            },
        },
        output_payload={
            "post_ids": [str(post["id"]) for post in created if post],
            "posts_count": len(created),
            "providers": [post.get("llm_provider") for post in created if post],
            "fallback_used": [post.get("stats", {}).get("fallback_used") for post in created if post],
            "invalid_output_detected": [post.get("stats", {}).get("invalid_output_detected") for post in created if post],
        },
        status="completed",
    )
    return {"created": created}

async def generate_from_latest_plan(session: AsyncSession,user_id: str,profile: dict[str, Any],use_llm: bool = True,language: str | None = None,) -> dict[str, Any]:
    plan = await latest_content_plan(session, user_id)
    if not plan:
        raise HTTPException(status_code=409, detail="No content plan found. Create a content plan first.")
    return await generate_posts_for_plan(session,user_id,profile,str(plan["plan"]["id"]),use_llm=use_llm,language=language,)


async def generate_post_from_trend_message(session: AsyncSession,user_id: str,profile: dict[str, Any],message: str,use_llm: bool = True,language: str | None = None,) -> dict[str, Any]:
    trends = await active_trends(session, user_id, limit=10)
    if not trends:
        raise HTTPException(status_code=409, detail="No active trends available. Find new trends first.")
    index = _trend_slot_from_message(message) or 0
    if index >= len(trends):
        raise HTTPException(status_code=409, detail="Selected trend was not found. Ask to show current trends.")
    trend = trends[index]
    slot = _slot_from_trend(trend, profile, message)
    post_language = normalize_post_language(language)
    slot["language"] = post_language
    analytics_context, analytics_feedback = await _feedback_payload(session, user_id, profile)
    slot["analytics_feedback"] = analytics_feedback
    personality_brief = await build_personality_brief(session, user_id)
    slot["personality_brief"] = personality_brief
    generator_profile = merge_personality_with_profile({**profile, "analytics_feedback": analytics_feedback}, personality_brief)
    generated = await post_generator_adapter.generate_post_async(
        slot,
        generator_profile,
        use_llm=use_llm,
        mode="create",
        language=post_language,
    )
    post = await fetch_one(
        session,
        """
        INSERT INTO generated_posts
            (user_id, plan_item_id, trend_id, platform, format, draft_text, final_text, status, llm_provider, stats)
        VALUES
            (:user_id, NULL, :trend_id, :platform, :format, :draft_text, :final_text, 'draft', :llm_provider, CAST(:stats AS JSONB))
        RETURNING *
        """,
        {
            "user_id": user_id,
            "trend_id": trend["id"],
            "platform": slot["platform"],
            "format": slot["format"],
            **generated,
        },
    )
    await save_generation_run(
        session,
        user_id=user_id,
        run_type="post_generation",
        provider=post.get("llm_provider") if post else ("llm" if use_llm else "template"),
        agent_name="social_analyzer.agent2.post_generator",
        input_payload={
            "trend_id": trend.get("id"),
            "message": message,
            "use_llm": use_llm,
            "mode": "create",
            "language": post_language,
            "analytics_context_summary": {
                "data_quality": analytics_context.get("data_quality"),
                "metrics_rows": analytics_context.get("metrics_rows"),
                "best_platforms": analytics_feedback.get("best_platforms", []),
                "best_formats": analytics_feedback.get("best_formats", []),
                "personality": {
                    "voice": personality_brief.get("voice"),
                    "writing_style": personality_brief.get("writing_style"),
                    "examples_used": personality_brief.get("examples_used"),
                },
            },
        },
        output_payload={
            "post_id": str(post["id"]) if post else None,
            "provider": generated.get("llm_provider"),
            "fallback_used": generated.get("stats", {}).get("fallback_used"),
            "invalid_output_detected": generated.get("stats", {}).get("invalid_output_detected"),
        },
        status="completed",
    )
    return {"post": post, "trend": trend}


async def generate_post_from_trend_id(
    session: AsyncSession,
    user_id: str,
    profile: dict[str, Any],
    trend_id: int,
    platform: str | None = None,
    format: str | None = None,
    use_llm: bool = True,
    language: str | None = None,
) -> dict[str, Any]:
    trend = await fetch_one(
        session,
        "SELECT * FROM trends WHERE id = :id AND user_id = :user_id AND expires_at > NOW()",
        {"id": trend_id, "user_id": user_id},
    )
    if not trend:
        raise HTTPException(status_code=404, detail="Selected trend was not found")
    slot = _slot_from_trend(trend, profile, trend.get("topic") or "")
    if platform:
        slot["platform"] = platform
    if format:
        slot["format"] = format
    post_language = normalize_post_language(language)
    slot["language"] = post_language
    analytics_context, analytics_feedback = await _feedback_payload(session, user_id, profile)
    slot["analytics_feedback"] = analytics_feedback
    personality_brief = await build_personality_brief(session, user_id)
    slot["personality_brief"] = personality_brief
    generator_profile = merge_personality_with_profile({**profile, "analytics_feedback": analytics_feedback}, personality_brief)
    generated = await post_generator_adapter.generate_post_async(
        slot,
        generator_profile,
        use_llm=use_llm,
        mode="create",
        language=post_language,
    )
    post = await fetch_one(
        session,
        """
        INSERT INTO generated_posts
            (user_id, plan_item_id, trend_id, platform, format, draft_text, final_text, status, llm_provider, stats)
        VALUES
            (:user_id, NULL, :trend_id, :platform, :format, :draft_text, :final_text, 'draft', :llm_provider, CAST(:stats AS JSONB))
        RETURNING *
        """,
        {
            "user_id": user_id,
            "trend_id": trend["id"],
            "platform": slot["platform"],
            "format": slot["format"],
            **generated,
        },
    )
    await save_generation_run(
        session,
        user_id=user_id,
        run_type="post_generation",
        provider=post.get("llm_provider") if post else ("llm" if use_llm else "template"),
        agent_name="social_analyzer.agent2.post_generator",
        input_payload={
            "flow_mode": "single_trend",
            "trend_id": trend.get("id"),
            "platform": slot["platform"],
            "format": slot["format"],
            "use_llm": use_llm,
            "mode": "create",
            "language": post_language,
            "analytics_context_summary": {
                "data_quality": analytics_context.get("data_quality"),
                "metrics_rows": analytics_context.get("metrics_rows"),
                "best_platforms": analytics_feedback.get("best_platforms", []),
                "best_formats": analytics_feedback.get("best_formats", []),
                "personality": {
                    "voice": personality_brief.get("voice"),
                    "writing_style": personality_brief.get("writing_style"),
                    "examples_used": personality_brief.get("examples_used"),
                },
            },
        },
        output_payload={
            "post_id": str(post["id"]) if post else None,
            "provider": generated.get("llm_provider"),
            "fallback_used": generated.get("stats", {}).get("fallback_used"),
            "invalid_output_detected": generated.get("stats", {}).get("invalid_output_detected"),
        },
        status="completed",
    )
    return {"post": post, "trend": trend}


async def regenerate_post(
    session: AsyncSession,
    user_id: str,
    post_id: str,
    profile: dict[str, Any],
    use_llm: bool = True,
    mode: str = "regenerate_full",
    language: str | None = None,
) -> dict[str, Any]:
    mode = normalize_generation_mode(mode)
    post_language = normalize_post_language(language)
    post = await fetch_one(session, "SELECT * FROM generated_posts WHERE id = :id AND user_id = :user_id", {"id": post_id, "user_id": user_id})
    if not post:
        raise HTTPException(status_code=404, detail="Generated post not found")
    item = await fetch_one(session, "SELECT * FROM content_plan_items WHERE id = :id", {"id": post["plan_item_id"]}) if post.get("plan_item_id") else None
    trend = None
    if post.get("trend_id"):
        trend = await fetch_one(
            session,
            "SELECT id, topic, summary, keywords FROM trends WHERE id = :id AND user_id = :user_id",
            {"id": post["trend_id"], "user_id": user_id},
        )
    analytics_context, analytics_feedback = await _feedback_payload(session, user_id, profile)
    if str(post_id) in set(analytics_feedback.get("low_engagement_post_ids") or []):
        analytics_feedback = {
            **analytics_feedback,
            "regeneration_guidance": [
                "Strengthen the opening hook.",
                "Improve the CTA so it connects to the user's goal.",
                "Adapt toward best-performing formats or platforms when the user has not fixed them.",
                "Avoid weak patterns from previous low-engagement posts.",
            ],
        }
    slot = {
        "slot_id": str(item["id"]) if item else str(post["id"]),
        "language": post_language,
        "date": item["scheduled_date"].isoformat() if item else date.today().isoformat(),
        "time": str(item["scheduled_time"])[:5] if item else "09:00",
        "platform": post["platform"],
        "format": post["format"],
        "post_idea": item.get("post_idea") if item else (post["final_text"] or post["draft_text"] or "")[:160],
        "trend": {
            "id": post.get("trend_id"),
            "topic": trend.get("topic") if trend else None,
            "summary": trend.get("summary") if trend else None,
            "keywords": trend.get("keywords") if trend else [],
        },
        "analytics_feedback": analytics_feedback,
        "generation_mode": mode,
        "current_final_text": post.get("final_text"),
    }
    personality_brief = await build_personality_brief(session, user_id)
    slot["personality_brief"] = personality_brief
    generator_profile = merge_personality_with_profile({**profile, "analytics_feedback": analytics_feedback}, personality_brief)
    generated = await post_generator_adapter.generate_post_async(
        slot,
        generator_profile,
        use_llm=use_llm,
        mode=mode,
        current_text=post.get("final_text"),
        language=post_language,

    )
    await execute(
        session,
        """
        UPDATE generated_posts
        SET draft_text=:draft_text, final_text=:final_text, stats=CAST(:stats AS JSONB), llm_provider=:llm_provider, status='draft'
        WHERE id=:id AND user_id=:user_id
        """,
        {**generated, "id": post_id, "user_id": user_id},
    )
    updated = await fetch_one(session, "SELECT * FROM generated_posts WHERE id = :id AND user_id = :user_id", {"id": post_id, "user_id": user_id})
    await save_generation_run(
        session,
        user_id=user_id,
        run_type="post_regeneration",
        provider=generated.get("llm_provider"),
        agent_name="social_analyzer.agent2.post_generator",
        input_payload={
            "post_id": post_id,
            "use_llm": use_llm,
            "mode": mode,
            "language": post_language,
            "analytics_context_summary": {
                "data_quality": analytics_context.get("data_quality"),
                "metrics_rows": analytics_context.get("metrics_rows"),
                "best_platforms": analytics_feedback.get("best_platforms", []),
                "best_formats": analytics_feedback.get("best_formats", []),
                "regeneration_guidance": analytics_feedback.get("regeneration_guidance", []),
                "personality": {
                    "voice": personality_brief.get("voice"),
                    "writing_style": personality_brief.get("writing_style"),
                    "examples_used": personality_brief.get("examples_used"),
                },
            },
        },
        output_payload={
            "post_id": str(updated["id"]) if updated else post_id,
            "provider": generated.get("llm_provider"),
            "fallback_used": generated.get("stats", {}).get("fallback_used"),
            "invalid_output_detected": generated.get("stats", {}).get("invalid_output_detected"),
            "generation_mode": mode,
        },
        status="completed",
    )
    return updated


async def update_generated_post(
    session: AsyncSession,
    user_id: str,
    post_id: str,
    draft_text: str | None = None,
    final_text: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    post = await fetch_one(
        session,
        "SELECT * FROM generated_posts WHERE id = :id AND user_id = :user_id",
        {"id": post_id, "user_id": user_id},
    )
    if not post:
        raise HTTPException(status_code=404, detail="Generated post not found")
    text_changed = False
    next_draft = post["draft_text"]
    next_final = post["final_text"]
    if draft_text is not None and draft_text != post["draft_text"]:
        next_draft = draft_text
        text_changed = True
    if final_text is not None and final_text != post["final_text"]:
        next_final = final_text
        text_changed = True
    next_status = status or ("edited" if text_changed else post["status"])
    if next_status not in ALLOWED_POST_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unsupported post status: {next_status}")
    await execute(
        session,
        """
        UPDATE generated_posts
        SET draft_text = :draft_text, final_text = :final_text, status = :status
        WHERE id = :id AND user_id = :user_id
        """,
        {
            "draft_text": next_draft,
            "final_text": next_final,
            "status": next_status,
            "id": post_id,
            "user_id": user_id,
        },
    )
    updated = await fetch_one(
        session,
        "SELECT * FROM generated_posts WHERE id = :id AND user_id = :user_id",
        {"id": post_id, "user_id": user_id},
    )
    await save_generation_run(
        session,
        user_id=user_id,
        run_type="post_edit" if text_changed else "post_status_update",
        provider=None,
        agent_name="generated_posts_router",
        input_payload={
            "post_id": post_id,
            "draft_text_changed": draft_text is not None and draft_text != post["draft_text"],
            "final_text_changed": final_text is not None and final_text != post["final_text"],
            "requested_status": status,
        },
        output_payload={"post_id": post_id, "status": next_status},
        status="completed",
    )
    return updated or {}
