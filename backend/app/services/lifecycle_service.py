from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import execute, fetch_all, fetch_one


CONFIRMATION_STATUSES = {"draft", "needs_confirmation", "confirmed"}
PROFILE_CONFIRMATION_FIELDS = {"name", "niche", "profession", "goal", "tone", "avoid", "user_values", "platforms"}
AUDIENCE_CONFIRMATION_FIELDS = {"audience"}

LIFECYCLE_ORDER = [
    "registered",
    "onboarding_in_progress",
    "profile_generated",
    "profile_needs_confirmation",
    "profile_confirmed",
    "trends_ready",
    "content_plan_ready",
    "content_plan_needs_approval",
    "content_plan_approved",
    "posts_generated",
    "posts_ready_for_review",
    "posts_approved",
    "scheduled",
    "published",
    "metrics_added",
    "recommendations_ready",
]


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _has_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def profile_has_meaningful_fields(profile: dict[str, Any] | None) -> bool:
    if not profile:
        return False
    return any(
        [
            _has_text(profile.get("niche")),
            _has_text(profile.get("profession")),
            _has_text(profile.get("goal")),
            _has_text(profile.get("tone")),
            _has_text(profile.get("avoid")),
            _has_list(profile.get("platforms")),
            _has_list(profile.get("user_values")),
        ]
    )


def profile_fields_changed(current: dict[str, Any], updates: dict[str, Any], fields: set[str]) -> bool:
    sentinel = object()
    for field in fields:
        if field not in updates:
            continue
        before = current.get(field, sentinel)
        after = updates.get(field, sentinel)
        if before != after:
            return True
    return False


async def mark_profile_needs_confirmation(session: AsyncSession, user_id: str) -> None:
    await execute(
        session,
        """
        UPDATE user_profiles
        SET profile_confirmation_status = 'needs_confirmation',
            profile_confirmed_at = NULL
        WHERE user_id = :user_id
        """,
        {"user_id": user_id},
    )


async def mark_audience_needs_confirmation(session: AsyncSession, user_id: str) -> None:
    await execute(
        session,
        """
        UPDATE user_profiles
        SET audience_confirmation_status = 'needs_confirmation',
            audience_confirmed_at = NULL
        WHERE user_id = :user_id
        """,
        {"user_id": user_id},
    )


async def confirm_profile_scope(session: AsyncSession, user_id: str, scope: str) -> dict[str, Any]:
    if scope not in {"profile", "audience", "all"}:
        raise HTTPException(status_code=422, detail="Unsupported confirmation scope")
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    fields: list[str] = []
    if scope in {"profile", "all"}:
        fields.append("profile_confirmation_status = 'confirmed'")
        fields.append("profile_confirmed_at = NOW()")
    if scope in {"audience", "all"}:
        fields.append("audience_confirmation_status = 'confirmed'")
        fields.append("audience_confirmed_at = NOW()")
    await execute(
        session,
        f"UPDATE user_profiles SET {', '.join(fields)} WHERE user_id = :user_id",
        {"user_id": user_id},
    )
    return await build_lifecycle(session, user_id)


def _status_count(rows: list[dict[str, Any]], status: str) -> int:
    return sum(_as_int(row.get("count")) for row in rows if row.get("status") == status)


def _action_for_state(state: str, latest_plan_id: str | None = None) -> dict[str, Any]:
    actions = {
        "registered": {"type": "complete_onboarding", "route": "/onboarding"},
        "onboarding_in_progress": {"type": "continue_onboarding", "route": "/onboarding"},
        "profile_generated": {"type": "confirm_profile", "route": "/profile"},
        "profile_needs_confirmation": {"type": "confirm_profile", "route": "/profile"},
        "profile_confirmed": {"type": "find_trends", "route": "/chat", "message_key": "chat.quickFindTrendsMessage"},
        "trends_ready": {"type": "create_content_plan", "route": "/chat", "message_key": "chat.quickCreatePlanMessage"},
        "content_plan_ready": {"type": "approve_content_plan", "route": f"/content-plans/{latest_plan_id}" if latest_plan_id else "/content-plans"},
        "content_plan_needs_approval": {"type": "approve_content_plan", "route": f"/content-plans/{latest_plan_id}" if latest_plan_id else "/content-plans"},
        "content_plan_approved": {"type": "generate_posts", "route": f"/content-plans/{latest_plan_id}" if latest_plan_id else "/content-plans"},
        "posts_generated": {"type": "review_posts", "route": "/generated-posts"},
        "posts_ready_for_review": {"type": "review_posts", "route": "/generated-posts"},
        "posts_approved": {"type": "schedule_posts", "route": "/generated-posts"},
        "scheduled": {"type": "publish_posts", "route": "/generated-posts"},
        "published": {"type": "add_metrics", "route": "/generated-posts"},
        "metrics_added": {"type": "view_recommendations", "route": "/dashboard"},
        "recommendations_ready": {"type": "view_recommendations", "route": "/dashboard"},
    }
    return actions.get(state, {"type": "open_dashboard", "route": "/dashboard"})


