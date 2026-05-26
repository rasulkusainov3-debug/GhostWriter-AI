from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_session
from app.schemas.common import LifecycleConfirmRequest
from app.services.lifecycle_service import build_lifecycle, confirm_profile_scope

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])


@router.get("")
async def get_lifecycle(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return await build_lifecycle(session, str(user["id"]))


@router.post("/confirm")
async def confirm_lifecycle_scope(
    payload: LifecycleConfirmRequest,
    user: dict = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await confirm_profile_scope(session, str(user["id"]), payload.scope)
    await session.commit()
    return await build_lifecycle(session, str(user["id"]))
