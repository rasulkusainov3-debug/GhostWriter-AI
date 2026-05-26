from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import fetch_all, fetch_one
from app.schemas.common import PostMetricsUpsertRequest
from app.services.run_tracking_service import save_generation_run

METRIC_FIELDS = ("impressions", "reach", "views", "likes", "comments", "shares", "saves", "clicks", "reactions")


def calculate_engagement_rate(payload: PostMetricsUpsertRequest | dict[str, Any]) -> float:
    data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    if data.get("engagement_rate") is not None:
        return round(float(data["engagement_rate"]), 4)
    engagements = sum(int(data.get(field) or 0) for field in ("likes", "comments", "shares", "saves", "clicks", "reactions"))
    denominator = max(int(data.get("impressions") or 0), int(data.get("reach") or 0), int(data.get("views") or 0), 1)
    return round((engagements / denominator) * 100, 4)


async def _owned_post(session: AsyncSession, user_id: str, post_id: str) -> dict[str, Any]:
    post = await fetch_one(
        session,
        "SELECT * FROM generated_posts WHERE id = :id AND user_id = :user_id",
        {"id": post_id, "user_id": user_id},
    )
    if not post:
        raise HTTPException(status_code=404, detail="Generated post not found")
    return post


async def _validate_schedule(session: AsyncSession, user_id: str, post_id: str, scheduled_post_id: str | None) -> None:
    if not scheduled_post_id:
        return
    schedule = await fetch_one(
        session,
        """
        SELECT id
        FROM scheduled_posts
        WHERE id = :id
          AND user_id = :user_id
          AND generated_post_id = :post_id
        """,
        {"id": scheduled_post_id, "user_id": user_id, "post_id": post_id},
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Scheduled post not found for this generated post")


async def list_post_metrics(session: AsyncSession, user_id: str, post_id: str) -> list[dict[str, Any]]:
    await _owned_post(session, user_id, post_id)
    return await fetch_all(
        session,
        """
        SELECT *
        FROM post_metrics
        WHERE user_id = :user_id
          AND generated_post_id = :post_id
        ORDER BY metric_date DESC, updated_at DESC
        """,
        {"user_id": user_id, "post_id": post_id},
    )


async def upsert_manual_post_metrics(session: AsyncSession, user_id: str, post_id: str, payload: PostMetricsUpsertRequest) -> dict[str, Any]:
    post = await _owned_post(session, user_id, post_id)
    if payload.source != "manual":
        raise HTTPException(status_code=422, detail="Only manual metrics are supported")
    scheduled_post_id = str(payload.scheduled_post_id) if payload.scheduled_post_id else None
    await _validate_schedule(session, user_id, post_id, scheduled_post_id)
    platform = (payload.platform or post.get("platform") or "").strip()
    if not platform:
        raise HTTPException(status_code=422, detail="Platform is required")
    values = payload.model_dump()
    engagement_rate = calculate_engagement_rate(payload)
    row = await fetch_one(
        session,
        """
        INSERT INTO post_metrics
            (user_id, generated_post_id, scheduled_post_id, platform, metric_date, source,
             impressions, reach, views, likes, comments, shares, saves, clicks, reactions,
             engagement_rate, raw_metrics)
        VALUES
            (:user_id, :generated_post_id, :scheduled_post_id, :platform, :metric_date, 'manual',
             :impressions, :reach, :views, :likes, :comments, :shares, :saves, :clicks, :reactions,
             :engagement_rate, CAST(:raw_metrics AS JSONB))
        ON CONFLICT (user_id, generated_post_id, platform, metric_date, source)
        DO UPDATE SET
            scheduled_post_id = EXCLUDED.scheduled_post_id,
            impressions = EXCLUDED.impressions,
            reach = EXCLUDED.reach,
            views = EXCLUDED.views,
            likes = EXCLUDED.likes,
            comments = EXCLUDED.comments,
            shares = EXCLUDED.shares,
            saves = EXCLUDED.saves,
            clicks = EXCLUDED.clicks,
            reactions = EXCLUDED.reactions,
            engagement_rate = EXCLUDED.engagement_rate,
            raw_metrics = EXCLUDED.raw_metrics
        RETURNING *
        """,
        {
            "user_id": user_id,
            "generated_post_id": post_id,
            "scheduled_post_id": scheduled_post_id,
            "platform": platform,
            "metric_date": payload.metric_date,
            "impressions": values["impressions"],
            "reach": values["reach"],
            "views": values["views"],
            "likes": values["likes"],
            "comments": values["comments"],
            "shares": values["shares"],
            "saves": values["saves"],
            "clicks": values["clicks"],
            "reactions": values["reactions"],
            "engagement_rate": engagement_rate,
            "raw_metrics": payload.raw_metrics,
        },
    )
    await save_generation_run(
        session,
        user_id=user_id,
        run_type="manual_metrics_upsert",
        provider=None,
        agent_name="post_metrics_service",
        input_payload={
            "generated_post_id": post_id,
            "scheduled_post_id": scheduled_post_id,
            "platform": platform,
            "metric_date": payload.metric_date.isoformat(),
            "source": "manual",
        },
        output_payload={
            "metric_id": str(row["id"]) if row else None,
            "engagement_rate": engagement_rate,
        },
        status="completed",
    )
    return row or {}


async def delete_post_metrics(session: AsyncSession, user_id: str, post_id: str, metric_id: str) -> dict[str, Any]:
    await _owned_post(session, user_id, post_id)
    row = await fetch_one(
        session,
        """
        DELETE FROM post_metrics
        WHERE id = :metric_id
          AND generated_post_id = :post_id
          AND user_id = :user_id
        RETURNING *
        """,
        {"metric_id": metric_id, "post_id": post_id, "user_id": user_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Post metrics not found")
    await save_generation_run(
        session,
        user_id=user_id,
        run_type="manual_metrics_delete",
        provider=None,
        agent_name="post_metrics_service",
        input_payload={"metric_id": metric_id, "generated_post_id": post_id},
        output_payload={"metric_id": metric_id, "deleted": True},
        status="completed",
    )
    return row
