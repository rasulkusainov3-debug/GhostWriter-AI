from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_session
from app.services.analytics_context_service import recommendations_for_user
from app.services.analytics_service import (
    get_content_plan_analytics,
    get_dashboard_analytics,
    get_posts_analytics,
    get_profile_analytics,
    get_social_account_analytics,
    get_social_analytics,
    get_trend_analytics,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
async def dashboard_analytics(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return await get_dashboard_analytics(session, str(user["id"]))


@router.get("/profile")
async def profile_analytics(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return await get_profile_analytics(session, str(user["id"]))


@router.get("/social")
async def social_analytics(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return await get_social_analytics(session, str(user["id"]))


@router.get("/trends")
async def trend_analytics(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return await get_trend_analytics(session, str(user["id"]))


@router.get("/posts")
async def posts_analytics(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return await get_posts_analytics(session, str(user["id"]))


@router.get("/content-plans")
async def content_plans_analytics(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return await get_content_plan_analytics(session, str(user["id"]))


@router.get("/social-accounts")
async def social_accounts_analytics(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return await get_social_account_analytics(session, str(user["id"]))


@router.get("/recommendations")
async def recommendations(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return await recommendations_for_user(session, str(user["id"]))
