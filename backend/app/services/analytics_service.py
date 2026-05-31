from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import fetch_all, fetch_one


PROFILE_FIELDS = ["name", "niche", "profession", "goal", "tone", "audience", "avoid"]
PROFILE_COMPLETENESS_FIELDS = [
    "name",
    "niche",
    "profession",
    "goal",
    "tone",
    "audience",
    "avoid",
    "user_values",
    "platforms",
    "personality",
]


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rows_to_counts(rows: Iterable[dict[str, Any]], key: str = "status") -> dict[str, int]:
    return {str(row.get(key) or "unknown"): _as_int(row.get("count")) for row in rows}


def _as_list(value: Any) -> list[Any]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _profile_field_value(profile: dict[str, Any], field: str) -> Any:
    if field == "personality":
        return _as_dict(profile.get("raw_answers")).get("personality")
    return profile.get(field)


def _activity_recommendations(profile: dict[str, Any], activity: dict[str, int], missing: list[str]) -> list[str]:
    recommendations: list[str] = []
    raw_answers = _as_dict(profile.get("raw_answers"))
    personality = _as_dict(raw_answers.get("personality"))
    example_ids = _as_list(personality.get("example_post_ids"))
    platforms = [str(item).lower() for item in _as_list(profile.get("platforms"))]

    if "audience" in missing:
        recommendations.append("Сформулируйте 2-3 типовые боли аудитории, чтобы посты точнее попадали в запрос.")
    if "tone" in missing:
        recommendations.append("Добавьте тон коммуникации: экспертный, дружелюбный, прямой или другой подходящий стиль.")
    if not platforms:
        recommendations.append("Добавьте хотя бы одну платформу публикации, например Telegram или LinkedIn.")
    elif "linkedin" not in platforms and _filled(profile.get("goal")):
        recommendations.append("Добавьте LinkedIn как канал для B2B-охвата, если цель связана с экспертностью или клиентами.")
    if len(example_ids) < 2 and activity.get("generated_posts", 0) > 0:
        recommendations.append("Добавьте 2-3 утверждённых поста как примеры стиля для более точной генерации.")
    if activity.get("metrics_rows", 0) == 0 and activity.get("published_posts", 0) > 0:
        recommendations.append("Добавьте ручные метрики к опубликованным постам, чтобы рекомендации стали точнее.")
    if not recommendations:
        recommendations.append("Профиль готов к генерации контента. Следующий шаг — сравнить темы по метрикам и усиливать лучшие форматы.")
    return recommendations[:4]


