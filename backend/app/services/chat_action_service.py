from __future__ import annotations

import re
import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import execute, fetch_all, fetch_one
from app.services.analytics_context_service import recommendations_for_user
from app.services.chat_intent_service import ChatIntent
from app.services.content_plan_service import add_trend_to_draft_plan, create_weekly_content_plan, latest_content_plan
from app.services.lifecycle_service import (
    AUDIENCE_CONFIRMATION_FIELDS,
    PROFILE_CONFIRMATION_FIELDS,
    mark_audience_needs_confirmation,
    mark_profile_needs_confirmation,
)
from app.services.llm.base import LLMUnavailable
from app.services.llm.factory import generate_text_with_fallback
from app.services.post_asset_service import enrich_generated_post, enrich_generated_posts
from app.services.post_generation_service import generate_from_latest_plan, generate_post_from_trend_id, generate_post_from_trend_message, regenerate_post, update_generated_post
from app.services.run_tracking_service import save_generation_run
from app.services.trend_service import active_trends, find_and_save_trends


def _keywords(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        if value.strip().startswith("["):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed if str(item).strip()]
            except Exception:
                pass
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _list_value(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;]", raw or "") if item.strip()]


def _platform_from_message(message: str, params: dict[str, Any] | None = None) -> str | None:
    raw = (params or {}).get("platform")
    if raw:
        return str(raw).strip()
    text = f" {(message or '').lower()} "
    if any(word in text for word in [" linkedin ", " линкедин ", " линкедын ", " linked in "]):
        return "LinkedIn"
    if any(word in text for word in [" telegram ", " телеграм ", " tg "]):
        return "Telegram"
    if any(word in text for word in [" instagram ", " инстаграм "]):
        return "Instagram"
    if any(word in text for word in [" twitter ", " твиттер ", " x/twitter ", " x "]):
        return "X"
    return None


