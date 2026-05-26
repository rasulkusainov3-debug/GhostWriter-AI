from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import fetch_all, fetch_one


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _data_quality(rows: int) -> str:
    if rows < 3:
        return "none"
    if rows < 10:
        return "limited"
    return "usable"


def _terms(value: Any) -> set[str]:
    return {term for term in re.split(r"\W+", str(value or "").lower()) if len(term) > 2}


def _matches_pattern(trend: dict[str, Any], pattern: dict[str, Any]) -> bool:
    keywords = trend.get("keywords") or []
    keyword_text = keywords if isinstance(keywords, str) else " ".join(str(item) for item in keywords)
    trend_terms = _terms(trend.get("topic")) | _terms(keyword_text)
    pattern_terms = _terms(pattern.get("topic")) | _terms(pattern.get("platform")) | _terms(pattern.get("format"))
    return bool(trend_terms & pattern_terms)


async def build_analytics_context(session: AsyncSession, user_id: str) -> dict[str, Any]:
    totals = await fetch_one(
        session,
        """
        SELECT
            COUNT(*) AS rows,
            COALESCE(AVG(engagement_rate), 0) AS avg_er
        FROM post_metrics
        WHERE user_id = :user_id AND source = 'manual'
        """,
        {"user_id": user_id},
    )
    rows = _as_int((totals or {}).get("rows"))
    quality = _data_quality(rows)
    top_trends = await fetch_all(
        session,
        """
        SELECT
            t.id,
            t.topic,
            COALESCE(AVG(pm.engagement_rate), 0) AS avg_engagement_rate,
            COALESCE(SUM(pm.views), 0) AS total_views,
            COALESCE(SUM(pm.impressions), 0) AS total_impressions,
            COALESCE(SUM(pm.likes + pm.comments + pm.shares + pm.saves + pm.clicks + pm.reactions), 0) AS total_engagements,
            COUNT(pm.id) AS metrics_rows
        FROM trends t
        JOIN generated_posts gp ON gp.trend_id = t.id AND gp.user_id = t.user_id
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        WHERE t.user_id = :user_id
        GROUP BY t.id, t.topic
        HAVING COUNT(pm.id) > 0
        ORDER BY avg_engagement_rate DESC, total_engagements DESC
        LIMIT 6
        """,
        {"user_id": user_id},
    )
    weak_trends = await fetch_all(
        session,
        """
        SELECT
            t.id,
            t.topic,
            COALESCE(AVG(pm.engagement_rate), 0) AS avg_engagement_rate,
            COALESCE(SUM(pm.views), 0) AS total_views,
            COALESCE(SUM(pm.impressions), 0) AS total_impressions,
            COUNT(pm.id) AS metrics_rows
        FROM trends t
        JOIN generated_posts gp ON gp.trend_id = t.id AND gp.user_id = t.user_id
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        WHERE t.user_id = :user_id
        GROUP BY t.id, t.topic
        HAVING COUNT(pm.id) > 0
        ORDER BY avg_engagement_rate ASC, total_views ASC, total_impressions ASC
        LIMIT 6
        """,
        {"user_id": user_id},
    )
    best_platforms = await fetch_all(
        session,
        """
        SELECT gp.platform, COALESCE(AVG(pm.engagement_rate), 0) AS avg_engagement_rate, COUNT(pm.id) AS metrics_rows
        FROM generated_posts gp
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        WHERE gp.user_id = :user_id
        GROUP BY gp.platform
        ORDER BY avg_engagement_rate DESC, metrics_rows DESC
        LIMIT 5
        """,
        {"user_id": user_id},
    )
    best_formats = await fetch_all(
        session,
        """
        SELECT gp.format, COALESCE(AVG(pm.engagement_rate), 0) AS avg_engagement_rate, COUNT(pm.id) AS metrics_rows
        FROM generated_posts gp
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        WHERE gp.user_id = :user_id
        GROUP BY gp.format
        ORDER BY avg_engagement_rate DESC, metrics_rows DESC
        LIMIT 5
        """,
        {"user_id": user_id},
    )
    best_posting_times = await fetch_all(
        session,
        """
        SELECT
            EXTRACT(HOUR FROM sp.scheduled_for)::INT AS hour,
            COALESCE(AVG(pm.engagement_rate), 0) AS avg_engagement_rate,
            COUNT(pm.id) AS metrics_rows
        FROM scheduled_posts sp
        JOIN post_metrics pm ON pm.scheduled_post_id = sp.id AND pm.user_id = sp.user_id
        WHERE sp.user_id = :user_id
        GROUP BY hour
        ORDER BY avg_engagement_rate DESC, metrics_rows DESC
        LIMIT 5
        """,
        {"user_id": user_id},
    )
    low_posts = await fetch_all(
        session,
        """
        SELECT
            gp.id,
            gp.platform,
            gp.format,
            gp.trend_id,
            t.topic AS trend_topic,
            COALESCE(AVG(pm.engagement_rate), 0) AS avg_engagement_rate,
            COALESCE(SUM(pm.views), 0) AS total_views,
            COALESCE(SUM(pm.impressions), 0) AS total_impressions,
            MAX(pm.metric_date) AS latest_metric_date
        FROM generated_posts gp
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        LEFT JOIN trends t ON t.id = gp.trend_id AND t.user_id = gp.user_id
        WHERE gp.user_id = :user_id
        GROUP BY gp.id, gp.platform, gp.format, gp.trend_id, t.topic
        HAVING AVG(pm.engagement_rate) < 2.5
        ORDER BY avg_engagement_rate ASC, latest_metric_date DESC
        LIMIT 8
        """,
        {"user_id": user_id},
    )
    visual = await fetch_one(
        session,
        """
        SELECT
            COALESCE(AVG(pm.engagement_rate) FILTER (WHERE pa.id IS NOT NULL), 0) AS with_visual_avg_er,
            COALESCE(AVG(pm.engagement_rate) FILTER (WHERE pa.id IS NULL), 0) AS without_visual_avg_er,
            COUNT(pm.id) FILTER (WHERE pa.id IS NOT NULL) AS with_visual_rows,
            COUNT(pm.id) FILTER (WHERE pa.id IS NULL) AS without_visual_rows
        FROM generated_posts gp
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        LEFT JOIN post_assets pa ON pa.post_id = gp.id AND pa.user_id = gp.user_id AND pa.is_selected = true
        WHERE gp.user_id = :user_id
        """,
        {"user_id": user_id},
    )
    visual_impact = {
        "known": _as_int((visual or {}).get("with_visual_rows")) >= 3 and _as_int((visual or {}).get("without_visual_rows")) >= 3,
        "with_visual_avg_er": _as_float((visual or {}).get("with_visual_avg_er")),
        "without_visual_avg_er": _as_float((visual or {}).get("without_visual_avg_er")),
    }
    guidance = build_guidance(quality, top_trends, weak_trends, best_platforms, best_formats, visual_impact)
    return {
        "data_quality": quality,
        "metrics_source": "manual",
        "metrics_rows": rows,
        "top_performing_trends": top_trends,
        "weak_performing_trends": weak_trends,
        "best_platforms": best_platforms,
        "best_formats": best_formats,
        "best_posting_times": best_posting_times,
        "best_topics": [{"topic": item.get("topic"), "avg_engagement_rate": item.get("avg_engagement_rate")} for item in top_trends[:5]],
        "low_engagement_posts": low_posts,
        "visual_impact": visual_impact,
        "guidance": guidance,
    }