async def get_profile_analytics(session: AsyncSession, user_id: str) -> dict[str, Any]:
    profile = await fetch_one(session, "SELECT * FROM user_profiles WHERE user_id = :user_id", {"user_id": user_id})
    if not profile:
        return {
            "completeness": 0,
            "missing": ["profile"],
            "profile": None,
            "style": {},
            "platforms": [],
            "values": [],
            "tone": None,
            "activity": {
                "active_trends": 0,
                "generated_posts": 0,
                "selected_visuals": 0,
                "published_posts": 0,
                "metrics_rows": 0,
            },
            "recommendations": ["Заполните профиль, чтобы аналитика могла оценить готовность к генерации контента."],
        }

    raw_answers = _as_dict(profile.get("raw_answers"))
    personality = _as_dict(raw_answers.get("personality"))
    filled = [field for field in PROFILE_COMPLETENESS_FIELDS if _filled(_profile_field_value(profile, field))]
    missing = [field for field in PROFILE_COMPLETENESS_FIELDS if field not in filled]
    active_trends = await fetch_one(
        session,
        "SELECT COUNT(*) AS count FROM trends WHERE user_id = :user_id AND expires_at > NOW()",
        {"user_id": user_id},
    )
    generated_posts = await fetch_one(
        session,
        "SELECT COUNT(*) AS count FROM generated_posts WHERE user_id = :user_id",
        {"user_id": user_id},
    )
    selected_visuals = await fetch_one(
        session,
        "SELECT COUNT(*) AS count FROM post_assets WHERE user_id = :user_id AND is_selected = true",
        {"user_id": user_id},
    )
    published_posts = await fetch_one(
        session,
        """
        SELECT COUNT(*) AS count
        FROM scheduled_posts
        WHERE user_id = :user_id AND status = 'published'
        """,
        {"user_id": user_id},
    )
    metrics_rows = await fetch_one(
        session,
        "SELECT COUNT(*) AS count FROM post_metrics WHERE user_id = :user_id",
        {"user_id": user_id},
    )
    activity = {
        "active_trends": _as_int((active_trends or {}).get("count")),
        "generated_posts": _as_int((generated_posts or {}).get("count")),
        "selected_visuals": _as_int((selected_visuals or {}).get("count")),
        "published_posts": _as_int((published_posts or {}).get("count")),
        "metrics_rows": _as_int((metrics_rows or {}).get("count")),
    }
    profile_payload = {
        "name": profile.get("name"),
        "niche": profile.get("niche"),
        "profession": profile.get("profession"),
        "goal": profile.get("goal"),
        "tone": profile.get("tone"),
        "audience": profile.get("audience"),
        "avoid": profile.get("avoid"),
        "user_values": _as_list(profile.get("user_values")),
        "platforms": _as_list(profile.get("platforms")),
    }
    return {
        "completeness": round(len(filled) / len(PROFILE_COMPLETENESS_FIELDS) * 100),
        "missing": missing,
        "profile": profile_payload,
        "style": {
            "voice": personality.get("voice") or profile.get("tone"),
            "writing_style": personality.get("writing_style"),
            "preferred_structure": _as_list(personality.get("preferred_structure")),
            "vocabulary_preferences": _as_list(personality.get("vocabulary_preferences")),
            "avoid_phrases": _as_list(personality.get("avoid_phrases")),
            "example_post_ids": _as_list(personality.get("example_post_ids")),
        },
        "activity": activity,
        "recommendations": _activity_recommendations(profile, activity, missing),
        "platforms": profile_payload["platforms"],
        "values": profile_payload["user_values"],
        "tone": profile.get("tone"),
    }


async def get_social_analytics(session: AsyncSession, user_id: str) -> dict[str, Any]:
    by_source = await fetch_all(
        session,
        """
        SELECT source, COUNT(*) AS count, COALESCE(AVG(score), 0) AS avg_score
        FROM raw_posts
        WHERE user_id = :user_id
        GROUP BY source
        ORDER BY count DESC
        """,
        {"user_id": user_id},
    )
    top_topics = await fetch_all(
        session,
        """
        SELECT title, score, comments, url
        FROM raw_posts
        WHERE user_id = :user_id
        ORDER BY score DESC NULLS LAST
        LIMIT 10
        """,
        {"user_id": user_id},
    )
    return {"by_source": by_source, "top_topics": top_topics}


