from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import fetch_all, fetch_one


DEFAULT_STRUCTURE = ["hook", "insight", "example", "CTA"]
MAX_EXAMPLE_CHARS = 700


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]
    return []


def _append_unique(items: list[str], additions: list[str]) -> list[str]:
    result = list(items)
    seen = {item.lower() for item in result}
    for item in additions:
        normalized = str(item or "").strip()
        if normalized and normalized.lower() not in seen:
            result.append(normalized)
            seen.add(normalized.lower())
    return result


def _truncate(text: str, limit: int = MAX_EXAMPLE_CHARS) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _usable_example(text: str | None) -> bool:
    value = str(text or "").strip()
    if len(value) < 80:
        return False
    lower = value.lower()
    blocked = ("json data", "provided json", "overall structure", "key findings", "potential use cases")
    return not any(marker in lower for marker in blocked)


def merge_personality_with_profile(profile: dict[str, Any], personality: dict[str, Any]) -> dict[str, Any]:
    return {**profile, "personality_brief": personality}


async def get_style_examples(session: AsyncSession, user_id: str, limit: int = 3) -> list[dict[str, Any]]:
    rows = await fetch_all(
        session,
        """
        SELECT id, platform, final_text, status
        FROM generated_posts
        WHERE user_id = :user_id
          AND status IN ('approved', 'edited')
          AND NULLIF(TRIM(final_text), '') IS NOT NULL
        ORDER BY
          CASE WHEN status = 'approved' THEN 0 ELSE 1 END,
          generated_at DESC
        LIMIT :limit
        """,
        {"user_id": user_id, "limit": max(limit * 3, 6)},
    )
    examples = [
        {
            "post_id": str(row["id"]),
            "platform": row.get("platform"),
            "status": row.get("status"),
            "text": _truncate(row.get("final_text") or ""),
        }
        for row in rows
        if _usable_example(row.get("final_text"))
    ]
    return examples[:limit] if len(examples) >= 2 else []


async def build_personality_brief(session: AsyncSession, user_id: str) -> dict[str, Any]:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user_id})
    profile = profile or {}
    raw_answers = profile.get("raw_answers") or {}
    personality = raw_answers.get("personality") if isinstance(raw_answers, dict) else {}
    personality = personality if isinstance(personality, dict) else {}
    examples = await get_style_examples(session, user_id)

    avoid_phrases = _append_unique(_as_list(personality.get("avoid_phrases")), _as_list(profile.get("avoid")))
    vocabulary = _append_unique(_as_list(personality.get("vocabulary_preferences")), _as_list(profile.get("user_values")))
    preferred_structure = _as_list(personality.get("preferred_structure")) or DEFAULT_STRUCTURE

    return {
        "voice": personality.get("voice") or profile.get("tone") or "expert but human",
        "writing_style": personality.get("writing_style")
        or "Clear, practical, audience-focused, with short paragraphs and a useful CTA.",
        "preferred_structure": preferred_structure,
        "vocabulary_preferences": vocabulary,
        "avoid_phrases": avoid_phrases,
        "example_post_ids": _as_list(personality.get("example_post_ids")),
        "examples": examples,
        "examples_used": len(examples),
        "source": "stored" if personality else "profile_defaults",
        "defaults_from_profile": {
            "tone": profile.get("tone"),
            "audience": profile.get("audience"),
            "profession": profile.get("profession"),
            "goal": profile.get("goal"),
            "niche": profile.get("niche"),
            "platforms": profile.get("platforms") or [],
        },
    }


async def update_personality_from_chat(session: AsyncSession, user_id: str, field: str, value: Any) -> dict[str, Any]:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user_id})
    if not profile:
        return {}
    raw_answers = dict(profile.get("raw_answers") or {})
    personality = dict(raw_answers.get("personality") or {})

    if field in {"preferred_structure", "vocabulary_preferences", "avoid_phrases", "example_post_ids"}:
        personality[field] = _append_unique(_as_list(personality.get(field)), _as_list(value))
    else:
        personality[field] = str(value or "").strip()

    raw_answers["personality"] = personality
    updated = await fetch_one(
        session,
        """
        UPDATE user_profiles
        SET raw_answers = CAST(:raw_answers AS JSONB),
            updated_at = NOW()
        WHERE user_id = :user_id
        RETURNING *
        """,
        {"user_id": user_id, "raw_answers": raw_answers},
    )
    return updated or {**profile, "raw_answers": raw_answers}
