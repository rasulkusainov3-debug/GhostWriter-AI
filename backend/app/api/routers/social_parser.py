from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import execute, fetch_all, fetch_one, get_session
from app.schemas.common import ParserRunRequest, SocialLinksRequest
from app.services.social_analyzer_adapter import adapter

router = APIRouter(prefix="/social-parser", tags=["social_parser"])


@router.post("/links")
async def save_social_links(payload: SocialLinksRequest, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    profile = await fetch_one(session, "SELECT raw_answers FROM user_profiles WHERE user_id = :user_id", {"user_id": user["id"]})
    raw_answers = (profile or {}).get("raw_answers") or {}
    raw_answers["social_links"] = payload.links
    await execute(session, "UPDATE user_profiles SET raw_answers = CAST(:raw_answers AS JSONB) WHERE user_id = :user_id", {"raw_answers": raw_answers, "user_id": user["id"]})
    await session.commit()
    return {"social_links": payload.links}


@router.post("/run")
async def run_parser(payload: ParserRunRequest, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    profile = await fetch_one(session, "SELECT niche FROM user_profiles WHERE user_id = :user_id", {"user_id": user["id"]})
    niche = payload.niche or (profile or {}).get("niche") or "общее"
    if not payload.execute_legacy:
        return {
            "status": "adapter_ready",
            "message": "Legacy parser execution is disabled for this request. Send execute_legacy=true to run social_analyzer parsers.",
            "sources": payload.sources,
            "niche": niche,
        }
    posts = adapter.run_legacy_parsers(niche=niche, sources=payload.sources)
    for post in posts:
        await execute(
            session,
            """
            INSERT INTO raw_posts (user_id, source, title, content, url, score, comments, niche, published_at)
            VALUES (:user_id, :source, :title, :content, :url, :score, :comments, :niche, :published_at)
            """,
            {
                "user_id": user["id"],
                "source": post.get("source", "legacy"),
                "title": post.get("title"),
                "content": post.get("content"),
                "url": post.get("url"),
                "score": post.get("score") or 0,
                "comments": post.get("comments") or 0,
                "niche": post.get("niche") or niche,
                "published_at": post.get("published_at"),
            },
        )
    await session.commit()
    return {"inserted": len(posts), "sources": payload.sources, "niche": niche}


@router.get("/raw-posts")
async def list_raw_posts(user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await fetch_all(
        session,
        "SELECT * FROM raw_posts WHERE user_id = :user_id ORDER BY collected_at DESC LIMIT 200",
        {"user_id": user["id"]},
    )


@router.delete("/raw-posts/{post_id}")
async def delete_raw_post(post_id: int, user: dict = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    await execute(session, "DELETE FROM raw_posts WHERE id = :id AND user_id = :user_id", {"id": post_id, "user_id": user["id"]})
    await session.commit()
    return {"deleted": post_id}