def _profile_text(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "Профиль клиента пока не создан."
    values = profile.get("user_values") or []
    platforms = profile.get("platforms") or []
    return "\n".join(
        [
            "Текущий профиль клиента:",
            f"- Имя: {profile.get('name') or 'не указано'}",
            f"- Ниша: {profile.get('niche') or 'не указано'}",
            f"- Профессия: {profile.get('profession') or 'не указано'}",
            f"- Цель: {profile.get('goal') or 'не указано'}",
            f"- Тон: {profile.get('tone') or 'не указано'}",
            f"- Аудитория: {profile.get('audience') or 'не указано'}",
            f"- Платформы: {', '.join(platforms) if platforms else 'не указано'}",
            f"- Ценности: {', '.join(values) if values else 'не указано'}",
            f"- Избегать: {profile.get('avoid') or 'не указано'}",
        ]
    )


def _trend_cards(trends: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for trend in trends:
        insights = trend.get("youtube_insights") or {}
        cards.append({
            "id": trend.get("id"),
            "topic": trend.get("topic"),
            "summary": trend.get("summary"),
            "keywords": _keywords(trend.get("keywords")),
            "score": trend.get("final_score"),
            "posts_count": trend.get("posts_count"),
            "source_count": trend.get("source_count") or trend.get("posts_count"),
            "example_sources": trend.get("example_sources") or [],
            "collected_at": trend.get("collected_at"),
            "expires_at": trend.get("expires_at"),
            "relevance_level": trend.get("relevance_level") or insights.get("relevance_level"),
            "relevance_score": trend.get("relevance_score") or insights.get("relevance_score"),
            "relevance_reason": trend.get("relevance_reason") or insights.get("relevance_reason"),
            "adaptation_suggestion": trend.get("adaptation_suggestion") or insights.get("adaptation_suggestion"),
        })
    return cards


def _latest_message_context(history: list[dict[str, Any]]) -> dict[str, Any]:
    for item in reversed(history or []):
        context = item.get("context")
        if isinstance(context, dict):
            return context
    return {}


def _trend_index_from_message(message: str) -> int | None:
    text = message.lower()
    if re.search(r"(?:втор|2|second)", text):
        return 1
    if re.search(r"(?:перв|1|first)", text):
        return 0
    if re.search(r"(?:трет|3|third)", text):
        return 2
    return None


def _trend_index_from_intent(message: str, intent: ChatIntent) -> int | None:
    raw_index = intent.params.get("trend_index")
    if raw_index is not None:
        try:
            return int(raw_index)
        except (TypeError, ValueError):
            pass
    return _trend_index_from_message(message)


def _trend_id_from_history_index(history: list[dict[str, Any]], index: int) -> int | None:
    for item in reversed(history or []):
        action = item.get("action") if isinstance(item.get("action"), dict) else {}
        trends = action.get("trends") if isinstance(action, dict) else None
        if isinstance(trends, list) and index < len(trends):
            try:
                return int(trends[index].get("id"))
            except (AttributeError, TypeError, ValueError):
                return None
    return None


def _latest_trend_id_from_history(history: list[dict[str, Any]]) -> int | None:
    for item in reversed(history or []):
        action = item.get("action") if isinstance(item.get("action"), dict) else {}
        trends = action.get("trends") if isinstance(action, dict) else None
        if isinstance(trends, list) and trends:
            try:
                return int(trends[0].get("id"))
            except (AttributeError, TypeError, ValueError):
                return None
    return None


async def _trend_id_from_topic(session: AsyncSession, user_id: str, message: str) -> int | None:
    text = (message or "").lower()
    topic_match = re.search(r"(?:по теме|about|topic)\s+(.+)$", text)
    topic_text = topic_match.group(1).strip(" .") if topic_match else text
    topic_terms = {term for term in re.split(r"\W+", topic_text) if len(term) > 2}
    if not topic_terms:
        return None
    trends = await active_trends(session, user_id, limit=10)
    best: tuple[int, int] | None = None
    for trend in trends:
        trend_text = f"{trend.get('topic') or ''} {trend.get('summary') or ''}".lower()
        trend_terms = {term for term in re.split(r"\W+", trend_text) if len(term) > 2}
        score = len(topic_terms & trend_terms)
        if score and (best is None or score > best[0]):
            try:
                best = (score, int(trend["id"]))
            except (KeyError, TypeError, ValueError):
                pass
    return best[1] if best else None


def _post_id_from_history(history: list[dict[str, Any]]) -> str | None:
    context = _latest_message_context(history)
    raw_post_id = context.get("post_id")
    if raw_post_id:
        return str(raw_post_id)
    for item in reversed(history or []):
        action = item.get("action") if isinstance(item.get("action"), dict) else {}
        post = action.get("post") if isinstance(action, dict) else None
        if isinstance(post, dict) and post.get("id"):
            return str(post["id"])
        posts = action.get("posts") if isinstance(action, dict) else None
        if isinstance(posts, list) and posts and isinstance(posts[0], dict) and posts[0].get("id"):
            return str(posts[0]["id"])
    return None


def _mentions_specific_trend(message: str, context: dict[str, Any]) -> bool:
    text = message.lower()
    return bool(
        context.get("trend_id")
        or _trend_index_from_message(message) is not None
        or any(phrase in text for phrase in ["по этому тренду", "this trend", "selected trend", "по тренду"])
    )


def _asks_for_recommendations(message: str) -> bool:
    text = message.lower()
    phrases = [
        "что улучшить",
        "что работает лучше",
        "почему такой план",
        "какие рекомендации",
        "рекомендации",
        "what should i improve",
        "what works better",
        "why this plan",
        "recommendations",
    ]
    return any(phrase in text for phrase in phrases)


def _regeneration_mode_from_message(message: str) -> str:
    text = (message or "").lower()
    if any(phrase in text for phrase in ["короче", "shorter", "сократи", "сделай кратко"]):
        return "shorter"
    if any(phrase in text for phrase in ["эксперт", "expert", "профессиональ"]):
        return "more_expert"
    if any(phrase in text for phrase in ["живее", "human", "человеч", "теплее"]):
        return "more_human"
    if any(phrase in text for phrase in ["улучши", "improve", "доработай"]):
        return "improve_current"
    if any(phrase in text for phrase in ["хук", "hook", "цепля"]):
        return "stronger_hook"
    return "regenerate_full"


async def _resolve_selected_trend_id(session: AsyncSession, user_id: str, message: str, history: list[dict[str, Any]], intent: ChatIntent) -> int | None:
    context = _latest_message_context(history)
    raw_trend_id = context.get("trend_id") or intent.params.get("trend_id")
    if raw_trend_id:
        try:
            return int(raw_trend_id)
        except (TypeError, ValueError):
            return None
    index = _trend_index_from_intent(message, intent)
    if index is None:
        return await _trend_id_from_topic(session, user_id, message)
    history_trend_id = _trend_id_from_history_index(history, index)
    if history_trend_id:
        return history_trend_id
    trends = await active_trends(session, user_id, limit=10)
    if index >= len(trends):
        return None
    return int(trends[index]["id"])


OpenAIChatUnavailable = LLMUnavailable


def _compact_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    if not profile:
        return {}
    return {
        "name": profile.get("name"),
        "niche": profile.get("niche"),
        "profession": profile.get("profession"),
        "goal": profile.get("goal"),
        "tone": profile.get("tone"),
        "audience": profile.get("audience"),
        "platforms": profile.get("platforms") or [],
        "values": profile.get("user_values") or [],
        "avoid": profile.get("avoid"),
    }


async def _compact_general_context(
    session: AsyncSession,
    user_id: str,
    profile: dict[str, Any] | None,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    trends = await active_trends(session, user_id, limit=5)
    latest_plan = await latest_content_plan(session, user_id)
    latest_post = await fetch_one(
        session,
        """
        SELECT id, platform, format, status, draft_text, final_text, trend_id
        FROM generated_posts
        WHERE user_id = :user_id
        ORDER BY generated_at DESC
        LIMIT 1
        """,
        {"user_id": user_id},
    )
    try:
        recommendations = await recommendations_for_user(session, user_id)
    except Exception:
        recommendations = {}
    return {
        "profile": _compact_profile(profile),
        "recent_trends": [
            {
                "id": trend.get("id"),
                "topic": trend.get("topic"),
                "summary": trend.get("summary"),
                "relevance_level": trend.get("relevance_level") or (trend.get("youtube_insights") or {}).get("relevance_level"),
            }
            for trend in trends
        ],
        "latest_content_plan": {
            "id": latest_plan["plan"].get("id"),
            "title": latest_plan["plan"].get("title"),
            "status": latest_plan["plan"].get("status"),
            "items_count": len(latest_plan.get("items") or []),
        } if latest_plan else None,
        "latest_post": {
            "id": latest_post.get("id"),
            "platform": latest_post.get("platform"),
            "format": latest_post.get("format"),
            "status": latest_post.get("status"),
            "final_text_preview": str(latest_post.get("final_text") or latest_post.get("draft_text") or "")[:400],
        } if latest_post else None,
        "recommendations": {
            "data_quality": recommendations.get("data_quality"),
            "items": (recommendations.get("recommendations") or [])[:5],
            "next_actions": (recommendations.get("next_actions") or [])[:3],
        },
        "recent_user_messages": [
            {"role": item.get("role"), "text": str(item.get("text") or "")[:300]}
            for item in history[-8:]
            if item.get("role") in {"user", "assistant"}
        ],
    }


def _general_fallback(message: str, context: dict[str, Any]) -> str:
    profile = context.get("profile") or {}
    trends = context.get("recent_trends") or []
    recommendations = context.get("recommendations") or {}
    lower = (message or "").lower()
    if not profile:
        return "Я пока не вижу ваш цифровой профиль. Заполните профиль или пройдите onboarding, и я смогу отвечать с учётом ниши, аудитории, целей и платформ."
    if any(phrase in lower for phrase in ["кто я", "что ты знаешь", "профил", "who am i", "what do you know"]):
        return _profile_text(profile)
    if any(phrase in lower for phrase in ["тем", "topics", "content ideas", "что писать"]):
        if trends:
            lines = [f"- {trend.get('topic')}" for trend in trends[:5]]
            return "По текущему профилю лучше брать темы, которые связывают вашу экспертизу с целью и аудиторией:\n" + "\n".join(lines)
        return "Пока нет активных трендов. Сначала запустите поиск трендов, и я предложу темы на основе вашего профиля."
    if any(phrase in lower for phrase in ["улучш", "лучше", "improve", "better"]):
        items = recommendations.get("items") or []
        if items:
            return "По текущим данным я бы улучшил вот это:\n" + "\n".join(f"- {item}" for item in items[:5])
        return "Пока мало метрик для точных рекомендаций. Практичный следующий шаг: добавить метрики по постам, а до этого усилить хук, CTA и связь темы с вашей целью."
    return (
        "Я могу помочь с профилем, трендами, контент-планом и постами. "
        "Напишите, что хотите сделать: например, «найди тренды», «создай контент-план» или «сделай пост по второму тренду»."
    )


async def answer_with_llm(message: str, context: dict[str, Any]) -> tuple[str, str]:
    prompt = (
        f"User message: {message}\n"
        f"Compact user context:\n{json.dumps(context, ensure_ascii=False, default=str)}\n\n"
        "Answer the user's normal question as GhostWriter AI. Use the profile, audience, platforms, "
        "recent trends, latest plan/post, and recommendations when relevant. If context is missing, say what is needed. "
        "Do not mention providers, detectors, internal statuses, JSON, database fields, or backend implementation."
    )
    text, provider = await generate_text_with_fallback(
        prompt,
        system_prompt=(
            "You are GhostWriter AI, a helpful social media strategy assistant. "
            "Answer in the user's language. Be concise, practical, and user-facing. "
            "Do not expose internal debug information."
        ),
    )
    return text, provider


async def _update_profile(session: AsyncSession, user_id: str, profile: dict[str, Any], field: str, value: Any) -> dict[str, Any]:
    if not field or value in (None, ""):
        raise HTTPException(status_code=409, detail="Уточните, какое значение нужно сохранить.")
    if field in {"platforms", "user_values"}:
        value = _list_value(value) if isinstance(value, str) else value
    merged = {**profile, field: value}
    await execute(
        session,
        """
        UPDATE user_profiles
        SET name=:name, niche=:niche, profession=:profession, goal=:goal, tone=:tone,
            audience=:audience, avoid=:avoid, user_values=CAST(:user_values AS JSONB),
            platforms=CAST(:platforms AS JSONB)
        WHERE user_id=:user_id
        """,
        {
            "user_id": user_id,
            "name": merged.get("name"),
            "niche": merged.get("niche"),
            "profession": merged.get("profession"),
            "goal": merged.get("goal"),
            "tone": merged.get("tone"),
            "audience": merged.get("audience"),
            "avoid": merged.get("avoid"),
            "user_values": merged.get("user_values") or [],
            "platforms": merged.get("platforms") or [],
        },
    )
    if field in PROFILE_CONFIRMATION_FIELDS:
        await mark_profile_needs_confirmation(session, user_id)
    if field in AUDIENCE_CONFIRMATION_FIELDS:
        await mark_audience_needs_confirmation(session, user_id)
    return merged


async def execute_chat_intent(
    session: AsyncSession,
    user: dict[str, Any],
    profile: dict[str, Any] | None,
    intent: ChatIntent,
    message: str,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    user_id = str(user["id"])
    if not profile and intent.name not in {"general_chat"}:
        return {
            "text": "Сначала нужен профиль клиента. Пройдите onboarding или заполните профиль.",
            "action": {"type": intent.name, "status": "needs_profile", "action_required": "complete_profile"},
        }
    if not profile:
        return {
            "text": "Я пока не вижу ваш цифровой профиль. Пройдите onboarding или заполните профиль, и я смогу отвечать с учётом ниши, аудитории, целей и платформ.",
            "action": {"type": intent.name, "status": "needs_profile", "action_required": "complete_profile"},
        }

    if intent.name in {"find_new_trends", "refresh_trends"}:
        result = await find_and_save_trends(session, user_id, profile, run_legacy=True)
        cards = _trend_cards(result["trends"])
        if cards:
            text = f"Нашёл {len(cards)} трендов по вашему профилю и сохранил результаты. Ниже карточки тем, из которых можно сразу сделать пост или контент-план."
            if result["status"] == "limited_sources":
                text += "\n\nИсточников оказалось меньше, чем нужно для уверенного анализа, поэтому я расширил поиск. Карточки ниже основаны только на найденных материалах."
        else:
            text = "Не удалось найти достаточно актуальных материалов по вашему профилю. Попробуйте добавить больше платформ, ссылок или уточнить нишу."
        if cards:
            high = len([card for card in cards if card.get("relevance_level") == "high"])
            medium = len([card for card in cards if card.get("relevance_level") == "medium"])
            text = f"Я нашёл {len(cards)} релевантных трендов для вашего профиля: {high} с высокой релевантностью и {medium} со средней. Ниже карточки тем, из которых можно сделать пост или контент-план."
            if result["status"] == "limited_sources":
                text += "\n\nИсточников оказалось меньше, чем нужно для уверенного анализа, поэтому я расширил поиск. Карточки ниже основаны только на найденных материалах."
        else:
            text = "Не удалось найти достаточно актуальных материалов по вашему профилю. Попробуйте добавить больше платформ, ссылок или уточнить нишу."
        return {
            "text": text,
            "action": {
                "type": intent.name,
                "status": "done" if cards else result["status"],
                "trends": cards,
                "run_summary": {
                    "queries_used": result["context"].get("queries", []),
                    "raw_posts_found": result["raw_posts_inserted"],
                    "trends_found": len(cards),
                },
                "data": {
                    "trend_run": result.get("trend_run"),
                    "run_summary": {
                        "queries_used": result["context"].get("queries", []),
                        "raw_posts_found": result["raw_posts_inserted"],
                        "trends_found": len(cards),
                    },
                    "queries_used": result["context"].get("queries", []),
                    "raw_posts_found": result["raw_posts_inserted"],
                    "trends_found": len(cards),
                    "trends": cards,
                },
                "context": result["context"],
                "errors": result.get("errors"),
            },
        }

    if intent.name == "show_current_trends":
        trends = await active_trends(session, user_id, limit=10)
        cards = _trend_cards(trends)
        text = "Текущие активные тренды:\n" + "\n".join([f"{idx + 1}. {card['topic']}" for idx, card in enumerate(cards)]) if cards else "Активных трендов пока нет. Напишите: «Найди новые тренды»."
        return {"text": text, "action": {"type": intent.name, "status": "completed", "trends": cards}}

    if intent.name == "create_content_plan":
        message_context = _latest_message_context(history)
        if message_context.get("action") == "add_trend_to_plan" or intent.params.get("action") == "add_trend_to_plan":
            trend_id = await _resolve_selected_trend_id(session, user_id, message, history, intent)
            if not trend_id:
                return {
                    "text": "Выберите тренд, который нужно добавить в контент-план.",
                    "action": {"type": intent.name, "status": "needs_trend_selection", "action_required": "select_trend"},
                }
            try:
                result = await add_trend_to_draft_plan(session, user_id, trend_id, profile)
            except HTTPException as exc:
                return {
                    "text": f"Не удалось добавить тренд в контент-план: {exc.detail}",
                    "action": {"type": intent.name, "status": "needs_trend", "action_required": "find_trends"},
                }
            return {
                "text": f"Добавил тренд «{result['trend']['topic']}» в черновик контент-плана.",
                "action": {
                    "type": intent.name,
                    "status": "completed",
                    "plan": result["plan"],
                    "items": [result["item"]],
                    "trend": result["trend"],
                },
            }
        try:
            plan = await create_weekly_content_plan(session, user_id, profile, title="Content plan from chat")
        except HTTPException as exc:
            return {
                "text": f"Пока не могу создать контент-план: {exc.detail}. Сначала нужно найти тренды для вашего профиля. Напишите: «Найди тренды».",
                "action": {"type": intent.name, "status": "needs_trends", "action_required": "find_trends"},
            }
        text = "Я создал общий контент-план на основе найденных трендов и сохранил его в Content plans."
        return {
            "text": text,
            "action": {
                "type": intent.name,
                "status": "done",
                "plan": plan["plan"],
                "summary": plan.get("summary"),
                "items": plan["items"],
                "data": {
                    "content_plan_id": str(plan["plan"]["id"]),
                    "summary": plan.get("summary"),
                    "items": plan["items"],
                    "selected_trends": plan.get("selected_trends", []),
                },
            },
        }

    if False and intent.name == "create_content_plan":
        try:
            plan = await create_weekly_content_plan(session, user_id, profile, title="Content plan from chat")
        except HTTPException as exc:
            return {
                "text": f"Пока не могу создать контент-план: {exc.detail}. Напишите «Найди новые тренды», затем повторите запрос.",
                "action": {"type": intent.name, "status": "needs_trends"},
            }
        text = f"Сделал контент-план на неделю: {len(plan['items'])} слотов. План сохранён в Content plans."
        return {"text": text, "action": {"type": intent.name, "status": "completed", "plan": plan["plan"], "items": plan["items"]}}

    if intent.name == "edit_content_plan":
        plan = await latest_content_plan(session, user_id)
        if not plan:
            return {"text": "Не нашёл контент-план для редактирования. Сначала напишите: «Сделай контент-план на неделю».", "action": {"type": intent.name, "status": "needs_plan"}}
        return {"text": "Какой слот изменить? Напишите номер слота и новое значение: платформа, формат, дата, время или идея.", "action": {"type": intent.name, "status": "needs_clarification", "plan": plan["plan"], "items": plan["items"]}}

    if intent.name == "generate_posts":
        message_context = _latest_message_context(history)
        platform = _platform_from_message(message, intent.params)
        is_plural_posts = bool(re.search(r"(?:посты|posts)", message.lower()))
        if _mentions_specific_trend(message, message_context) or platform or not is_plural_posts:
            trend_id = await _resolve_selected_trend_id(session, user_id, message, history, intent)
            if not trend_id:
                trend_id = _latest_trend_id_from_history(history)
            if not trend_id:
                return {
                    "text": "Выберите тренд, по которому нужно создать пост. Можно нажать кнопку «Создать пост» на карточке тренда или написать: «по второму тренду сделай пост».",
                    "action": {"type": intent.name, "status": "needs_trend_selection", "action_required": "select_trend"},
                }
            try:
                result = await generate_post_from_trend_id(session, user_id, profile, trend_id, platform=platform, use_llm=True)
            except HTTPException as exc:
                return {
                    "text": f"Не удалось создать пост по выбранному тренду: {exc.detail}. Покажите текущие тренды или запустите поиск трендов заново.",
                    "action": {"type": intent.name, "status": "needs_trend", "action_required": "find_trends"},
                }
            platform_text = f" для {platform}" if platform else ""
            text = f"Создал черновик поста{platform_text} по тренду «{result['trend']['topic']}» и сохранил его в Generated posts."
            return {"text": text, "action": {"type": intent.name, "status": "completed", "post": await enrich_generated_post(session, user_id, result["post"]), "trend": result["trend"]}}
        if re.search(r"(?:тренд|trend)", message.lower()):
            try:
                result = await generate_post_from_trend_message(session, user_id, profile, message, use_llm=True)
            except HTTPException as exc:
                return {
                    "text": f"Пока не могу сделать пост по тренду: {exc.detail}. Напишите «Покажи тренды» или «Найди новые тренды».",
                    "action": {"type": intent.name, "status": "needs_trend", "action_required": "find_trends"},
                }
            text = f"Сгенерировал пост по тренду «{result['trend']['topic']}» и сохранил его в Generated posts."
            return {"text": text, "action": {"type": intent.name, "status": "completed", "post": await enrich_generated_post(session, user_id, result["post"]), "trend": result["trend"]}}
        try:
            result = await generate_from_latest_plan(session, user_id, profile, use_llm=True)
        except HTTPException as exc:
            return {
                "text": f"Пока не могу сгенерировать посты: {exc.detail}. Сначала создайте контент-план или попросите пост по конкретному тренду.",
                "action": {"type": intent.name, "status": "needs_plan", "action_required": "find_trends"},
            }
        text = f"Сгенерировал посты из последнего контент-плана: {len(result['created'])}."
        return {"text": text, "action": {"type": intent.name, "status": "completed", "posts": await enrich_generated_posts(session, user_id, result["created"])}}

    if intent.name == "regenerate_post" and _post_id_from_history(history):
        mode = _regeneration_mode_from_message(message)
        post = await regenerate_post(session, user_id, _post_id_from_history(history) or "", profile, use_llm=True, mode=mode)
        return {"text": "Перегенерировал выбранный пост и сохранил новый черновик.", "action": {"type": intent.name, "status": "completed", "post": await enrich_generated_post(session, user_id, post)}}

    if intent.name == "regenerate_post":
        return {"text": "Выберите пост, который нужно переделать.", "action": {"type": intent.name, "status": "needs_post_selection", "action_required": "select_post"}}
        posts = await fetch_all(session, "SELECT * FROM generated_posts WHERE user_id = :user_id ORDER BY generated_at DESC LIMIT 1", {"user_id": user_id})
        if not posts:
            return {"text": "Не нашёл пост для регенерации. Сначала сгенерируйте пост.", "action": {"type": intent.name, "status": "needs_post", "action_required": "select_post"}}
        mode = _regeneration_mode_from_message(message)
        post = await regenerate_post(session, user_id, str(posts[0]["id"]), profile, use_llm=True, mode=mode)
        return {"text": "Перегенерировал последний пост и сохранил новый черновик.", "action": {"type": intent.name, "status": "completed", "post": await enrich_generated_post(session, user_id, post)}}

    if intent.name in {"edit_profile", "edit_audience_profile", "change_tone", "update_platforms"}:
        field = intent.params.get("field")
        value = intent.params.get("value")
        updated = await _update_profile(session, user_id, profile, field, value)
        await save_generation_run(
            session,
            user_id=user_id,
            run_type="chat_action",
            provider=None,
            agent_name="chat_action_service",
            input_payload={"intent": intent.name, "field": field, "value": value},
            output_payload={"updated": {field: value}},
            status="completed",
        )
        return {
            "text": f"Обновил поле «{field}». Хотите пересобрать тренды, контент-план или посты под новые данные?",
            "profile": updated,
            "action": {"type": intent.name, "status": "completed", "updated": {field: value}},
        }

    if intent.name == "content_plan_analytics":
        plan = await latest_content_plan(session, user_id)
        if not plan:
            return {"text": "Не нашёл контент-план для аналитики. Сначала создайте план.", "action": {"type": intent.name, "status": "needs_plan"}}
        items = plan["items"]
        platforms: dict[str, int] = {}
        statuses: dict[str, int] = {}
        for item in items:
            platforms[item["platform"]] = platforms.get(item["platform"], 0) + 1
            statuses[item["status"]] = statuses.get(item["status"], 0) + 1
        text = f"Аналитика плана: {len(items)} слотов, платформы: {', '.join(platforms.keys()) or '-'}."
        return {"text": text, "action": {"type": intent.name, "status": "completed", "plan": plan["plan"], "items": items, "analytics": {"platforms": platforms, "statuses": statuses}}}

    if intent.name == "recommendations" or (intent.name == "general_chat" and _asks_for_recommendations(message)):
        recs = await recommendations_for_user(session, user_id)
        if recs["data_quality"] == "none":
            text = "Пока данных мало: добавьте ручные метрики хотя бы для 3 постов, и я начну давать рекомендации по темам, форматам и платформам."
        else:
            prefix = "Рекомендации предварительные, потому что данных пока меньше 10 строк." if recs["data_quality"] == "limited" else "Вот что сейчас видно по ручным метрикам."
            bullets = "\n".join(f"- {item}" for item in recs.get("recommendations", [])[:5])
            next_actions = "\n".join(f"- {item}" for item in recs.get("next_actions", [])[:3])
            text = f"{prefix}\n\n{bullets or '- Пока нет устойчивого паттерна.'}\n\nСледующие шаги:\n{next_actions}"
        return {"text": text, "action": {"type": "recommendations", "status": "completed", "recommendations": recs}}

    if intent.name == "edit_post" and (intent.params.get("status") or intent.params.get("action") == "save"):
        message_context = _latest_message_context(history)
        post_id = _post_id_from_history(history)
        if not post_id:
            return {"text": "Не нашёл пост для редактирования. Сначала сгенерируйте пост.", "action": {"type": intent.name, "status": "needs_post_selection", "action_required": "select_post"}}
        next_status = intent.params.get("status") or "edited"
        post = await update_generated_post(
            session,
            user_id,
            post_id,
            draft_text=message_context.get("draft_text") if isinstance(message_context.get("draft_text"), str) else None,
            final_text=message_context.get("final_text") if isinstance(message_context.get("final_text"), str) else None,
            status=next_status,
        )
        return {"text": "Сохранил изменения поста.", "action": {"type": intent.name, "status": "completed", "post": await enrich_generated_post(session, user_id, post)}}

    if intent.name == "edit_post":
        posts = await fetch_all(session, "SELECT * FROM generated_posts WHERE user_id = :user_id ORDER BY generated_at DESC LIMIT 1", {"user_id": user_id})
        if not posts:
            return {"text": "Не нашёл пост для редактирования. Сначала сгенерируйте пост.", "action": {"type": intent.name, "status": "needs_post", "action_required": "select_post"}}
        return {"text": "Как изменить последний пост? Напишите новое финальное содержание или конкретную правку.", "action": {"type": intent.name, "status": "needs_clarification", "post": await enrich_generated_post(session, user_id, posts[0])}}

    if intent.name == "explain_profile":
        return {"text": _profile_text(profile), "action": {"type": intent.name, "status": "completed"}}

    if intent.name == "explain_trend":
        trends = await active_trends(session, user_id, limit=10)
        if not trends:
            return {"text": "Пока нет активных трендов для объяснения.", "action": {"type": intent.name, "status": "no_trends"}}
        trend = trends[0]
        text = f"Тренд: {trend['topic']}\n{trend.get('summary') or ''}\nКлючевые слова: {', '.join(trend.get('keywords') or [])}"
        return {"text": text, "action": {"type": intent.name, "status": "completed", "trend": trend}}

    try:
        general_context = await _compact_general_context(session, user_id, profile, history)
        text, provider = await answer_with_llm(message, general_context)
        await save_generation_run(
            session,
            user_id=user_id,
            run_type="general_chat",
            provider=provider,
            agent_name="chat_action_service",
            input_payload={"message": message},
            output_payload={"text": text},
            status="completed",
        )
        return {"text": text, "action": {"type": "general_chat", "status": "completed"}}
    except OpenAIChatUnavailable:
        general_context = await _compact_general_context(session, user_id, profile, history)
        text = _general_fallback(message, general_context)
        await save_generation_run(
            session,
            user_id=user_id,
            run_type="general_chat",
            provider=None,
            agent_name="chat_action_service",
            input_payload={"message": message},
            output_payload={"fallback_used": True},
            status="fallback_used",
            error_message="LLM unavailable",
        )
        return {
            "text": text,
            "action": {"type": "general_chat", "status": "fallback_used"},
        }
