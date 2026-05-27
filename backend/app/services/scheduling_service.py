from __future__ import annotations
from fastapi.encoders import jsonable_encoder
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import execute, fetch_all, fetch_one
from app.services.run_tracking_service import save_generation_run
from app.services.social_account_service import owned_social_account, public_social_account

ACTIVE_SCHEDULE_STATUSES = {"scheduled", "publishing"}
SCHEDULE_STATUSES = {"scheduled", "publishing", "published", "failed", "cancelled"}
SCHEDULABLE_POST_STATUSES = {"approved", "edited"}

PLATFORM_NAMES = {
    "telegram": "Telegram",
    "linkedin": "LinkedIn",
    "instagram": "Instagram",
    "x": "X",
    "twitter": "X",
}


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_platform(value: str) -> str:
    cleaned = " ".join((value or "").strip().split())
    return PLATFORM_NAMES.get(cleaned.lower(), cleaned)


def _is_telegram_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in {"t.me", "www.t.me"} and bool(parsed.path.strip("/"))


def _public_schedule(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    schedule = dict(row)
    if schedule.get("social_account"):
        schedule["social_account"] = public_social_account(schedule["social_account"])
    return schedule


async def selected_schedule_for_post(session: AsyncSession, user_id: str, post_id: str) -> dict[str, Any] | None:
    schedule = await fetch_one(
        session,
        """
        SELECT sp.*,
               CASE WHEN sa.id IS NULL THEN NULL ELSE row_to_json(sa) END AS social_account
        FROM scheduled_posts sp
        LEFT JOIN social_accounts sa ON sa.id = sp.social_account_id AND sa.user_id = sp.user_id
        WHERE sp.generated_post_id = :post_id
          AND sp.user_id = :user_id
          AND sp.status IN ('scheduled', 'publishing')
        ORDER BY sp.scheduled_for ASC
        LIMIT 1
        """,
        {"post_id": post_id, "user_id": user_id},
    )
    return _public_schedule(schedule)


async def list_scheduled_posts(session: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    rows = await fetch_all(
        session,
        """
        SELECT sp.*,
               CASE WHEN sa.id IS NULL THEN NULL ELSE row_to_json(sa) END AS social_account,
               gp.final_text AS post_text,
               gp.status AS post_status
        FROM scheduled_posts sp
        JOIN generated_posts gp ON gp.id = sp.generated_post_id AND gp.user_id = sp.user_id
        LEFT JOIN social_accounts sa ON sa.id = sp.social_account_id AND sa.user_id = sp.user_id
        WHERE sp.user_id = :user_id
        ORDER BY sp.scheduled_for DESC
        """,
        {"user_id": user_id},
    )
    return [_public_schedule(row) or {} for row in rows]


async def get_scheduled_post(session: AsyncSession, user_id: str, schedule_id: str) -> dict[str, Any]:
    row = await fetch_one(
        session,
        """
        SELECT sp.*,
               CASE WHEN sa.id IS NULL THEN NULL ELSE row_to_json(sa) END AS social_account,
               gp.final_text AS post_text,
               gp.status AS post_status
        FROM scheduled_posts sp
        JOIN generated_posts gp ON gp.id = sp.generated_post_id AND gp.user_id = sp.user_id
        LEFT JOIN social_accounts sa ON sa.id = sp.social_account_id AND sa.user_id = sp.user_id
        WHERE sp.id = :id AND sp.user_id = :user_id
        """,
        {"id": schedule_id, "user_id": user_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Scheduled post not found")
    return _public_schedule(row) or {}


async def schedule_generated_post(
    session: AsyncSession,
    user_id: str,
    post_id: str,
    platform: str,
    scheduled_for: datetime,
    social_account_id: str | None = None,
    selected_asset_id: str | None = None,
) -> dict[str, Any]:
    platform = _normalize_platform(platform)
    if not platform:
        raise HTTPException(status_code=422, detail="Platform is required")
    post = await fetch_one(
        session,
        "SELECT * FROM generated_posts WHERE id = :id AND user_id = :user_id",
        {"id": post_id, "user_id": user_id},
    )
    if not post:
        raise HTTPException(status_code=404, detail="Generated post not found")
    if post["status"] not in SCHEDULABLE_POST_STATUSES:
        raise HTTPException(status_code=409, detail="Approve or edit this post before scheduling")
    if not (post.get("final_text") or "").strip():
        raise HTTPException(status_code=409, detail="Post final text is empty")

    account = None
    if social_account_id:
        account = await owned_social_account(session, user_id, social_account_id)
        if account["platform"].lower() != platform.lower():
            raise HTTPException(status_code=422, detail="Social account platform does not match")
    if platform.lower() == "telegram":
        if not account:
            raise HTTPException(status_code=422, detail="Telegram destination is required")
        if not (account.get("external_account_id") or "").strip() and not _is_telegram_url(account.get("account_url")):
            raise HTTPException(status_code=422, detail="Telegram chat ID, @channel, or valid t.me URL is required")

    asset = None
    if selected_asset_id:
        asset = await fetch_one(
            session,
            """
            SELECT *
            FROM post_assets
            WHERE id = :asset_id AND post_id = :post_id AND user_id = :user_id
            """,
            {"asset_id": selected_asset_id, "post_id": post_id, "user_id": user_id},
        )
        if not asset:
            raise HTTPException(status_code=404, detail="Selected asset not found")
    else:
        asset = await fetch_one(
            session,
            """
            SELECT *
            FROM post_assets
            WHERE post_id = :post_id AND user_id = :user_id AND is_selected = true
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {"post_id": post_id, "user_id": user_id},
        )

    existing = await fetch_one(
        session,
        """
        SELECT id
        FROM scheduled_posts
        WHERE generated_post_id = :post_id
          AND user_id = :user_id
          AND platform = :platform
          AND status IN ('scheduled', 'publishing')
        LIMIT 1
        """,
        {"post_id": post_id, "user_id": user_id, "platform": platform},
    )
    if existing:
        raise HTTPException(status_code=409, detail="This post is already scheduled for this platform")

    scheduled_for_utc = _to_utc(scheduled_for)
    payload = {
        "generated_post_id": post_id,
        "platform": platform,
        "format": post.get("format"),
        "final_text": post.get("final_text"),
        "draft_text": post.get("draft_text"),
        "selected_asset": {
            "id": str(asset["id"]),
            "asset_type": asset.get("asset_type"),
            "provider": asset.get("provider"),
            "preview_url": asset.get("preview_url"),
            "source_url": asset.get("source_url"),
            "author": asset.get("author"),
            "alt_text": asset.get("alt_text"),
            "image_prompt": asset.get("image_prompt"),
        } if asset else None,
        "social_account": public_social_account(account) if account else None,
        "snapshot_at": datetime.now(UTC).isoformat(),
    }
    payload = jsonable_encoder(payload)
    try:
        schedule = await fetch_one(
            session,
            """
            INSERT INTO scheduled_posts
                (user_id, generated_post_id, social_account_id, selected_asset_id, platform, scheduled_for, status, payload)
            VALUES
                (:user_id, :generated_post_id, :social_account_id, :selected_asset_id, :platform,
                 :scheduled_for, 'scheduled', CAST(:payload AS JSONB))
            RETURNING *
            """,
            {
                "user_id": user_id,
                "generated_post_id": post_id,
                "social_account_id": social_account_id,
                "selected_asset_id": str(asset["id"]) if asset else None,
                "platform": platform,
                "scheduled_for": scheduled_for_utc,
                "payload": payload,
            },
        )
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="This post is already scheduled for this platform") from exc

    await execute(
        session,
        "UPDATE generated_posts SET status = 'scheduled' WHERE id = :id AND user_id = :user_id",
        {"id": post_id, "user_id": user_id},
    )
    await save_generation_run(
        session,
        user_id=user_id,
        run_type="post_schedule",
        provider=None,
        agent_name="scheduling_service",
        input_payload={
            "post_id": post_id,
            "platform": platform,
            "scheduled_for": scheduled_for_utc.isoformat(),
            "social_account_id": social_account_id,
            "selected_asset_id": str(asset["id"]) if asset else None,
        },
        output_payload={"schedule_id": str(schedule["id"]) if schedule else None, "status": "scheduled"},
        status="completed",
    )
    return await get_scheduled_post(session, user_id, str(schedule["id"]))


async def cancel_scheduled_post(session: AsyncSession, user_id: str, schedule_id: str) -> dict[str, Any]:
    schedule = await fetch_one(
        session,
        "SELECT * FROM scheduled_posts WHERE id = :id AND user_id = :user_id",
        {"id": schedule_id, "user_id": user_id},
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Scheduled post not found")
    if schedule["status"] not in ACTIVE_SCHEDULE_STATUSES:
        raise HTTPException(status_code=409, detail="Only active schedules can be cancelled")
    updated = await fetch_one(
        session,
        """
        UPDATE scheduled_posts
        SET status = 'cancelled', error_message = NULL
        WHERE id = :id AND user_id = :user_id
        RETURNING *
        """,
        {"id": schedule_id, "user_id": user_id},
    )
    still_active = await fetch_one(
        session,
        """
        SELECT id
        FROM scheduled_posts
        WHERE generated_post_id = :post_id
          AND user_id = :user_id
          AND status IN ('scheduled', 'publishing')
        LIMIT 1
        """,
        {"post_id": schedule["generated_post_id"], "user_id": user_id},
    )
    if not still_active:
        await execute(
            session,
            "UPDATE generated_posts SET status = 'approved' WHERE id = :id AND user_id = :user_id AND status = 'scheduled'",
            {"id": schedule["generated_post_id"], "user_id": user_id},
        )
    await save_generation_run(
        session,
        user_id=user_id,
        run_type="post_schedule_cancel",
        provider=None,
        agent_name="scheduling_service",
        input_payload={"schedule_id": schedule_id, "post_id": str(schedule["generated_post_id"])},
        output_payload={"schedule_id": schedule_id, "status": "cancelled"},
        status="completed",
    )
    return await get_scheduled_post(session, user_id, str(updated["id"]))
