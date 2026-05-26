from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import fetch_all, fetch_one, get_session
from app.services.trend_service import find_and_save_trends

router = APIRouter(prefix="/trends", tags=["trends"])


@router.post("/generate")
async def generate_trends(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user["id"]})
    if not profile:
        return {"status": "needs_profile", "message": "Complete onboarding/profile before trend generation."}
    result = await find_and_save_trends(session, str(user["id"]), profile, run_legacy=True)
    await session.commit()
    return result


@router.get("")
async def list_active_trends(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await fetch_all(
        session,
        """
        SELECT *
        FROM trends
        WHERE user_id = :user_id AND expires_at > NOW()
        ORDER BY final_score DESC
        LIMIT 50
        """,
        {"user_id": user["id"]},
    )


@router.get("/{trend_id}")
async def get_trend(trend_id: int, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict | None:
    trend = await fetch_one(
        session,
        "SELECT * FROM trends WHERE id = :id AND user_id = :user_id",
        {"id": trend_id, "user_id": user["id"]},
    )
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    return trend


@router.post("/cleanup")
async def cleanup_expired(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    row = await fetch_one(session, "SELECT cleanup_expired_trends() AS deleted_count")
    await session.commit()
    return row or {"deleted_count": 0}
