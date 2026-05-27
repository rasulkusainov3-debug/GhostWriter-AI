from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import execute, fetch_all, fetch_one
from app.services.run_tracking_service import save_generation_run
from app.services.scheduling_service import selected_schedule_for_post
from app.services.visual_adapter import visual_adapter


async def _owned_post(session: AsyncSession, user_id: str, post_id: str) -> dict[str, Any]:
    post = await fetch_one(
        session,
        """
        SELECT gp.*, t.topic AS trend_topic
        FROM generated_posts gp
        LEFT JOIN trends t ON t.id = gp.trend_id
        WHERE gp.id = :post_id AND gp.user_id = :user_id
        """,
        {"post_id": post_id, "user_id": user_id},
    )
    if not post:
        raise HTTPException(status_code=404, detail="Generated post not found")
    return post


async def selected_asset_for_post(session: AsyncSession, user_id: str, post_id: str) -> dict[str, Any] | None:
    return await fetch_one(
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


async def assets_count_for_post(session: AsyncSession, user_id: str, post_id: str) -> int:
    row = await fetch_one(
        session,
        "SELECT COUNT(*) AS count FROM post_assets WHERE post_id = :post_id AND user_id = :user_id",
        {"post_id": post_id, "user_id": user_id},
    )
    return int((row or {}).get("count") or 0)


async def enrich_generated_post(session: AsyncSession, user_id: str, post: dict[str, Any] | None) -> dict[str, Any] | None:
    if not post:
        return None
    post_id = str(post["id"])
    enriched = dict(post)
    enriched["selected_asset"] = await selected_asset_for_post(session, user_id, post_id)
    enriched["assets_count"] = await assets_count_for_post(session, user_id, post_id)
    enriched["active_schedule"] = await selected_schedule_for_post(session, user_id, post_id)
    return enriched


async def enrich_generated_posts(session: AsyncSession, user_id: str, posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [await enrich_generated_post(session, user_id, post) or post for post in posts]


async def list_post_assets(session: AsyncSession, user_id: str, post_id: str) -> list[dict[str, Any]]:
    await _owned_post(session, user_id, post_id)
    return await fetch_all(
        session,
        """
        SELECT *
        FROM post_assets
        WHERE post_id = :post_id AND user_id = :user_id
        ORDER BY is_selected DESC, created_at DESC
        """,
        {"post_id": post_id, "user_id": user_id},
    )


async def _insert_asset(session: AsyncSession, user_id: str, post_id: str, visual: dict[str, Any], select: bool = True) -> dict[str, Any]:
    if select:
        await execute(
            session,
            "UPDATE post_assets SET is_selected = false WHERE post_id = :post_id AND user_id = :user_id",
            {"post_id": post_id, "user_id": user_id},
        )
    return await fetch_one(
        session,
        """
        INSERT INTO post_assets
            (user_id, post_id, asset_type, provider, status, image_prompt, search_query,
             preview_url, source_url, author, alt_text, local_path, metadata, is_selected)
        VALUES
            (:user_id, :post_id, :asset_type, :provider, :status, :image_prompt, :search_query,
             :preview_url, :source_url, :author, :alt_text, :local_path, CAST(:metadata AS JSONB), :is_selected)
        RETURNING *
        """,
        {
            "user_id": user_id,
            "post_id": post_id,
            "asset_type": visual.get("asset_type") or "image",
            "provider": visual.get("provider"),
            "status": visual.get("status") or "idea",
            "image_prompt": visual.get("image_prompt"),
            "search_query": visual.get("search_query"),
            "preview_url": visual.get("preview_url"),
            "source_url": visual.get("source_url"),
            "author": visual.get("author"),
            "alt_text": visual.get("alt_text"),
            "local_path": visual.get("local_path"),
            "metadata": visual.get("metadata") or {},
            "is_selected": select,
        },
    ) or {}


async def generate_visual_for_post(session: AsyncSession, user_id: str, post_id: str) -> dict[str, Any]:
    post = await _owned_post(session, user_id, post_id)
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user_id})

    existing_assets = await fetch_all(
        session,
        """
        SELECT provider, preview_url, source_url, metadata
        FROM post_assets
        WHERE post_id = :post_id AND user_id = :user_id
        """,
        {"post_id": post_id, "user_id": user_id},
    )

    exclude_urls = {
        url
        for asset in existing_assets
        for url in [asset.get("preview_url"), asset.get("source_url")]
        if url
    }

    exclude_ids = set()
    for asset in existing_assets:
        metadata = asset.get("metadata") or {}

        if isinstance(metadata, dict):
            for key in ("provider_asset_id", "pexels_id", "unsplash_id", "id"):
                value = metadata.get(key)
                if value:
                    exclude_ids.add(str(value))

            raw = metadata.get("raw")
            if isinstance(raw, dict):
                for key in ("id", "pexels_id", "unsplash_id"):
                    value = raw.get(key)
                    if value:
                        exclude_ids.add(str(value))

    try:
        print("VISUAL EXCLUDE URLS:", exclude_urls)
        print("VISUAL EXCLUDE IDS:", exclude_ids)
        visual = await visual_adapter.generate_visual(
            post,
            profile,
            exclude_urls=exclude_urls,
            exclude_ids=exclude_ids,
        )

        new_preview = visual.get("preview_url")
        new_source = visual.get("source_url")

        if new_preview and new_preview in exclude_urls:
            raise HTTPException(status_code=409, detail="Visual provider returned a duplicate preview image. Try again.")
        if new_source and new_source in exclude_urls:
            raise HTTPException(status_code=409, detail="Visual provider returned a duplicate source image. Try again.")

        asset = await _insert_asset(session, user_id, post_id, visual, select=True)
        await save_generation_run(
            session,
            user_id=user_id,
            run_type="post_visual_generation",
            provider=asset.get("provider"),
            agent_name="social_analyzer.agent2_beautify_adapter",
            input_payload={
                "post_id": post_id,
                "platform": post.get("platform"),
                "trend_topic": post.get("trend_topic"),
                "excluded_assets": len(existing_assets),
            },
            output_payload={
                "asset_id": str(asset.get("id")),
                "status": asset.get("status"),
                "provider": asset.get("provider"),
                "preview_url": asset.get("preview_url"),
                "source_url": asset.get("source_url"),
            },
            status="completed",
        )
        return {"asset": asset, "post": await enrich_generated_post(session, user_id, post)}
    except Exception as exc:
        await save_generation_run(
            session,
            user_id=user_id,
            run_type="post_visual_generation",
            provider=None,
            agent_name="social_analyzer.agent2_beautify_adapter",
            input_payload={"post_id": post_id},
            output_payload={},
            status="failed",
            error_message=str(exc),
        )
        raise


async def select_post_asset(session: AsyncSession, user_id: str, post_id: str, asset_id: str) -> dict[str, Any]:
    await _owned_post(session, user_id, post_id)
    asset = await fetch_one(
        session,
        "SELECT * FROM post_assets WHERE id = :asset_id AND post_id = :post_id AND user_id = :user_id",
        {"asset_id": asset_id, "post_id": post_id, "user_id": user_id},
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Post asset not found")
    await execute(
        session,
        "UPDATE post_assets SET is_selected = false WHERE post_id = :post_id AND user_id = :user_id",
        {"post_id": post_id, "user_id": user_id},
    )
    selected = await fetch_one(
        session,
        """
        UPDATE post_assets
        SET is_selected = true, status = 'selected'
        WHERE id = :asset_id AND post_id = :post_id AND user_id = :user_id
        RETURNING *
        """,
        {"asset_id": asset_id, "post_id": post_id, "user_id": user_id},
    )
    return {"asset": selected, "post": await enrich_generated_post(session, user_id, await _owned_post(session, user_id, post_id))}
