from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import execute, fetch_all, fetch_one, get_session
from app.schemas.common import ContentPlanCreate, ContentPlanItemUpdate, StatusUpdate
from app.services.content_plan_service import add_trend_to_draft_plan, create_weekly_content_plan, get_content_plan as get_plan_service

router = APIRouter(prefix="/content-plans", tags=["content_plans"])

CONTENT_PLAN_STATUSES = {"draft", "approved", "active", "archived"}
CONTENT_PLAN_ITEM_STATUSES = {"planned", "generating", "generated", "skipped"}


@router.post("")
async def create_content_plan(payload: ContentPlanCreate, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user["id"]})
    result = await create_weekly_content_plan(session, str(user["id"]), profile, payload.title, payload.posts_per_week, payload.week_start)
    await session.commit()
    return result


@router.get("")
async def list_content_plans(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await fetch_all(
        session,
        """
        SELECT
            cp.*,
            COUNT(DISTINCT cpi.id) AS items_count,
            COUNT(DISTINCT gp.id) AS generated_posts_count,
            COUNT(DISTINCT gp.id) FILTER (WHERE gp.status = 'approved') AS approved_posts_count,
            COUNT(DISTINCT gp.id) FILTER (WHERE gp.status = 'scheduled') AS scheduled_posts_count,
            COUNT(DISTINCT gp.id) FILTER (WHERE gp.status = 'published') AS published_posts_count
        FROM content_plans cp
        LEFT JOIN content_plan_items cpi ON cpi.plan_id = cp.id
        LEFT JOIN generated_posts gp ON gp.plan_item_id = cpi.id AND gp.user_id = cp.user_id
        WHERE cp.user_id = :user_id
        GROUP BY cp.id
        ORDER BY cp.created_at DESC
        """,
        {"user_id": user["id"]},
    )


@router.get("/{plan_id}")
async def get_content_plan(plan_id: str, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return await get_plan_service(session, str(user["id"]), plan_id)


@router.post("/from-trend/{trend_id}")
async def add_trend_to_plan(trend_id: int, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user["id"]})
    result = await add_trend_to_draft_plan(session, str(user["id"]), trend_id, profile)
    await session.commit()
    return result


@router.patch("/items/{item_id}")
async def update_item(item_id: str, payload: ContentPlanItemUpdate, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    if payload.status is not None and payload.status not in CONTENT_PLAN_ITEM_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unsupported content plan item status: {payload.status}")
    item = await fetch_one(
        session,
        """
        SELECT cpi.* FROM content_plan_items cpi
        JOIN content_plans cp ON cp.id = cpi.plan_id
        WHERE cpi.id = :id AND cp.user_id = :user_id
        """,
        {"id": item_id, "user_id": user["id"]},
    )
    if not item:
        raise HTTPException(status_code=404, detail="Plan item not found")
    merged = {**item, **payload.model_dump(exclude_unset=True)}
    await execute(
        session,
        """
        UPDATE content_plan_items
        SET platform=:platform, format=:format, post_idea=:post_idea,
            scheduled_date=:scheduled_date, scheduled_time=:scheduled_time, status=:status
        WHERE id=:id
        """,
        {**merged, "id": item_id},
    )
    await execute(
        session,
        """
        UPDATE content_plans
        SET status = 'draft'
        WHERE id = :plan_id
          AND user_id = :user_id
          AND status IN ('approved', 'active')
        """,
        {"plan_id": item["plan_id"], "user_id": user["id"]},
    )
    await session.commit()
    return await fetch_one(session, "SELECT * FROM content_plan_items WHERE id = :id", {"id": item_id})


@router.patch("/{plan_id}/status")
async def update_plan_status(plan_id: str, payload: StatusUpdate, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    if payload.status not in CONTENT_PLAN_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unsupported content plan status: {payload.status}")
    await execute(
        session,
        "UPDATE content_plans SET status = :status WHERE id = :id AND user_id = :user_id",
        {"status": payload.status, "id": plan_id, "user_id": user["id"]},
    )
    await session.commit()
    return await get_content_plan(plan_id, user, session)


@router.get("/{plan_id}/analytics")
async def plan_analytics(plan_id: str, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    rows = await fetch_all(
        session,
        """
        SELECT cpi.platform, cpi.status, COUNT(*) AS count
        FROM content_plan_items cpi
        JOIN content_plans cp ON cp.id = cpi.plan_id
        WHERE cp.id = :plan_id AND cp.user_id = :user_id
        GROUP BY cpi.platform, cpi.status
        """,
        {"plan_id": plan_id, "user_id": user["id"]},
    )
    metrics = await fetch_one(
        session,
        """
        SELECT
            COUNT(pm.id) AS metrics_rows,
            COUNT(DISTINCT gp.id) AS posts_with_metrics,
            COALESCE(SUM(pm.impressions), 0) AS total_impressions,
            COALESCE(SUM(pm.views), 0) AS total_views,
            COALESCE(SUM(pm.likes + pm.comments + pm.shares + pm.saves + pm.clicks + pm.reactions), 0) AS total_engagements,
            COALESCE(AVG(pm.engagement_rate), 0) AS average_engagement_rate
        FROM content_plan_items cpi
        JOIN content_plans cp ON cp.id = cpi.plan_id
        JOIN generated_posts gp ON gp.plan_item_id = cpi.id AND gp.user_id = cp.user_id
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        WHERE cp.id = :plan_id AND cp.user_id = :user_id
        """,
        {"plan_id": plan_id, "user_id": user["id"]},
    )
    best_platforms = await fetch_all(
        session,
        """
        SELECT
            cpi.platform,
            COALESCE(AVG(pm.engagement_rate), 0) AS average_engagement_rate,
            COALESCE(SUM(pm.views), 0) AS total_views,
            COALESCE(SUM(pm.impressions), 0) AS total_impressions
        FROM content_plan_items cpi
        JOIN content_plans cp ON cp.id = cpi.plan_id
        JOIN generated_posts gp ON gp.plan_item_id = cpi.id AND gp.user_id = cp.user_id
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        WHERE cp.id = :plan_id AND cp.user_id = :user_id
        GROUP BY cpi.platform
        ORDER BY average_engagement_rate DESC, total_views DESC, total_impressions DESC
        LIMIT 5
        """,
        {"plan_id": plan_id, "user_id": user["id"]},
    )
    return {"plan_id": plan_id, "breakdown": rows, "manual_metrics": metrics or {}, "best_platforms": best_platforms}
