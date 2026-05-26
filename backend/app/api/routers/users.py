from fastapi import APIRouter, Depends

from app.api.deps import current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_me(user: dict = Depends(current_user)) -> dict:
    return user