def build_guidance(
    data_quality: str,
    top_trends: list[dict[str, Any]],
    weak_trends: list[dict[str, Any]],
    best_platforms: list[dict[str, Any]],
    best_formats: list[dict[str, Any]],
    visual_impact: dict[str, Any],
) -> list[str]:
    if data_quality == "none":
        return ["Not enough manual metrics yet. Add at least 3 metric rows before using analytics feedback."]
    guidance = []
    if data_quality == "limited":
        guidance.append("Recommendations are preliminary because there are fewer than 10 manual metric rows.")
    if best_platforms:
        guidance.append(f"Prioritize {best_platforms[0].get('platform')} when it fits the content goal.")
    if best_formats:
        guidance.append(f"Use more {best_formats[0].get('format')} format posts when appropriate.")
    if top_trends:
        guidance.append(f"Reuse angles similar to: {top_trends[0].get('topic')}.")
    if data_quality == "usable" and weak_trends:
        guidance.append(f"Avoid repeating weak angle without changes: {weak_trends[0].get('topic')}.")
    if visual_impact.get("known") and visual_impact.get("with_visual_avg_er", 0) > visual_impact.get("without_visual_avg_er", 0):
        guidance.append("Selected visuals appear to improve engagement; prefer visual-backed posts.")
    return guidance


