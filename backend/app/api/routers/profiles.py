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
from app.services.style_context_service import get_style_examples

router = APIRouter(prefix="/profiles", tags=["profiles"])


PERSONALITY_STRING_FIELDS = {"voice", "writing_style"}
PERSONALITY_LIST_FIELDS = {"preferred_structure", "vocabulary_preferences", "avoid_phrases", "example_post_ids"}


def _clean_text(value: object, limit: int = 1000) -> str:
    return " ".join(str(value or "").split())[:limit]


def _clean_string_list(value: object, max_items: int = 30, item_limit: int = 120) -> list[str]:
    if isinstance(value, str):
        items = [item.strip() for item in value.replace("\n", ",").split(",")]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        items = []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = " ".join(item.split())[:item_limit]
        key = normalized.lower()
        if normalized and key not in seen:
            cleaned.append(normalized)
            seen.add(key)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _sanitize_personality(value: object, existing: dict | None = None) -> dict:
    current = dict(existing or {})
    incoming = value if isinstance(value, dict) else {}
    for field in PERSONALITY_STRING_FIELDS:
        if field in incoming:
            current[field] = _clean_text(incoming.get(field))
    for field in PERSONALITY_LIST_FIELDS:
        if field in incoming:
            current[field] = _clean_string_list(incoming.get(field))
    return current


def _merge_raw_answers(current_raw: object, incoming_raw: object) -> dict:
    current = dict(current_raw or {}) if isinstance(current_raw, dict) else {}
    incoming = dict(incoming_raw or {}) if isinstance(incoming_raw, dict) else {}
    merged = {**current, **{key: value for key, value in incoming.items() if key != "personality"}}
    if "personality" in incoming:
        merged["personality"] = _sanitize_personality(incoming.get("personality"), current.get("personality") if isinstance(current.get("personality"), dict) else {})
    return merged


async def _attach_style_count(session: AsyncSession, user_id: str, profile: dict) -> dict:
    examples = await get_style_examples(session, user_id)
    return {**profile, "style_examples_count": len(examples)}


@router.get("/me")
async def get_profile(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return await _attach_style_count(session, str(user["id"]), profile)


@router.patch("/me")
async def update_profile(payload: ProfileUpdate, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    current = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user["id"]})
    if not current:
        raise HTTPException(status_code=404, detail="Profile not found")
    data = payload.model_dump(exclude_unset=True)
    if "raw_answers" in data:
        data["raw_answers"] = _merge_raw_answers(current.get("raw_answers"), data.get("raw_answers"))
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
