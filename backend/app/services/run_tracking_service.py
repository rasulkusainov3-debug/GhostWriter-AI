from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import execute, fetch_one


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (UUID, datetime, date, Decimal)):
        return str(value)
    return value


async def start_trend_run(session: AsyncSession, user_id: str, profile_snapshot: dict[str, Any]) -> dict[str, Any]:
    return await fetch_one(
        session,
        """
        INSERT INTO trend_runs (user_id, status, input_profile_snapshot)
        VALUES (:user_id, 'running', CAST(:input_profile_snapshot AS JSONB))
        RETURNING *
        """,
        {"user_id": user_id, "input_profile_snapshot": _json_safe(profile_snapshot or {})},
    ) or {}


async def finish_trend_run(
    session: AsyncSession,
    run_id: str,
    queries_used: list[str],
    raw_posts_found: int,
    trends_found: int,
) -> dict[str, Any]:
    return await fetch_one(
        session,
        """
        UPDATE trend_runs
        SET status='completed',
            queries_used=CAST(:queries_used AS JSONB),
            raw_posts_found=:raw_posts_found,
            trends_found=:trends_found,
            finished_at=NOW(),
            error_message=NULL
        WHERE id=:id
        RETURNING *
        """,
        {
            "id": run_id,
            "queries_used": _json_safe(queries_used),
            "raw_posts_found": raw_posts_found,
            "trends_found": trends_found,
        },
    ) or {}


async def fail_trend_run(
    session: AsyncSession,
    run_id: str,
    error_message: str,
    queries_used: list[str] | None = None,
    raw_posts_found: int = 0,
    trends_found: int = 0,
) -> dict[str, Any]:
    return await fetch_one(
        session,
        """
        UPDATE trend_runs
        SET status='failed',
            queries_used=CAST(:queries_used AS JSONB),
            raw_posts_found=:raw_posts_found,
            trends_found=:trends_found,
            finished_at=NOW(),
            error_message=:error_message
        WHERE id=:id
        RETURNING *
        """,
        {
            "id": run_id,
            "queries_used": _json_safe(queries_used or []),
            "raw_posts_found": raw_posts_found,
            "trends_found": trends_found,
            "error_message": error_message[:1000],
        },
    ) or {}


async def save_generation_run(
    session: AsyncSession,
    user_id: str,
    run_type: str,
    provider: str | None,
    agent_name: str,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any],
    status: str = "completed",
    error_message: str | None = None,
) -> dict[str, Any]:
    return await fetch_one(
        session,
        """
        INSERT INTO generation_runs
            (user_id, run_type, provider, agent_name, input_payload, output_payload, status, error_message)
        VALUES
            (:user_id, :run_type, :provider, :agent_name, CAST(:input_payload AS JSONB),
             CAST(:output_payload AS JSONB), :status, :error_message)
        RETURNING *
        """,
        {
            "user_id": user_id,
            "run_type": run_type,
            "provider": provider,
            "agent_name": agent_name,
            "input_payload": _json_safe(input_payload or {}),
            "output_payload": _json_safe(output_payload or {}),
            "status": status,
            "error_message": error_message[:1000] if error_message else None,
        },
    ) or {}


async def link_trend_sources(
    session: AsyncSession,
    trend_id: int,
    raw_post_ids: list[int],
    relevance_score: float | None = None,
) -> None:
    for raw_post_id in raw_post_ids:
        await execute(
            session,
            """
            INSERT INTO trend_sources (trend_id, raw_post_id, relevance_score)
            VALUES (:trend_id, :raw_post_id, :relevance_score)
            ON CONFLICT (trend_id, raw_post_id) DO NOTHING
            """,
            {
                "trend_id": trend_id,
                "raw_post_id": raw_post_id,
                "relevance_score": relevance_score or 0,
            },
        )