def rank_trends_with_feedback(trends: list[dict[str, Any]], analytics_context: dict[str, Any]) -> list[dict[str, Any]]:
    quality = analytics_context.get("data_quality")
    if quality == "none":
        return trends
    top_patterns = analytics_context.get("top_performing_trends") or []
    best_topics = analytics_context.get("best_topics") or []
    weak_patterns = analytics_context.get("weak_performing_trends") or []
    usable = quality == "usable"
    soft = quality == "limited"

    def score(trend: dict[str, Any]) -> float:
        feedback = 0.0
        for pattern in top_patterns:
            if _matches_pattern(trend, pattern):
                feedback += 10 if usable else 3
        for pattern in best_topics:
            if _matches_pattern(trend, pattern):
                feedback += 6 if usable else 2
        if usable:
            for pattern in weak_patterns:
                if _matches_pattern(trend, pattern):
                    feedback -= 6
        return feedback

    ranked = []
    for index, trend in enumerate(trends):
        item = dict(trend)
        item["analytics_feedback_score"] = score(item)
        ranked.append((item["analytics_feedback_score"], -index, item))
    ranked.sort(key=lambda value: (value[0], value[1]), reverse=True)
    return [item for _feedback, _index, item in ranked]


def build_generation_guidance(profile: dict[str, Any] | None, analytics_context: dict[str, Any]) -> dict[str, Any]:
    quality = analytics_context.get("data_quality")
    if quality == "none":
        return {"data_quality": quality, "metrics_source": "manual", "guidance": []}
    return {
        "data_quality": quality,
        "metrics_source": "manual",
        "best_platforms": [item.get("platform") for item in analytics_context.get("best_platforms", [])[:3] if item.get("platform")],
        "best_formats": [item.get("format") for item in analytics_context.get("best_formats", [])[:3] if item.get("format")],
        "best_topics": [item.get("topic") for item in analytics_context.get("best_topics", [])[:5] if item.get("topic")],
        "avoid_patterns": [item.get("topic") for item in analytics_context.get("weak_performing_trends", [])[:3] if item.get("topic")] if quality == "usable" else [],
        "low_engagement_post_ids": [str(item.get("id")) for item in analytics_context.get("low_engagement_posts", [])[:5] if item.get("id")],
        "visual_impact": analytics_context.get("visual_impact"),
        "guidance": analytics_context.get("guidance", [])[:6],
        "profile_goal": (profile or {}).get("goal"),
    }


async def recommendations_for_user(session: AsyncSession, user_id: str) -> dict[str, Any]:
    context = await build_analytics_context(session, user_id)
    recommendations = list(context.get("guidance") or [])
    if context["data_quality"] == "none":
        next_actions = ["Add manual metrics for at least 3 published or scheduled posts."]
    else:
        next_actions = ["Use these patterns in the next content plan.", "Regenerate low-engagement posts with a stronger hook and CTA."]
    return {
        "data_quality": context["data_quality"],
        "metrics_source": context["metrics_source"],
        "recommendations": recommendations,
        "top_patterns": context.get("top_performing_trends", [])[:5],
        "weak_patterns": context.get("weak_performing_trends", [])[:5],
        "best_platforms": context.get("best_platforms", [])[:5],
        "best_formats": context.get("best_formats", [])[:5],
        "low_engagement_posts": context.get("low_engagement_posts", [])[:8],
        "next_actions": next_actions,
    }