async def get_trend_analytics(session: AsyncSession, user_id: str) -> dict[str, Any]:
    by_source = await fetch_all(
        session,
        """
        SELECT source, COUNT(*) AS count, COALESCE(AVG(final_score), 0) AS avg_final_score
        FROM trends
        WHERE user_id = :user_id AND expires_at > NOW()
        GROUP BY source
        ORDER BY count DESC
        """,
        {"user_id": user_id},
    )
    top = await fetch_all(
        session,
        """
        WITH source_counts AS (
            SELECT trend_id, COUNT(*) AS source_count
            FROM trend_sources
            GROUP BY trend_id
        ),
        post_counts AS (
            SELECT trend_id, COUNT(*) AS generated_posts_count
            FROM generated_posts
            WHERE user_id = :user_id
            GROUP BY trend_id
        ),
        schedule_counts AS (
            SELECT
                gp.trend_id,
                COUNT(DISTINCT sp.id) FILTER (WHERE sp.status IN ('scheduled', 'publishing', 'published')) AS scheduled_posts_count,
                COUNT(DISTINCT sp.id) FILTER (WHERE sp.status = 'published') AS published_posts_count
            FROM generated_posts gp
            JOIN scheduled_posts sp ON sp.generated_post_id = gp.id AND sp.user_id = gp.user_id
            WHERE gp.user_id = :user_id
            GROUP BY gp.trend_id
        ),
        metric_totals AS (
            SELECT
                gp.trend_id,
                COUNT(DISTINCT pm.generated_post_id) AS metrics_posts_count,
                COALESCE(SUM(pm.views), 0) AS total_views,
                COALESCE(SUM(pm.impressions), 0) AS total_impressions,
                COALESCE(AVG(pm.engagement_rate), 0) AS avg_engagement_rate,
                COALESCE(SUM(pm.likes + pm.comments + pm.shares + pm.saves + pm.clicks + pm.reactions), 0) AS total_engagements
            FROM generated_posts gp
            JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
            WHERE gp.user_id = :user_id
            GROUP BY gp.trend_id
        )
        SELECT
            t.id,
            t.topic,
            t.final_score,
            t.posts_count,
            t.keywords,
            t.summary,
            COALESCE(sc.source_count, 0) AS source_count,
            COALESCE(pc.generated_posts_count, 0) AS generated_posts_count,
            COALESCE(sch.scheduled_posts_count, 0) AS scheduled_posts_count,
            COALESCE(sch.published_posts_count, 0) AS published_posts_count,
            COALESCE(mt.metrics_posts_count, 0) AS metrics_posts_count,
            COALESCE(mt.total_views, 0) AS total_views,
            COALESCE(mt.total_impressions, 0) AS total_impressions,
            COALESCE(mt.avg_engagement_rate, 0) AS avg_engagement_rate,
            CASE
                WHEN COALESCE(mt.metrics_posts_count, 0) = 0 THEN 'unknown'
                WHEN COALESCE(mt.avg_engagement_rate, 0) >= 5 OR COALESCE(mt.total_engagements, 0) >= 20 THEN 'positive'
                ELSE 'neutral'
            END AS feedback_signal
        FROM trends t
        LEFT JOIN source_counts sc ON sc.trend_id = t.id
        LEFT JOIN post_counts pc ON pc.trend_id = t.id
        LEFT JOIN schedule_counts sch ON sch.trend_id = t.id
        LEFT JOIN metric_totals mt ON mt.trend_id = t.id
        WHERE t.user_id = :user_id AND t.expires_at > NOW()
        ORDER BY COALESCE(t.final_score, 0) DESC, COALESCE(sc.source_count, 0) DESC
        LIMIT 10
        """,
        {"user_id": user_id},
    )
    totals = await fetch_one(
        session,
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE expires_at > NOW()) AS active,
            COUNT(*) FILTER (WHERE expires_at <= NOW()) AS expired
        FROM trends
        WHERE user_id = :user_id
        """,
        {"user_id": user_id},
    )
    return {
        "total": _as_int((totals or {}).get("total")),
        "active": _as_int((totals or {}).get("active")),
        "expired": _as_int((totals or {}).get("expired")),
        "by_source": by_source,
        "top": top,
        "feedback_signal": "known" if any(item.get("feedback_signal") != "unknown" for item in top) else "unknown",
    }


async def get_posts_analytics(session: AsyncSession, user_id: str) -> dict[str, Any]:
    status_rows = await fetch_all(
        session,
        "SELECT status, COUNT(*) AS count FROM generated_posts WHERE user_id = :user_id GROUP BY status ORDER BY status",
        {"user_id": user_id},
    )
    schedule_rows = await fetch_all(
        session,
        "SELECT status, COUNT(*) AS count FROM scheduled_posts WHERE user_id = :user_id GROUP BY status ORDER BY status",
        {"user_id": user_id},
    )
    asset_coverage = await fetch_one(
        session,
        """
        SELECT
            COUNT(gp.id) AS total_posts,
            COUNT(gp.id) FILTER (WHERE selected.id IS NOT NULL) AS posts_with_selected_visual,
            COUNT(gp.id) FILTER (WHERE selected.id IS NULL) AS posts_without_visual
        FROM generated_posts gp
        LEFT JOIN post_assets selected
            ON selected.post_id = gp.id AND selected.user_id = gp.user_id AND selected.is_selected = true
        WHERE gp.user_id = :user_id
        """,
        {"user_id": user_id},
    )
    recent_posts = await fetch_all(
        session,
        """
        SELECT
            gp.id,
            gp.platform,
            gp.format,
            gp.status,
            gp.generated_at,
            gp.published_at,
            t.topic AS trend_topic,
            selected.preview_url AS selected_visual_url,
            active_schedule.status AS schedule_status,
            active_schedule.scheduled_for,
            latest_metric.metric_date AS latest_metric_date,
            latest_metric.views AS latest_metric_views,
            latest_metric.impressions AS latest_metric_impressions,
            latest_metric.engagement_rate AS latest_metric_engagement_rate
        FROM generated_posts gp
        LEFT JOIN trends t ON t.id = gp.trend_id AND t.user_id = gp.user_id
        LEFT JOIN post_assets selected ON selected.post_id = gp.id AND selected.user_id = gp.user_id AND selected.is_selected = true
        LEFT JOIN LATERAL (
            SELECT status, scheduled_for
            FROM scheduled_posts sp
            WHERE sp.generated_post_id = gp.id
              AND sp.user_id = gp.user_id
              AND sp.status IN ('scheduled', 'publishing', 'published', 'failed')
            ORDER BY sp.created_at DESC
            LIMIT 1
        ) active_schedule ON true
        LEFT JOIN LATERAL (
            SELECT metric_date, views, impressions, engagement_rate
            FROM post_metrics pm
            WHERE pm.generated_post_id = gp.id
              AND pm.user_id = gp.user_id
            ORDER BY pm.metric_date DESC, pm.updated_at DESC
            LIMIT 1
        ) latest_metric ON true
        WHERE gp.user_id = :user_id
        ORDER BY gp.generated_at DESC
        LIMIT 10
        """,
        {"user_id": user_id},
    )
    metrics_totals = await fetch_one(
        session,
        """
        SELECT
            COUNT(*) AS manual_metrics_rows,
            COALESCE(SUM(impressions), 0) AS total_impressions,
            COALESCE(SUM(reach), 0) AS total_reach,
            COALESCE(SUM(views), 0) AS total_views,
            COALESCE(SUM(likes + comments + shares + saves + clicks + reactions), 0) AS total_engagements,
            COALESCE(AVG(engagement_rate), 0) AS average_engagement_rate
        FROM post_metrics
        WHERE user_id = :user_id AND source = 'manual'
        """,
        {"user_id": user_id},
    )
    metrics_by_post = await fetch_all(
        session,
        """
        SELECT
            gp.id AS post_id,
            gp.platform,
            gp.format,
            gp.status,
            MAX(pm.metric_date) AS latest_metric_date,
            COALESCE(SUM(pm.impressions), 0) AS impressions,
            COALESCE(SUM(pm.views), 0) AS views,
            COALESCE(SUM(pm.likes + pm.comments + pm.shares + pm.saves + pm.clicks + pm.reactions), 0) AS engagements,
            COALESCE(AVG(pm.engagement_rate), 0) AS engagement_rate
        FROM generated_posts gp
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        WHERE gp.user_id = :user_id
        GROUP BY gp.id, gp.platform, gp.format, gp.status
        ORDER BY latest_metric_date DESC NULLS LAST
        LIMIT 25
        """,
        {"user_id": user_id},
    )
    top_posts_by_engagement = await fetch_all(
        session,
        """
        SELECT
            gp.id AS post_id,
            gp.platform,
            gp.format,
            gp.status,
            COALESCE(AVG(pm.engagement_rate), 0) AS engagement_rate,
            COALESCE(SUM(pm.views), 0) AS views,
            COALESCE(SUM(pm.impressions), 0) AS impressions
        FROM generated_posts gp
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        WHERE gp.user_id = :user_id
        GROUP BY gp.id, gp.platform, gp.format, gp.status
        ORDER BY engagement_rate DESC, views DESC, impressions DESC
        LIMIT 5
        """,
        {"user_id": user_id},
    )
    top_posts_by_views = await fetch_all(
        session,
        """
        SELECT
            gp.id AS post_id,
            gp.platform,
            gp.format,
            gp.status,
            COALESCE(SUM(pm.views), 0) AS views,
            COALESCE(SUM(pm.impressions), 0) AS impressions,
            COALESCE(AVG(pm.engagement_rate), 0) AS engagement_rate
        FROM generated_posts gp
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        WHERE gp.user_id = :user_id
        GROUP BY gp.id, gp.platform, gp.format, gp.status
        ORDER BY views DESC, impressions DESC
        LIMIT 5
        """,
        {"user_id": user_id},
    )
    return {
        "generated_posts_by_status": _rows_to_counts(status_rows),
        "scheduled_posts_by_status": _rows_to_counts(schedule_rows),
        "asset_coverage": {
            "total_posts": _as_int((asset_coverage or {}).get("total_posts")),
            "posts_with_selected_visual": _as_int((asset_coverage or {}).get("posts_with_selected_visual")),
            "posts_without_visual": _as_int((asset_coverage or {}).get("posts_without_visual")),
        },
        "recent_posts": recent_posts,
        "manual_metrics": {
            "rows": _as_int((metrics_totals or {}).get("manual_metrics_rows")),
            "total_impressions": _as_int((metrics_totals or {}).get("total_impressions")),
            "total_reach": _as_int((metrics_totals or {}).get("total_reach")),
            "total_views": _as_int((metrics_totals or {}).get("total_views")),
            "total_engagements": _as_int((metrics_totals or {}).get("total_engagements")),
            "average_engagement_rate": float((metrics_totals or {}).get("average_engagement_rate") or 0),
            "metrics_by_post": metrics_by_post,
            "top_posts_by_engagement": top_posts_by_engagement,
            "top_posts_by_views": top_posts_by_views,
        },
    }


async def get_content_plan_analytics(session: AsyncSession, user_id: str) -> dict[str, Any]:
    totals = await fetch_one(
        session,
        """
        SELECT
            COUNT(DISTINCT cp.id) AS total_plans,
            COUNT(cpi.id) AS total_items
        FROM content_plans cp
        LEFT JOIN content_plan_items cpi ON cpi.plan_id = cp.id
        WHERE cp.user_id = :user_id
        """,
        {"user_id": user_id},
    )
    plan_status_rows = await fetch_all(
        session,
        "SELECT status, COUNT(*) AS count FROM content_plans WHERE user_id = :user_id GROUP BY status ORDER BY status",
        {"user_id": user_id},
    )
    item_status_rows = await fetch_all(
        session,
        """
        SELECT cpi.status, COUNT(*) AS count
        FROM content_plan_items cpi
        JOIN content_plans cp ON cp.id = cpi.plan_id
        WHERE cp.user_id = :user_id
        GROUP BY cpi.status
        ORDER BY cpi.status
        """,
        {"user_id": user_id},
    )
    post_status_rows = await fetch_all(
        session,
        """
        SELECT gp.status, COUNT(*) AS count
        FROM generated_posts gp
        JOIN content_plan_items cpi ON cpi.id = gp.plan_item_id
        JOIN content_plans cp ON cp.id = cpi.plan_id
        WHERE cp.user_id = :user_id AND gp.user_id = :user_id
        GROUP BY gp.status
        ORDER BY gp.status
        """,
        {"user_id": user_id},
    )
    platform_distribution = await fetch_all(
        session,
        """
        SELECT cpi.platform, COUNT(*) AS count
        FROM content_plan_items cpi
        JOIN content_plans cp ON cp.id = cpi.plan_id
        WHERE cp.user_id = :user_id
        GROUP BY cpi.platform
        ORDER BY count DESC
        """,
        {"user_id": user_id},
    )
    format_distribution = await fetch_all(
        session,
        """
        SELECT cpi.format, COUNT(*) AS count
        FROM content_plan_items cpi
        JOIN content_plans cp ON cp.id = cpi.plan_id
        WHERE cp.user_id = :user_id
        GROUP BY cpi.format
        ORDER BY count DESC
        LIMIT 10
        """,
        {"user_id": user_id},
    )
    metrics_totals = await fetch_one(
        session,
        """
        SELECT
            COUNT(pm.id) AS metrics_rows,
            COUNT(DISTINCT gp.id) AS posts_with_metrics,
            COALESCE(SUM(pm.impressions), 0) AS total_impressions,
            COALESCE(SUM(pm.views), 0) AS total_views,
            COALESCE(SUM(pm.likes + pm.comments + pm.shares + pm.saves + pm.clicks + pm.reactions), 0) AS total_engagements,
            COALESCE(AVG(pm.engagement_rate), 0) AS average_engagement_rate
        FROM content_plans cp
        JOIN content_plan_items cpi ON cpi.plan_id = cp.id
        JOIN generated_posts gp ON gp.plan_item_id = cpi.id AND gp.user_id = cp.user_id
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        WHERE cp.user_id = :user_id
        """,
        {"user_id": user_id},
    )
    best_platforms = await fetch_all(
        session,
        """
        SELECT
            cpi.platform,
            COALESCE(AVG(pm.engagement_rate), 0) AS average_engagement_rate,
            COALESCE(SUM(pm.views), 0) AS total_views,
            COALESCE(SUM(pm.impressions), 0) AS total_impressions
        FROM content_plans cp
        JOIN content_plan_items cpi ON cpi.plan_id = cp.id
        JOIN generated_posts gp ON gp.plan_item_id = cpi.id AND gp.user_id = cp.user_id
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        WHERE cp.user_id = :user_id
        GROUP BY cpi.platform
        ORDER BY average_engagement_rate DESC, total_views DESC, total_impressions DESC
        LIMIT 5
        """,
        {"user_id": user_id},
    )
    best_formats = await fetch_all(
        session,
        """
        SELECT
            cpi.format,
            COALESCE(AVG(pm.engagement_rate), 0) AS average_engagement_rate,
            COALESCE(SUM(pm.views), 0) AS total_views,
            COALESCE(SUM(pm.impressions), 0) AS total_impressions
        FROM content_plans cp
        JOIN content_plan_items cpi ON cpi.plan_id = cp.id
        JOIN generated_posts gp ON gp.plan_item_id = cpi.id AND gp.user_id = cp.user_id
        JOIN post_metrics pm ON pm.generated_post_id = gp.id AND pm.user_id = gp.user_id
        WHERE cp.user_id = :user_id
        GROUP BY cpi.format
        ORDER BY average_engagement_rate DESC, total_views DESC, total_impressions DESC
        LIMIT 5
        """,
        {"user_id": user_id},
    )
    linked_post_statuses = _rows_to_counts(post_status_rows)
    approved_scheduled_published = sum(linked_post_statuses.get(status, 0) for status in ("approved", "scheduled", "published"))
    return {
        "total_plans": _as_int((totals or {}).get("total_plans")),
        "total_items": _as_int((totals or {}).get("total_items")),
        "plans_by_status": _rows_to_counts(plan_status_rows),
        "items_by_status": _rows_to_counts(item_status_rows),
        "generated_post_count": sum(linked_post_statuses.values()),
        "linked_generated_posts_by_status": linked_post_statuses,
        "approved_scheduled_published_count": approved_scheduled_published,
        "platform_distribution": platform_distribution,
        "format_distribution": format_distribution,
        "manual_metrics": {
            "rows": _as_int((metrics_totals or {}).get("metrics_rows")),
            "posts_with_metrics": _as_int((metrics_totals or {}).get("posts_with_metrics")),
            "total_impressions": _as_int((metrics_totals or {}).get("total_impressions")),
            "total_views": _as_int((metrics_totals or {}).get("total_views")),
            "total_engagements": _as_int((metrics_totals or {}).get("total_engagements")),
            "average_engagement_rate": float((metrics_totals or {}).get("average_engagement_rate") or 0),
            "best_platforms": best_platforms,
            "best_formats": best_formats,
        },
    }


async def get_social_account_analytics(session: AsyncSession, user_id: str) -> dict[str, Any]:
    connection_rows = await fetch_all(
        session,
        """
        SELECT connection_status, COUNT(*) AS count
        FROM social_accounts
        WHERE user_id = :user_id
        GROUP BY connection_status
        ORDER BY connection_status
        """,
        {"user_id": user_id},
    )
    platform_rows = await fetch_all(
        session,
        """
        SELECT platform, COUNT(*) AS count
        FROM social_accounts
        WHERE user_id = :user_id
        GROUP BY platform
        ORDER BY count DESC
        """,
        {"user_id": user_id},
    )
    scheduled_per_platform = await fetch_all(
        session,
        """
        SELECT platform, status, COUNT(*) AS count
        FROM scheduled_posts
        WHERE user_id = :user_id
        GROUP BY platform, status
        ORDER BY platform, status
        """,
        {"user_id": user_id},
    )
    total = await fetch_one(session, "SELECT COUNT(*) AS count FROM social_accounts WHERE user_id = :user_id", {"user_id": user_id})
    return {
        "total_accounts": _as_int((total or {}).get("count")),
        "accounts_by_connection_status": _rows_to_counts(connection_rows, "connection_status"),
        "platform_distribution": platform_rows,
        "scheduled_posts_per_platform": scheduled_per_platform,
        "metrics_missing": True,
    }


async def get_dashboard_analytics(session: AsyncSession, user_id: str) -> dict[str, Any]:
    profile = await get_profile_analytics(session, user_id)
    posts = await get_posts_analytics(session, user_id)
    trends = await get_trend_analytics(session, user_id)
    content_plans = await get_content_plan_analytics(session, user_id)
    raw_posts = await fetch_one(session, "SELECT COUNT(*) AS count FROM raw_posts WHERE user_id = :user_id", {"user_id": user_id})
    trend_runs = await fetch_one(session, "SELECT COUNT(*) AS count FROM trend_runs WHERE user_id = :user_id", {"user_id": user_id})
    recent_generation_runs = await fetch_all(
        session,
        """
        SELECT id, run_type, provider, agent_name, status, error_message, created_at
        FROM generation_runs
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        LIMIT 8
        """,
        {"user_id": user_id},
    )
    schedule_counts = posts["scheduled_posts_by_status"]
    manual_metrics = posts["manual_metrics"]
    return {
        "profile_completeness": profile["completeness"],
        "raw_posts_count": _as_int((raw_posts or {}).get("count")),
        "trends_count": trends["active"],
        "total_trends_count": trends["total"],
        "trend_runs_count": _as_int((trend_runs or {}).get("count")),
        "content_plans_count": content_plans["total_plans"],
        "generated_posts_by_status": posts["generated_posts_by_status"],
        "scheduled_posts_by_status": schedule_counts,
        "published_schedules_count": schedule_counts.get("published", 0),
        "failed_schedules_count": schedule_counts.get("failed", 0),
        "asset_coverage": posts["asset_coverage"],
        "manual_metrics": {
            "rows": manual_metrics["rows"],
            "total_impressions": manual_metrics["total_impressions"],
            "total_views": manual_metrics["total_views"],
            "total_engagements": manual_metrics["total_engagements"],
            "average_engagement_rate": manual_metrics["average_engagement_rate"],
        },
        "top_trends": trends["top"][:5],
        "recent_generation_runs": recent_generation_runs,
        "missing_metrics_flags": {
            "external_platform_metrics": True,
            "manual_metrics": manual_metrics["rows"] == 0,
        },
    }
