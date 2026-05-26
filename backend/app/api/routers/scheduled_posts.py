from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_session
from app.services.scheduling_service import cancel_scheduled_post, get_scheduled_post, list_scheduled_posts

router = APIRouter(prefix="/scheduled-posts", tags=["scheduled_posts"])


@router.get("")
async def list_schedules(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await list_scheduled_posts(session, str(user["id"]))


@router.get("/{schedule_id}")
async def get_schedule(schedule_id: str, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return await get_scheduled_post(session, str(user["id"]), schedule_id)


@router.patch("/{schedule_id}/cancel")
async def cancel_schedule(schedule_id: str, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    schedule = await cancel_scheduled_post(session, str(user["id"]), schedule_id)
    await session.commit()
    return schedule
