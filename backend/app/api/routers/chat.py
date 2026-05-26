from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import fetch_one, get_session
from app.schemas.common import ChatMessageRequest
from app.services.chat.orchestrator import run_chat_pipeline, visible_messages
from app.services.lifecycle_service import build_lifecycle

router = APIRouter(prefix="/chat", tags=["chat"])


async def _load_profile(session: AsyncSession, user_id: str) -> dict[str, Any] | None:
    return await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user_id})


@router.post("")
async def chat(payload: ChatMessageRequest, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    try:
        return await run_chat_pipeline(session, user, payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Chat action failed. Please try again.") from exc


@router.get("")
async def get_chat(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    profile = await _load_profile(session, str(user["id"]))
    lifecycle = await build_lifecycle(session, str(user["id"]))
    raw_answers = (profile or {}).get("raw_answers") or {}
    messages = raw_answers.get("chat_dialogues", [])
    if profile and not messages:
        messages = [
            {
                "role": "assistant",
                "text": (
                    "Готов работать с агентами GhostWriter AI. Можно написать: "
                    "«Найди новые тренды», «Покажи тренды», «Сделай контент-план на неделю», "
                    "«Сгенерируй посты», «Измени тон на экспертный»."
                ),
                "ts": datetime.now(timezone.utc).isoformat(),
                "intent": "general_chat",
                "action": {"type": "general_chat", "status": "ready"},
            }
        ]
    return {"messages": visible_messages(messages), "profile": profile, "lifecycle": lifecycle}
