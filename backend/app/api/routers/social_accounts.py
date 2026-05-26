from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_session
from app.schemas.common import ManualSocialAccountCreate
from app.services.social_account_service import create_manual_social_account, list_social_accounts

router = APIRouter(prefix="/social-accounts", tags=["social_accounts"])


@router.get("")
async def list_accounts(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await list_social_accounts(session, str(user["id"]))


@router.post("/manual")
async def create_manual_account(payload: ManualSocialAccountCreate, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    account = await create_manual_social_account(
        session,
        str(user["id"]),
        platform=payload.platform,
        display_name=payload.display_name,
        account_url=payload.account_url,
        external_account_id=payload.external_account_id,
    )
    await session.commit()
    return account
