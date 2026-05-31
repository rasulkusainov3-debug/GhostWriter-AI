from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import text

from app.db.session import AsyncSessionLocal


DEMO_EMAIL = "n.a.98.r.a@gmail.com"
DEMO_PLAN_TITLE = "Контент-план для личного бренда Python-разработчика"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _monday(anchor: date | None = None) -> date:
    today = anchor or date.today()
    return today - timedelta(days=today.weekday())


def _engagement_rate(metric: dict[str, int]) -> float:
    engagements = sum(metric.get(key, 0) for key in ("likes", "comments", "shares", "saves", "clicks", "reactions"))
    denominator = max(metric.get("impressions", 0), metric.get("reach", 0), metric.get("views", 0), 1)
    return round((engagements / denominator) * 100, 2)


async def _fetch_one(session, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    result = await session.execute(text(sql), params or {})
    row = result.mappings().first()
    return dict(row) if row else None


async def _fetch_all(session, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = await session.execute(text(sql), params or {})
    return [dict(row) for row in result.mappings().all()]


async def _execute(session, sql: str, params: dict[str, Any] | None = None) -> None:
    await session.execute(text(sql), params or {})


async def _cleanup_demo_data(session, user_id: str) -> None:
    await _execute(
        session,
        """
        DELETE FROM generation_runs
        WHERE user_id = :user_id
          AND (
            input_payload ->> 'demo_seed' = 'true'
            OR output_payload ->> 'demo_seed' = 'true'
            OR provider = 'demo'
          )
        """,
        {"user_id": user_id},
    )
    await _execute(session, "DELETE FROM post_metrics WHERE user_id = :user_id AND raw_metrics ->> 'demo_seed' = 'true'", {"user_id": user_id})
    await _execute(session, "DELETE FROM scheduled_posts WHERE user_id = :user_id AND payload ->> 'demo_seed' = 'true'", {"user_id": user_id})
    await _execute(session, "DELETE FROM post_assets WHERE user_id = :user_id AND metadata ->> 'demo_seed' = 'true'", {"user_id": user_id})
    await _execute(session, "DELETE FROM generated_posts WHERE user_id = :user_id AND stats ->> 'demo_seed' = 'true'", {"user_id": user_id})
    await _execute(
        session,
        """
        DELETE FROM content_plan_items
        WHERE plan_id IN (
          SELECT id FROM content_plans
          WHERE user_id = :user_id AND title = :title
        )
        """,
        {"user_id": user_id, "title": DEMO_PLAN_TITLE},
    )
    await _execute(session, "DELETE FROM content_plans WHERE user_id = :user_id AND title = :title", {"user_id": user_id, "title": DEMO_PLAN_TITLE})
    await _execute(
        session,
        """
        DELETE FROM trend_sources
        WHERE trend_id IN (SELECT id FROM trends WHERE user_id = :user_id AND source = 'demo')
           OR raw_post_id IN (SELECT id FROM raw_posts WHERE user_id = :user_id AND source = 'demo')
        """,
        {"user_id": user_id},
    )
    await _execute(session, "DELETE FROM trends WHERE user_id = :user_id AND source = 'demo'", {"user_id": user_id})
    await _execute(session, "DELETE FROM raw_posts WHERE user_id = :user_id AND source = 'demo'", {"user_id": user_id})
    await _execute(
        session,
        "DELETE FROM trend_runs WHERE user_id = :user_id AND input_profile_snapshot ->> 'demo_seed' = 'true'",
        {"user_id": user_id},
    )
    await _execute(session, "DELETE FROM social_accounts WHERE user_id = :user_id AND token_metadata ->> 'demo_seed' = 'true'", {"user_id": user_id})


async def _upsert_profile(session, user_id: str) -> None:
    raw_answers = {
        "demo_seed": True,
        "interview": {
            "name": "Арслан",
            "profession": "Python-разработчик",
            "goal": "найти клиентов через экспертный контент",
            "audience": "IT-компании, стартапы, предприниматели, HR и технические руководители",
            "content_preferences": "короткие практические разборы, кейсы, честные выводы",
        },
        "personality": {
            "voice": "экспертный, но дружелюбный",
            "writing_style": "короткие абзацы, практические примеры, прямой CTA",
            "preferred_structure": ["hook", "insight", "case", "CTA"],
            "vocabulary_preferences": ["практика", "бизнес-результат", "автоматизация"],
            "avoid_phrases": ["слишком много теории", "канцелярит", "политика"],
            "example_post_ids": [],
        },
    }
    lifecycle_notes = {"demo_seed": True, "note": "Demo analytics profile for presentation"}
    await _execute(
        session,
        """
        INSERT INTO user_profiles (
          user_id, name, niche, profession, goal, tone, audience, avoid,
          user_values, platforms, raw_answers,
          profile_confirmation_status, audience_confirmation_status,
          profile_confirmed_at, audience_confirmed_at, lifecycle_notes
        )
        VALUES (
          :user_id, :name, :niche, :profession, :goal, :tone, :audience, :avoid,
          CAST(:user_values AS JSONB), CAST(:platforms AS JSONB), CAST(:raw_answers AS JSONB),
          'confirmed', 'confirmed', NOW(), NOW(), CAST(:lifecycle_notes AS JSONB)
        )
        ON CONFLICT (user_id)
        DO UPDATE SET
          name = EXCLUDED.name,
          niche = EXCLUDED.niche,
          profession = EXCLUDED.profession,
          goal = EXCLUDED.goal,
          tone = EXCLUDED.tone,
          audience = EXCLUDED.audience,
          avoid = EXCLUDED.avoid,
          user_values = EXCLUDED.user_values,
          platforms = EXCLUDED.platforms,
          raw_answers = user_profiles.raw_answers || EXCLUDED.raw_answers,
          profile_confirmation_status = 'confirmed',
          audience_confirmation_status = 'confirmed',
          profile_confirmed_at = NOW(),
          audience_confirmed_at = NOW(),
          lifecycle_notes = user_profiles.lifecycle_notes || EXCLUDED.lifecycle_notes
        """,
        {
            "user_id": user_id,
            "name": "Арслан",
            "niche": "IT",
            "profession": "Python-разработчик",
            "goal": "найти клиентов",
            "tone": "дружелюбный, экспертный",
            "audience": "IT-компании, стартапы, предприниматели, HR и технические руководители",
            "avoid": "политика, слишком много теории, канцелярит",
            "user_values": _json(["честность", "рост", "практичность", "открытость"]),
            "platforms": _json(["Telegram", "LinkedIn"]),
            "raw_answers": _json(raw_answers),
            "lifecycle_notes": _json(lifecycle_notes),
        },
    )


async def _seed_trends(session, user_id: str) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    trend_run = await _fetch_one(
        session,
        """
        INSERT INTO trend_runs (
          user_id, status, input_profile_snapshot, queries_used,
          raw_posts_found, trends_found, started_at, finished_at
        )
        VALUES (
          :user_id, 'completed', CAST(:snapshot AS JSONB), CAST(:queries AS JSONB),
          14, 7, NOW() - INTERVAL '2 hours', NOW() - INTERVAL '1 hour 52 minutes'
        )
        RETURNING id
        """,
        {
            "user_id": user_id,
            "snapshot": _json({"demo_seed": True, "niche": "IT", "goal": "найти клиентов", "platforms": ["Telegram", "LinkedIn"]}),
            "queries": _json(["python personal brand clients", "linkedin for developers", "telegram channel IT expert", "aws lambda serverless"]),
        },
    )
    trend_run_id = str(trend_run["id"])
    raw_posts_data = [
        ("Python-разработчик: как находить клиентов через экспертный контент", 1460, 38, "https://example.com/demo/python-clients"),
        ("LinkedIn для разработчика: посты без воды и саморекламы", 980, 18, "https://example.com/demo/linkedin-dev"),
        ("AI Engineering vs Software Engineering in 2026", 3120, 76, "https://example.com/demo/ai-engineering"),
        ("Telegram-канал как витрина экспертизы IT-специалиста", 740, 22, "https://example.com/demo/telegram-brand"),
        ("AWS Lambda и serverless: как объяснять бизнес-ценность", 1880, 41, "https://example.com/demo/aws-lambda"),
        ("Python freelance: как упаковать навыки для B2B-клиентов", 1670, 29, "https://example.com/demo/python-freelance"),
        ("Технические кейсы, которые приводят лиды", 1290, 31, "https://example.com/demo/case-posts"),
        ("Как писать посты, которые приводят клиентов", 2210, 54, "https://example.com/demo/client-posts"),
        ("Serverless для стартапа: быстрее проверить гипотезу", 860, 13, "https://example.com/demo/serverless-startup"),
        ("AI-автоматизация процессов для малого бизнеса", 2760, 65, "https://example.com/demo/ai-automation"),
        ("Как объяснять сложные IT-решения предпринимателям", 930, 16, "https://example.com/demo/explain-it"),
        ("Личный бренд разработчика: доверие через практику", 1540, 34, "https://example.com/demo/dev-trust"),
        ("Как Telegram и LinkedIn работают вместе", 1120, 21, "https://example.com/demo/telegram-linkedin"),
        ("Python automation: маленькие скрипты, большой бизнес-эффект", 1980, 47, "https://example.com/demo/python-automation"),
    ]
    raw_posts: list[dict[str, Any]] = []
    for title, score, comments, url in raw_posts_data:
        row = await _fetch_one(
            session,
            """
            INSERT INTO raw_posts (
              user_id, source, title, content, url, media_type, score, comments,
              engagement_rate, niche, platform_tags, published_at, collected_at
            )
            VALUES (
              :user_id, 'demo', :title, :content, :url, 'text', :score, :comments,
              :engagement_rate, 'IT', CAST(:platform_tags AS JSONB),
              NOW() - (:days_ago * INTERVAL '1 day'), NOW() - (:days_ago * INTERVAL '1 day')
            )
            RETURNING id, title
            """,
            {
                "user_id": user_id,
                "title": title,
                "content": f"Демо-материал для аналитики: {title}. Подходит для экспертного контента Python-разработчика.",
                "url": url,
                "score": score,
                "comments": comments,
                "engagement_rate": round(((score * 0.05 + comments * 3) / max(score, 1)) * 100, 2),
                "platform_tags": _json(["LinkedIn", "Telegram", "demo"]),
                "days_ago": len(raw_posts) + 1,
            },
        )
        raw_posts.append(row)

    trends_data = [
        {
            "topic": "Python-разработчик: как находить клиентов через экспертный контент",
            "keywords": ["python", "личный бренд", "клиенты", "экспертный контент", "LinkedIn"],
            "posts_count": 5,
            "google_score": 84,
            "final_score": 93,
            "summary": "Тема показывает, как разработчику превращать техническую экспертизу в доверие и входящие заявки от клиентов.",
        },
        {
            "topic": "AI Engineering vs Software Engineering in 2026",
            "keywords": ["AI engineering", "software engineering", "production AI", "automation"],
            "posts_count": 4,
            "google_score": 79,
            "final_score": 88,
            "summary": "Компании переходят от AI-демо к production-системам, и это усиливает спрос на инженеров с backend-опытом.",
        },
        {
            "topic": "Telegram как канал личного бренда для IT-специалиста",
            "keywords": ["Telegram", "личный бренд", "IT эксперт", "канал", "аудитория"],
            "posts_count": 3,
            "google_score": 73,
            "final_score": 82,
            "summary": "Telegram помогает прогревать аудиторию короткими наблюдениями, кейсами и регулярными техническими заметками.",
        },
        {
            "topic": "Как писать посты, которые приводят клиентов",
            "keywords": ["контент", "лиды", "CTA", "B2B", "экспертиза"],
            "posts_count": 4,
            "google_score": 71,
            "final_score": 80,
            "summary": "Практичные посты с понятным результатом лучше работают для B2B, чем общие рассуждения о технологиях.",
        },
        {
            "topic": "AWS Lambda и serverless как способ показать экспертность",
            "keywords": ["AWS Lambda", "serverless", "backend", "cost saving", "startup"],
            "posts_count": 3,
            "google_score": 67,
            "final_score": 76,
            "summary": "Serverless-темы позволяют объяснять бизнесу скорость запуска, экономию и масштабирование на понятных примерах.",
        },
        {
            "topic": "Python freelance: как упаковать навыки для B2B-клиентов",
            "keywords": ["Python freelance", "B2B", "automation", "portfolio", "clients"],
            "posts_count": 3,
            "google_score": 69,
            "final_score": 74,
            "summary": "Фрилансерам важно описывать не технологии сами по себе, а бизнес-процессы, которые они ускоряют.",
        },
        {
            "topic": "LinkedIn для разработчика: как писать посты без воды",
            "keywords": ["LinkedIn", "developer content", "technical writing", "expert tone"],
            "posts_count": 2,
            "google_score": 62,
            "final_score": 70,
            "summary": "LinkedIn-посты разработчика лучше работают, когда показывают опыт, вывод и конкретную пользу для клиента.",
        },
    ]
    trends: list[dict[str, Any]] = []
    for item in trends_data:
        row = await _fetch_one(
            session,
            """
            INSERT INTO trends (
              user_id, trend_run_id, source, topic, keywords, posts_count,
              google_score, google_trend, final_score, youtube_insights,
              summary, collected_at, expires_at
            )
            VALUES (
              :user_id, :trend_run_id, 'demo', :topic, CAST(:keywords AS JSONB), :posts_count,
              :google_score, 'rising', :final_score, CAST(:youtube_insights AS JSONB),
              :summary, NOW() - INTERVAL '1 hour', NOW() + INTERVAL '14 days'
            )
            RETURNING id, topic
            """,
            {
                "user_id": user_id,
                "trend_run_id": trend_run_id,
                "topic": item["topic"],
                "keywords": _json(item["keywords"]),
                "posts_count": item["posts_count"],
                "google_score": item["google_score"],
                "final_score": item["final_score"],
                "youtube_insights": _json({"demo_seed": True, "best_format": "case", "best_posting_day": "Tuesday"}),
                "summary": item["summary"],
            },
        )
        trends.append(row)

    for index, trend in enumerate(trends):
        source_ids = [raw_posts[index * 2 % len(raw_posts)]["id"], raw_posts[(index * 2 + 1) % len(raw_posts)]["id"]]
        for raw_post_id in source_ids:
            await _execute(
                session,
                """
                INSERT INTO trend_sources (trend_id, raw_post_id, relevance_score)
                VALUES (:trend_id, :raw_post_id, :relevance_score)
                ON CONFLICT (trend_id, raw_post_id) DO NOTHING
                """,
                {"trend_id": trend["id"], "raw_post_id": raw_post_id, "relevance_score": round(0.88 - index * 0.04, 2)},
            )
    return trend_run_id, raw_posts, trends


async def _seed_content_plan(session, user_id: str, trends: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    week_start = _monday() + timedelta(days=7)
    plan = await _fetch_one(
        session,
        """
        INSERT INTO content_plans (user_id, title, week_start, status)
        VALUES (:user_id, :title, :week_start, 'active')
        RETURNING *
        """,
        {"user_id": user_id, "title": DEMO_PLAN_TITLE, "week_start": week_start},
    )
    items_data = [
        ("LinkedIn", "кейс", "Как Python-разработчику показать бизнес-результат через один автоматизированный процесс", 0, time(10, 0)),
        ("Telegram", "совет", "Короткий пост о том, почему технический контент должен начинаться с проблемы клиента", 1, time(12, 30)),
        ("LinkedIn", "экспертный пост", "AI Engineering: почему backend-опыт становится конкурентным преимуществом", 2, time(11, 0)),
        ("Telegram", "разбор", "AWS Lambda: простой пример serverless-решения для стартапа", 3, time(15, 0)),
        ("LinkedIn", "разбор", "Как LinkedIn и Telegram усиливают личный бренд разработчика", 4, time(9, 30)),
        ("Telegram", "короткий пост", "Python freelance: как объяснять клиенту ценность автоматизации", 5, time(18, 0)),
        ("LinkedIn", "совет", "Посты без воды: структура hook → insight → case → CTA", 6, time(10, 30)),
    ]
    items: list[dict[str, Any]] = []
    for index, (platform, fmt, idea, day_offset, scheduled_time) in enumerate(items_data):
        trend = trends[index % len(trends)]
        item = await _fetch_one(
            session,
            """
            INSERT INTO content_plan_items (
              plan_id, trend_id, platform, format, post_idea,
              scheduled_date, scheduled_time, slot_order, status
            )
            VALUES (
              :plan_id, :trend_id, :platform, :format, :post_idea,
              :scheduled_date, :scheduled_time, :slot_order, :status
            )
            RETURNING *
            """,
            {
                "plan_id": plan["id"],
                "trend_id": trend["id"],
                "platform": platform,
                "format": fmt,
                "post_idea": idea,
                "scheduled_date": week_start + timedelta(days=day_offset),
                "scheduled_time": scheduled_time,
                "slot_order": index + 1,
                "status": "generated" if index < 5 else "planned",
            },
        )
        items.append(item)
    return plan, items


async def _seed_posts(session, user_id: str, trends: list[dict[str, Any]], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    posts_data = [
        {
            "platform": "LinkedIn",
            "format": "кейс",
            "status": "published",
            "draft": "Рабочий черновик: показать, как Python-разработчик превращает автоматизацию в понятный бизнес-результат.",
            "final": (
                "Многие компании хотят AI и автоматизацию, но застревают на уровне демо.\n\n"
                "На практике ценность появляется не в красивой презентации, а в одном процессе, который стал быстрее: меньше ручных действий, меньше ошибок, понятный результат для команды.\n\n"
                "Для Python-разработчика это сильная точка позиционирования. Клиенту не нужен список библиотек. Ему важно понять, какую задачу вы снимете с бизнеса и как быстро это окупится.\n\n"
                "Если вы хотите привлекать B2B-клиентов через контент, показывайте не только код, а путь: проблема → решение → измеримый эффект."
            ),
        },
        {
            "platform": "Telegram",
            "format": "совет",
            "status": "published",
            "draft": "Черновик для Telegram: коротко объяснить, почему технический пост должен начинаться с боли клиента.",
            "final": (
                "Технический пост лучше начинать не с технологии, а с проблемы.\n\n"
                "Не: «Я использовал FastAPI, Redis и Celery».\n"
                "Лучше: «Команда тратила 6 часов в неделю на ручную проверку заявок. Мы автоматизировали этот шаг и сократили время до 20 минут».\n\n"
                "Так клиент видит не стек, а пользу. А стек уже становится доказательством вашей экспертизы."
            ),
        },
        {
            "platform": "LinkedIn",
            "format": "экспертный пост",
            "status": "approved",
            "draft": "Черновик: AI Engineering требует backend-мышления, мониторинга, данных и интеграций.",
            "final": (
                "AI Engineering в 2026 году всё меньше похож на «просто вызвать модель».\n\n"
                "Реальная работа начинается после прототипа: данные, мониторинг, стоимость запросов, безопасность, fallback-логика и интеграция с бизнес-процессами.\n\n"
                "Именно здесь backend-разработчики получают преимущество. Они умеют строить системы, которые не только впечатляют на демо, но и стабильно работают каждый день.\n\n"
                "Вопрос для команд: какая часть вашего AI-проекта уже готова к production, а какая всё ещё живёт в демо-режиме?"
            ),
        },
        {
            "platform": "Telegram",
            "format": "разбор",
            "status": "scheduled",
            "draft": "Черновик: AWS Lambda как понятный пример serverless для стартапа.",
            "final": (
                "AWS Lambda полезно объяснять через бизнес-сценарий.\n\n"
                "Например: стартапу нужно обрабатывать заявки, но нагрузка нерегулярная. Поднимать постоянный сервер дорого и избыточно. Lambda запускается только когда приходит событие, а значит команда платит ближе к реальному использованию.\n\n"
                "Это не магия и не универсальное решение. Но для быстрых гипотез, фоновых задач и интеграций serverless часто даёт хороший баланс скорости и стоимости."
            ),
        },
        {
            "platform": "LinkedIn",
            "format": "разбор",
            "status": "draft",
            "draft": "Черновик: показать, как Telegram и LinkedIn играют разные роли в личном бренде.",
            "final": (
                "LinkedIn и Telegram решают разные задачи в личном бренде разработчика.\n\n"
                "LinkedIn помогает находить новую аудиторию: рекрутеров, предпринимателей, технических лидов и потенциальных клиентов.\n\n"
                "Telegram лучше работает как пространство доверия: там можно чаще делиться наблюдениями, мини-кейсами, процессом и выводами из практики.\n\n"
                "Сильная связка выглядит так: LinkedIn привлекает внимание, Telegram прогревает доверие, а ваши кейсы показывают, почему с вами стоит работать."
            ),
        },
        {
            "platform": "Telegram",
            "format": "короткий пост",
            "status": "approved",
            "draft": "Черновик: как Python-фрилансеру говорить на языке бизнеса.",
            "final": (
                "Python-фрилансеру важно продавать не «скрипты», а результат.\n\n"
                "Клиенту понятнее так:\n"
                "• заявки обрабатываются быстрее\n"
                "• отчёты собираются автоматически\n"
                "• менеджеры меньше копируют данные вручную\n"
                "• бизнес видит цифры вовремя\n\n"
                "Технология важна, но сначала покажите, какую рутину вы убираете."
            ),
        },
    ]
    posts: list[dict[str, Any]] = []
    for index, item in enumerate(posts_data):
        trend = trends[index % len(trends)]
        plan_item = items[index % len(items)]
        generated_at = datetime.now(UTC) - timedelta(days=8 - index)
        published_at = generated_at + timedelta(hours=6) if item["status"] == "published" else None
        post = await _fetch_one(
            session,
            """
            INSERT INTO generated_posts (
              user_id, plan_item_id, trend_id, platform, format,
              draft_text, final_text, status, llm_provider, stats,
              generated_at, published_at
            )
            VALUES (
              :user_id, :plan_item_id, :trend_id, :platform, :format,
              :draft_text, :final_text, :status, 'demo', CAST(:stats AS JSONB),
              :generated_at, :published_at
            )
            RETURNING *
            """,
            {
                "user_id": user_id,
                "plan_item_id": plan_item["id"],
                "trend_id": trend["id"],
                "platform": item["platform"],
                "format": item["format"],
                "draft_text": item["draft"],
                "final_text": item["final"],
                "status": item["status"],
                "stats": _json({"demo_seed": True, "chars": len(item["final"]), "hashtags": ["#python", "#automation", "#personalbrand"]}),
                "generated_at": generated_at,
                "published_at": published_at,
            },
        )
        posts.append(post)
    return posts


async def _seed_assets(session, user_id: str, posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assets_data = [
        (
            "pexels",
            "https://images.pexels.com/photos/1181675/pexels-photo-1181675.jpeg?auto=compress&cs=tinysrgb&w=1200",
            "https://www.pexels.com/photo/person-using-laptop-computer-1181675/",
            "Christina Morillo",
            "Python developer working on a laptop",
        ),
        (
            "unsplash",
            "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80",
            "https://unsplash.com/photos/person-using-macbook-pro-npxXWgQ33ZQ",
            "Unsplash",
            "Workspace with analytics dashboard",
        ),
        (
            "pexels",
            "https://images.pexels.com/photos/3861969/pexels-photo-3861969.jpeg?auto=compress&cs=tinysrgb&w=1200",
            "https://www.pexels.com/photo/crop-programmer-working-on-laptop-3861969/",
            "ThisIsEngineering",
            "Engineer reviewing code and infrastructure",
        ),
    ]
    assets: list[dict[str, Any]] = []
    for post, (provider, preview_url, source_url, author, alt_text) in zip(posts[:3], assets_data, strict=False):
        asset = await _fetch_one(
            session,
            """
            INSERT INTO post_assets (
              user_id, post_id, asset_type, provider, status, image_prompt,
              search_query, preview_url, source_url, author, alt_text, metadata, is_selected
            )
            VALUES (
              :user_id, :post_id, 'image', :provider, 'selected', :image_prompt,
              :search_query, :preview_url, :source_url, :author, :alt_text,
              CAST(:metadata AS JSONB), true
            )
            RETURNING *
            """,
            {
                "user_id": user_id,
                "post_id": post["id"],
                "provider": provider,
                "image_prompt": f"Professional editorial visual for {post['platform']} post about Python automation and personal brand",
                "search_query": "python developer automation personal brand workspace",
                "preview_url": preview_url,
                "source_url": source_url,
                "author": author,
                "alt_text": alt_text,
                "metadata": _json({"demo_seed": True, "provider_configured": True}),
            },
        )
        assets.append(asset)
    return assets


async def _seed_social_and_schedules(session, user_id: str, posts: list[dict[str, Any]], assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    account = await _fetch_one(
        session,
        """
        INSERT INTO social_accounts (
          user_id, platform, display_name, external_account_id, account_url,
          connection_status, scopes, token_ref, token_metadata
        )
        VALUES (
          :user_id, 'Telegram', 'GhostWriter Telegram channel', '@ghostwriter_demo_channel',
          'https://t.me/ghostwriter_demo_channel', 'manual', CAST(:scopes AS JSONB), NULL,
          CAST(:token_metadata AS JSONB)
        )
        RETURNING *
        """,
        {"user_id": user_id, "scopes": _json(["publish"]), "token_metadata": _json({"demo_seed": True})},
    )
    schedules: list[dict[str, Any]] = []
    schedule_specs = [
        (posts[0], "published", datetime.now(UTC) - timedelta(days=5, hours=2), assets[0] if assets else None),
        (posts[3], "scheduled", datetime.now(UTC) + timedelta(days=2, hours=4), assets[2] if len(assets) > 2 else None),
    ]
    for post, status, scheduled_for, asset in schedule_specs:
        schedule = await _fetch_one(
            session,
            """
            INSERT INTO scheduled_posts (
              user_id, generated_post_id, social_account_id, selected_asset_id,
              platform, scheduled_for, status, payload, attempt_count,
              last_attempt_at, published_at, external_post_id, external_post_url
            )
            VALUES (
              :user_id, :generated_post_id, :social_account_id, :selected_asset_id,
              'Telegram', :scheduled_for, :status, CAST(:payload AS JSONB), :attempt_count,
              :last_attempt_at, :published_at, :external_post_id, :external_post_url
            )
            RETURNING *
            """,
            {
                "user_id": user_id,
                "generated_post_id": post["id"],
                "social_account_id": account["id"],
                "selected_asset_id": asset["id"] if asset else None,
                "scheduled_for": scheduled_for,
                "status": status,
                "payload": _json({
                    "demo_seed": True,
                    "final_text": post["final_text"],
                    "platform": "Telegram",
                    "selected_asset": {"preview_url": asset["preview_url"] if asset else None},
                }),
                "attempt_count": 1 if status == "published" else 0,
                "last_attempt_at": scheduled_for if status == "published" else None,
                "published_at": scheduled_for + timedelta(minutes=3) if status == "published" else None,
                "external_post_id": "demo-telegram-1001" if status == "published" else None,
                "external_post_url": "https://t.me/ghostwriter_demo_channel/1001" if status == "published" else None,
            },
        )
        schedules.append(schedule)
    return schedules


async def _seed_metrics(session, user_id: str, posts: list[dict[str, Any]], schedules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base_date = date.today() - timedelta(days=6)
    metric_specs = [
        (0, 2100, 1650, 3400, 145, 18, 15, 42, 28, 68),
        (1, 1300, 1020, 2100, 84, 11, 8, 24, 18, 41),
        (2, 980, 800, 1300, 53, 7, 6, 16, 9, 25),
        (3, 740, 630, 820, 32, 4, 3, 10, 6, 15),
        (4, 1560, 1210, 1850, 96, 14, 11, 30, 20, 48),
        (5, 450, 390, 620, 21, 2, 2, 7, 4, 9),
    ]
    metrics: list[dict[str, Any]] = []
    for index, impressions, reach, views, likes, comments, shares, saves, clicks, reactions in metric_specs:
        post = posts[index % len(posts)]
        schedule = next((item for item in schedules if str(item["generated_post_id"]) == str(post["id"])), None)
        values = {
            "impressions": impressions,
            "reach": reach,
            "views": views,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "saves": saves,
            "clicks": clicks,
            "reactions": reactions,
        }
        metric = await _fetch_one(
            session,
            """
            INSERT INTO post_metrics (
              user_id, generated_post_id, scheduled_post_id, platform, metric_date, source,
              impressions, reach, views, likes, comments, shares, saves, clicks, reactions,
              engagement_rate, raw_metrics
            )
            VALUES (
              :user_id, :generated_post_id, :scheduled_post_id, :platform, :metric_date, 'manual',
              :impressions, :reach, :views, :likes, :comments, :shares, :saves, :clicks, :reactions,
              :engagement_rate, CAST(:raw_metrics AS JSONB)
            )
            RETURNING *
            """,
            {
                "user_id": user_id,
                "generated_post_id": post["id"],
                "scheduled_post_id": schedule["id"] if schedule else None,
                "platform": post["platform"],
                "metric_date": base_date + timedelta(days=index),
                **values,
                "engagement_rate": _engagement_rate(values),
                "raw_metrics": _json({"demo_seed": True, "source_note": "Manual demo metrics for presentation"}),
            },
        )
        metrics.append(metric)
    return metrics


async def _seed_generation_runs(session, user_id: str, trend_run_id: str, posts: list[dict[str, Any]], plan: dict[str, Any], assets: list[dict[str, Any]]) -> None:
    runs = [
        ("trend_search", "Analyzer Agent", {"trend_run_id": trend_run_id}, {"raw_posts_found": 14, "trends_found": 7}),
        ("content_plan", "Creator Agent", {"profile": "Python developer demo"}, {"content_plan_id": str(plan["id"]), "items": 7}),
        ("post_generation", "Creator Agent", {"posts_requested": 6}, {"generated_posts": [str(post["id"]) for post in posts]}),
        ("visual_generation", "Creator Agent", {"provider": "demo"}, {"assets": [str(asset["id"]) for asset in assets]}),
        ("manual_metrics_upsert", "Analytics", {"source": "manual"}, {"metrics_rows": 6}),
    ]
    for offset, (run_type, agent_name, input_payload, output_payload) in enumerate(runs):
        await _execute(
            session,
            """
            INSERT INTO generation_runs (
              user_id, run_type, provider, agent_name,
              input_payload, output_payload, status, created_at
            )
            VALUES (
              :user_id, :run_type, 'demo', :agent_name,
              CAST(:input_payload AS JSONB), CAST(:output_payload AS JSONB),
              'completed', NOW() - (:offset * INTERVAL '20 minutes')
            )
            """,
            {
                "user_id": user_id,
                "run_type": run_type,
                "agent_name": agent_name,
                "input_payload": _json({"demo_seed": True, **input_payload}),
                "output_payload": _json({"demo_seed": True, **output_payload}),
                "offset": offset,
            },
        )


async def seed_demo_analytics(email: str) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        user = await _fetch_one(session, "SELECT id, email FROM users WHERE email = :email", {"email": email})
        if not user:
            raise RuntimeError(f"User with email {email} not found.")
        user_id = str(user["id"])
        await _cleanup_demo_data(session, user_id)
        await _upsert_profile(session, user_id)
        trend_run_id, raw_posts, trends = await _seed_trends(session, user_id)
        plan, items = await _seed_content_plan(session, user_id, trends)
        posts = await _seed_posts(session, user_id, trends, items)
        assets = await _seed_assets(session, user_id, posts)
        schedules = await _seed_social_and_schedules(session, user_id, posts, assets)
        metrics = await _seed_metrics(session, user_id, posts, schedules)
        await _seed_generation_runs(session, user_id, trend_run_id, posts, plan, assets)
        await session.commit()
        return {
            "user_id": user_id,
            "profile": 1,
            "trend_runs": 1,
            "raw_posts": len(raw_posts),
            "trends": len(trends),
            "content_plans": 1,
            "content_plan_items": len(items),
            "generated_posts": len(posts),
            "post_assets": len(assets),
            "social_accounts": 1,
            "scheduled_posts": len(schedules),
            "post_metrics": len(metrics),
            "generation_runs": 5,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed realistic demo analytics data for an existing GhostWriter AI user.")
    parser.add_argument("--email", default=DEMO_EMAIL, help="Existing user email to attach demo data to.")
    args = parser.parse_args()
    try:
        summary = asyncio.run(seed_demo_analytics(args.email))
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print("Demo analytics seed completed.")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
