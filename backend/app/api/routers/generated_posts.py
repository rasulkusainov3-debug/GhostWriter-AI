from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import fetch_all, fetch_one, get_session
from app.schemas.common import GeneratePostFromTrendRequest, GeneratePostsRequest, GeneratedPostUpdate, PostMetricsUpsertRequest, SchedulePostRequest
from app.services.post_asset_service import (
    enrich_generated_post,
    enrich_generated_posts,
    generate_visual_for_post,
    list_post_assets,
    select_post_asset,
)
from app.services.post_generation_service import (
    generate_post_from_trend_id,
    generate_posts_for_plan,
    regenerate_post as regenerate_post_service,
    update_generated_post as update_generated_post_service,
)
from app.services.post_metrics_service import delete_post_metrics, list_post_metrics, upsert_manual_post_metrics
from app.services.scheduling_service import schedule_generated_post

router = APIRouter(prefix="/generated-posts", tags=["generated_posts"])


@router.post("/from-plan/{plan_id}")
async def generate_from_plan(plan_id: str, payload: GeneratePostsRequest, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=409, detail="Complete onboarding first")
    wanted = {str(item_id) for item_id in payload.item_ids} if payload.item_ids else None
    result = await generate_posts_for_plan(
        session,
        str(user["id"]),
        profile,
        plan_id,
        use_llm=payload.use_llm,
        item_ids=wanted,
        language=payload.language,
    )
    await session.commit()
    result["created"] = await enrich_generated_posts(session, str(user["id"]), result.get("created", []))
    return result


@router.post("/from-trend/{trend_id}")
async def generate_from_trend(trend_id: int, payload: GeneratePostFromTrendRequest, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=409, detail="Complete onboarding first")
    result = await generate_post_from_trend_id(
        session,
        str(user["id"]),
        profile,
        trend_id,
        platform=payload.platform,
        format=payload.format,
        use_llm=payload.use_llm,
        language=payload.language,
    )
    await session.commit()
    result["post"] = await enrich_generated_post(session, str(user["id"]), result.get("post"))
    return result


@router.get("")
async def list_generated_posts(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
    posts = await fetch_all(session, "SELECT * FROM generated_posts WHERE user_id = :user_id ORDER BY generated_at DESC", {"user_id": user["id"]})
    return await enrich_generated_posts(session, str(user["id"]), posts)


@router.get("/{post_id}/assets")
async def list_assets_for_post(post_id: str, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return {"assets": await list_post_assets(session, str(user["id"]), post_id)}


@router.get("/{post_id}/metrics")
async def list_metrics_for_post(post_id: str, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return {"metrics": await list_post_metrics(session, str(user["id"]), post_id)}


@router.post("/{post_id}/metrics/manual")
async def upsert_metrics_for_post(post_id: str, payload: PostMetricsUpsertRequest, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    metric = await upsert_manual_post_metrics(session, str(user["id"]), post_id, payload)
    await session.commit()
    return {"metric": metric}


@router.delete("/{post_id}/metrics/{metric_id}")
async def delete_metrics_for_post(post_id: str, metric_id: str, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    await delete_post_metrics(session, str(user["id"]), post_id, metric_id)
    await session.commit()
    return {"ok": True}


@router.post("/{post_id}/assets/generate")
async def generate_asset_for_post(post_id: str, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    result = await generate_visual_for_post(session, str(user["id"]), post_id)
    await session.commit()
    return result


@router.patch("/{post_id}/assets/{asset_id}/select")
async def select_asset_for_post(post_id: str, asset_id: str, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    result = await select_post_asset(session, str(user["id"]), post_id, asset_id)
    await session.commit()
    return result


@router.get("/{post_id}")
async def get_generated_post(post_id: str, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    post = await fetch_one(session, "SELECT * FROM generated_posts WHERE id = :id AND user_id = :user_id", {"id": post_id, "user_id": user["id"]})
    if not post:
        raise HTTPException(status_code=404, detail="Generated post not found")
    return await enrich_generated_post(session, str(user["id"]), post)


@router.patch("/{post_id}")
async def update_generated_post(post_id: str, payload: GeneratedPostUpdate, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    updated = await update_generated_post_service(
        session,
        str(user["id"]),
        post_id,
        draft_text=payload.draft_text,
        final_text=payload.final_text,
        status=payload.status,
    )
    await session.commit()
    return await enrich_generated_post(session, str(user["id"]), updated)


@router.post("/{post_id}/schedule")
async def schedule_post(post_id: str, payload: SchedulePostRequest, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    schedule = await schedule_generated_post(
        session,
        str(user["id"]),
        post_id,
        platform=payload.platform,
        scheduled_for=payload.scheduled_for,
        social_account_id=str(payload.social_account_id) if payload.social_account_id else None,
        selected_asset_id=str(payload.selected_asset_id) if payload.selected_asset_id else None,
    )
    await session.commit()
    post = await fetch_one(session, "SELECT * FROM generated_posts WHERE id = :id AND user_id = :user_id", {"id": post_id, "user_id": user["id"]})
    return {"schedule": schedule, "post": await enrich_generated_post(session, str(user["id"]), post)}


@router.post("/{post_id}/regenerate")
async def regenerate_post(post_id: str, payload: GeneratePostsRequest, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=409, detail="Cannot regenerate without profile")
    post = await regenerate_post_service(
        session,
        str(user["id"]),
        post_id,
        profile,
        use_llm=payload.use_llm,
        mode=payload.mode,
        language=payload.language,
    )
    await session.commit()
    return await enrich_generated_post(session, str(user["id"]), post)
