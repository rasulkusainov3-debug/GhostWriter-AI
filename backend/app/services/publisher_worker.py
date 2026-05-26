from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import execute, fetch_all, fetch_one
from app.services.run_tracking_service import save_generation_run
from app.services.telegram_adapter import TelegramPublishError, sanitize_telegram_error, telegram_adapter

MAX_TELEGRAM_ATTEMPTS = 3


async def due_scheduled_posts(session: AsyncSession, limit: int = 25) -> list[dict]:
    return await fetch_all(
        session,
        """
        SELECT *
        FROM scheduled_posts
        WHERE status = 'scheduled'
          AND scheduled_for <= NOW()
        ORDER BY scheduled_for ASC
        LIMIT :limit
        """,
        {"limit": limit},
    )


async def due_telegram_posts_for_user(session: AsyncSession, user_id: str, limit: int = 25) -> list[dict]:
    return await fetch_all(
        session,
        """
        SELECT sp.*,
               CASE WHEN sa.id IS NULL THEN NULL ELSE row_to_json(sa) END AS social_account
        FROM scheduled_posts sp
        JOIN generated_posts gp ON gp.id = sp.generated_post_id AND gp.user_id = sp.user_id
        LEFT JOIN social_accounts sa ON sa.id = sp.social_account_id AND sa.user_id = sp.user_id
        LEFT JOIN post_assets pa ON pa.id = sp.selected_asset_id AND pa.user_id = sp.user_id AND pa.post_id = sp.generated_post_id
        WHERE sp.user_id = :user_id
          AND sp.platform = 'Telegram'
          AND sp.status = 'scheduled'
          AND sp.scheduled_for <= NOW()
          AND (sp.social_account_id IS NULL OR sa.id IS NOT NULL)
          AND (sp.selected_asset_id IS NULL OR pa.id IS NOT NULL)
        ORDER BY sp.scheduled_for ASC
        LIMIT :limit
        """,
        {"user_id": user_id, "limit": limit},
    )


async def _mark_publishing(session: AsyncSession, user_id: str, schedule_id: str) -> dict | None:
    return await fetch_one(
        session,
        """
        UPDATE scheduled_posts
        SET status = 'publishing', last_attempt_at = NOW(), error_message = NULL
        WHERE id = :id
          AND user_id = :user_id
          AND status = 'scheduled'
        RETURNING *
        """,
        {"id": schedule_id, "user_id": user_id},
    )


async def _mark_published(session: AsyncSession, schedule: dict, result: dict) -> None:
    await execute(
        session,
        """
        UPDATE scheduled_posts
        SET status = 'published',
            published_at = NOW(),
            external_post_id = :external_post_id,
            error_message = NULL
        WHERE id = :id AND user_id = :user_id
        """,
        {
            "id": schedule["id"],
            "user_id": schedule["user_id"],
            "external_post_id": result.get("message_id"),
        },
    )
    await execute(
        session,
        """
        UPDATE generated_posts
        SET status = 'published', published_at = NOW()
        WHERE id = :id AND user_id = :user_id
        """,
        {"id": schedule["generated_post_id"], "user_id": schedule["user_id"]},
    )


async def _mark_failed_or_retry(session: AsyncSession, schedule: dict, error: TelegramPublishError) -> str:
    attempts = int(schedule.get("attempt_count") or 0) + 1
    next_status = "scheduled" if error.transient and attempts < MAX_TELEGRAM_ATTEMPTS else "failed"
    await execute(
        session,
        """
        UPDATE scheduled_posts
        SET status = :status,
            attempt_count = :attempt_count,
            last_attempt_at = NOW(),
            error_message = :error_message
        WHERE id = :id AND user_id = :user_id
        """,
        {
            "id": schedule["id"],
            "user_id": schedule["user_id"],
            "status": next_status,
            "attempt_count": attempts,
            "error_message": sanitize_telegram_error(error),
        },
    )
    return next_status


async def run_due_telegram_for_user(session: AsyncSession, user_id: str, limit: int = 25) -> dict:
    due = await due_telegram_posts_for_user(session, user_id, limit=limit)
    result = {"processed": 0, "published": 0, "failed": 0, "skipped": 0, "dry_run": settings.telegram_dry_run}
    for schedule in due:
        result["processed"] += 1
        locked = await _mark_publishing(session, user_id, str(schedule["id"]))
        if not locked:
            result["skipped"] += 1
            continue
        schedule = {**schedule, **locked}
        try:
            publish_result = await telegram_adapter.publish(schedule)
            await _mark_published(session, schedule, publish_result)
            await save_generation_run(
                session,
                user_id=user_id,
                run_type="telegram_publish",
                provider="telegram",
                agent_name="publisher_worker",
                input_payload={
                    "schedule_id": str(schedule["id"]),
                    "generated_post_id": str(schedule["generated_post_id"]),
                    "platform": schedule["platform"],
                    "dry_run": settings.telegram_dry_run,
                },
                output_payload={
                    "schedule_id": str(schedule["id"]),
                    "status": "published",
                    "method": publish_result.get("method"),
                    "message_id": publish_result.get("message_id"),
                    "dry_run": publish_result.get("dry_run"),
                },
                status="completed",
            )
            result["published"] += 1
        except TelegramPublishError as exc:
            next_status = await _mark_failed_or_retry(session, schedule, exc)
            await save_generation_run(
                session,
                user_id=user_id,
                run_type="telegram_publish",
                provider="telegram",
                agent_name="publisher_worker",
                input_payload={
                    "schedule_id": str(schedule["id"]),
                    "generated_post_id": str(schedule["generated_post_id"]),
                    "platform": schedule["platform"],
                    "dry_run": settings.telegram_dry_run,
                },
                output_payload={"schedule_id": str(schedule["id"]), "status": next_status},
                status="failed",
                error_message=sanitize_telegram_error(exc),
            )
            if next_status == "failed":
                result["failed"] += 1
            else:
                result["skipped"] += 1
    return result
