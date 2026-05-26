from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import execute, fetch_one, get_session
from app.schemas.common import ProfileUpdate
from app.services.lifecycle_service import (
    AUDIENCE_CONFIRMATION_FIELDS,
    PROFILE_CONFIRMATION_FIELDS,
    mark_audience_needs_confirmation,
    mark_profile_needs_confirmation,
    profile_fields_changed,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me")
async def get_profile(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.patch("/me")
async def update_profile(payload: ProfileUpdate, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    current = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user["id"]})
    if not current:
        raise HTTPException(status_code=404, detail="Profile not found")
    data = payload.model_dump(exclude_unset=True)
    profile_changed = profile_fields_changed(current, data, PROFILE_CONFIRMATION_FIELDS)
    audience_changed = profile_fields_changed(current, data, AUDIENCE_CONFIRMATION_FIELDS)
    merged = {**current, **data}
    await execute(
        session,
        """
        UPDATE user_profiles
        SET name=:name, niche=:niche, profession=:profession, goal=:goal, tone=:tone,
            audience=:audience, avoid=:avoid, user_values=CAST(:user_values AS JSONB),
            platforms=CAST(:platforms AS JSONB), raw_answers=CAST(:raw_answers AS JSONB)
        WHERE user_id=:user_id
        """,
        {
            "user_id": user["id"],
            "name": merged.get("name"),
            "niche": merged.get("niche"),
            "profession": merged.get("profession"),
            "goal": merged.get("goal"),
            "tone": merged.get("tone"),
            "audience": merged.get("audience"),
            "avoid": merged.get("avoid"),
            "user_values": merged.get("user_values") or [],
            "platforms": merged.get("platforms") or [],
            "raw_answers": merged.get("raw_answers") or {},
        },
    )
    if profile_changed:
        await mark_profile_needs_confirmation(session, str(user["id"]))
    if audience_changed:
        await mark_audience_needs_confirmation(session, str(user["id"]))
    await session.commit()
    return await get_profile(user, session)
