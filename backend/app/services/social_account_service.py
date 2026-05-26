from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import fetch_all, fetch_one


def public_social_account(account: dict[str, Any] | None) -> dict[str, Any] | None:
    if not account:
        return None
    safe = dict(account)
    safe.pop("token_ref", None)
    safe.pop("token_metadata", None)
    return safe


async def list_social_accounts(session: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    rows = await fetch_all(
        session,
        """
        SELECT *
        FROM social_accounts
        WHERE user_id = :user_id
        ORDER BY platform, created_at DESC
        """,
        {"user_id": user_id},
    )
    return [public_social_account(row) or {} for row in rows]


async def create_manual_social_account(
    session: AsyncSession,
    user_id: str,
    platform: str,
    display_name: str,
    account_url: str | None = None,
    external_account_id: str | None = None,
) -> dict[str, Any]:
    platform = platform.strip()
    display_name = display_name.strip()
    if not platform:
        raise HTTPException(status_code=422, detail="Platform is required")
    if not display_name:
        raise HTTPException(status_code=422, detail="Display name is required")
    account = await fetch_one(
        session,
        """
        INSERT INTO social_accounts
            (user_id, platform, display_name, external_account_id, account_url, connection_status)
        VALUES
            (:user_id, :platform, :display_name, :external_account_id, :account_url, 'manual')
        RETURNING *
        """,
        {
            "user_id": user_id,
            "platform": platform,
            "display_name": display_name,
            "external_account_id": external_account_id,
            "account_url": account_url,
        },
    )
    return public_social_account(account) or {}


async def owned_social_account(session: AsyncSession, user_id: str, account_id: str) -> dict[str, Any]:
    account = await fetch_one(
        session,
        "SELECT * FROM social_accounts WHERE id = :id AND user_id = :user_id",
        {"id": account_id, "user_id": user_id},
    )
    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")
    return account
