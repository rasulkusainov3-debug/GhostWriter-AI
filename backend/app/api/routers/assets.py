from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import fetch_all, get_session

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
async def list_assets(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    assets = await fetch_all(
        session,
        """
        SELECT pa.*
        FROM post_assets pa
        WHERE pa.user_id = :user_id
        ORDER BY pa.created_at DESC
        LIMIT 100
        """,
        {"user_id": user["id"]},
    )
    return {
        "assets": assets,
        "message": "Post visual ideas and remote image metadata. Binary image storage is not enabled yet.",
    }
