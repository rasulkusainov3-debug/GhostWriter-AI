from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import execute, fetch_all, fetch_one, get_session
from app.schemas.common import InterviewAnswer
from app.services.onboarding_flow import finish_onboarding_flow
from app.services.social_analyzer_adapter import adapter

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/start")
async def start_interview(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    existing = await fetch_one(
        session,
        """
        SELECT *
        FROM interview_sessions
        WHERE user_id = :user_id AND status = 'in_progress'
        ORDER BY started_at DESC
        LIMIT 1
        """,
        {"user_id": user["id"]},
    )
    if existing:
        return {"session": existing, "questions": adapter.onboarding_questions()}
    interview = await fetch_one(
        session,
        """
        INSERT INTO interview_sessions (user_id, status, dialogues)
        VALUES (:user_id, 'in_progress', CAST(:dialogues AS JSONB))
        RETURNING *
        """,
        {"user_id": user["id"], "dialogues": []},
    )
    await session.commit()
    return {"session": interview, "questions": adapter.onboarding_questions()}


@router.get("/{session_id}")
async def get_state(session_id: str, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    interview = await fetch_one(
        session,
        "SELECT * FROM interview_sessions WHERE id = :id AND user_id = :user_id",
        {"id": session_id, "user_id": user["id"]},
    )
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    return {"session": interview, "questions": adapter.onboarding_questions()}


@router.post("/{session_id}/answers")
async def submit_answer(
    session_id: str,
    payload: InterviewAnswer,
    user: dict = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    interview = await fetch_one(
        session,
        "SELECT * FROM interview_sessions WHERE id = :id AND user_id = :user_id",
        {"id": session_id, "user_id": user["id"]},
    )
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    dialogues = interview.get("dialogues") or []
    dialogues.append({"role": "user", "key": payload.key, "text": payload.answer, "ts": datetime.now(timezone.utc).isoformat()})
    await execute(session, "UPDATE interview_sessions SET dialogues = CAST(:dialogues AS JSONB) WHERE id = :id", {"dialogues": dialogues, "id": session_id})
    await session.commit()
    return {"session_id": session_id, "dialogues": dialogues}


@router.post("/{session_id}/finish")
async def finish_interview(session_id: str, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    interview = await fetch_one(
        session,
        "SELECT * FROM interview_sessions WHERE id = :id AND user_id = :user_id",
        {"id": session_id, "user_id": user["id"]},
    )
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    answers = {item["key"]: item["text"] for item in interview.get("dialogues", []) if item.get("role") == "user" and item.get("key")}
    result = await finish_onboarding_flow(session, str(user["id"]), answers, session_id)
    await session.commit()
    return result


@router.get("")
async def list_interviews(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await fetch_all(session, "SELECT * FROM interview_sessions WHERE user_id = :user_id ORDER BY started_at DESC", {"user_id": user["id"]})