async def build_lifecycle(session: AsyncSession, user_id: str) -> dict[str, Any]:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user_id})
    interview_rows = await fetch_all(
        session,
        "SELECT status, COUNT(*) AS count FROM interview_sessions WHERE user_id = :user_id GROUP BY status",
        {"user_id": user_id},
    )
    trend_count = await fetch_one(
        session,
        "SELECT COUNT(*) AS count FROM trends WHERE user_id = :user_id AND expires_at > NOW()",
        {"user_id": user_id},
    )
    latest_plan = await fetch_one(
        session,
        "SELECT id, status FROM content_plans WHERE user_id = :user_id ORDER BY created_at DESC LIMIT 1",
        {"user_id": user_id},
    )
    plan_count = await fetch_one(session, "SELECT COUNT(*) AS count FROM content_plans WHERE user_id = :user_id", {"user_id": user_id})
    post_rows = await fetch_all(
        session,
        "SELECT status, COUNT(*) AS count FROM generated_posts WHERE user_id = :user_id GROUP BY status",
        {"user_id": user_id},
    )
    schedule_rows = await fetch_all(
        session,
        "SELECT status, COUNT(*) AS count FROM scheduled_posts WHERE user_id = :user_id GROUP BY status",
        {"user_id": user_id},
    )
    metrics = await fetch_one(session, "SELECT COUNT(*) AS count FROM post_metrics WHERE user_id = :user_id", {"user_id": user_id})

    counts = {
        "interviews_in_progress": _status_count(interview_rows, "in_progress"),
        "interviews_completed": _status_count(interview_rows, "completed"),
        "trends": _as_int((trend_count or {}).get("count")),
        "content_plans": _as_int((plan_count or {}).get("count")),
        "generated_posts": sum(_as_int(row.get("count")) for row in post_rows),
        "draft_or_edited_posts": _status_count(post_rows, "draft") + _status_count(post_rows, "edited"),
        "approved_posts": _status_count(post_rows, "approved"),
        "scheduled_posts": _status_count(post_rows, "scheduled") + _status_count(schedule_rows, "scheduled") + _status_count(schedule_rows, "publishing"),
        "published_posts": _status_count(post_rows, "published") + _status_count(schedule_rows, "published"),
        "metrics_rows": _as_int((metrics or {}).get("count")),
    }

    confirmations = {
        "profile": {
            "status": (profile or {}).get("profile_confirmation_status") or "draft",
            "confirmed_at": (profile or {}).get("profile_confirmed_at"),
        },
        "audience": {
            "status": (profile or {}).get("audience_confirmation_status") or "draft",
            "confirmed_at": (profile or {}).get("audience_confirmed_at"),
        },
    }
    has_profile = profile_has_meaningful_fields(profile)
    has_audience = bool(profile and _has_text(profile.get("audience")))

    completed: set[str] = {"registered"}
    current = "registered"
    if counts["interviews_in_progress"]:
        current = "onboarding_in_progress"
        completed.add("onboarding_in_progress")
    if has_profile:
        completed.add("profile_generated")
        current = "profile_generated"
    if has_profile and (
        confirmations["profile"]["status"] != "confirmed"
        or (has_audience and confirmations["audience"]["status"] != "confirmed")
    ):
        current = "profile_needs_confirmation"
    elif has_profile:
        completed.add("profile_confirmed")
        current = "profile_confirmed"
        if counts["trends"] > 0:
            completed.add("trends_ready")
            current = "trends_ready"
        if counts["content_plans"] > 0:
            completed.add("content_plan_ready")
            current = "content_plan_ready"
            if latest_plan and latest_plan.get("status") == "draft":
                current = "content_plan_needs_approval"
            elif latest_plan and latest_plan.get("status") in {"approved", "active"}:
                completed.add("content_plan_approved")
                current = "content_plan_approved"
        if counts["generated_posts"] > 0:
            completed.add("posts_generated")
            current = "posts_generated"
            if counts["draft_or_edited_posts"] > 0:
                current = "posts_ready_for_review"
            if counts["approved_posts"] > 0:
                completed.add("posts_approved")
                current = "posts_approved"
        if counts["scheduled_posts"] > 0:
            completed.add("scheduled")
            current = "scheduled"
        if counts["published_posts"] > 0:
            completed.add("published")
            current = "published"
        if counts["metrics_rows"] > 0:
            completed.add("metrics_added")
            current = "metrics_added"
        if counts["metrics_rows"] >= 3:
            completed.add("recommendations_ready")
            current = "recommendations_ready"

    if current == "content_plan_needs_approval":
        completed.add("content_plan_ready")
    if current == "posts_ready_for_review":
        completed.add("posts_generated")

    latest_plan_id = str(latest_plan["id"]) if latest_plan and latest_plan.get("id") else None
    steps = [
        {
            "key": key,
            "status": "current" if key == current else "completed" if key in completed else "upcoming",
            "route": _action_for_state(key, latest_plan_id).get("route"),
            "action": _action_for_state(key, latest_plan_id).get("type"),
        }
        for key in LIFECYCLE_ORDER
    ]
    return {
        "current_state": current,
        "completed_states": [key for key in LIFECYCLE_ORDER if key in completed],
        "steps": steps,
        "next_action": _action_for_state(current, latest_plan_id),
        "confirmations": confirmations,
        "counts": {**counts, "latest_content_plan_id": latest_plan_id, "latest_content_plan_status": latest_plan.get("status") if latest_plan else None},
    }
