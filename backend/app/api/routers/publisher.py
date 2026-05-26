from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_session
from app.services.publisher_worker import run_due_telegram_for_user

router = APIRouter(prefix="/publisher", tags=["publisher"])


@router.post("/run-due")
async def run_due_publisher(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    result = await run_due_telegram_for_user(session, str(user["id"]))
    await session.commit()
    return result
