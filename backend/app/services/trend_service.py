from __future__ import annotations

import asyncio
import html
import json
import re
from collections import Counter
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import execute, fetch_all
from app.services.llm.base import LLMUnavailable
from app.services.llm.factory import generate_text_with_fallback
from app.services.run_tracking_service import (
    fail_trend_run,
    finish_trend_run,
    link_trend_sources,
    save_generation_run,
    start_trend_run,
)
from app.services.trend_adapter import trend_adapter

STOP_WORDS = {
    "и", "в", "на", "с", "по", "для", "что", "как", "это", "не", "или", "но", "уже",
    "the", "and", "for", "with", "from", "about", "into", "your", "you", "are", "this",
}

STOP_WORDS.update(
    {
        "continue", "reading", "read", "more", "click", "here", "home", "page", "login",
        "div", "class", "span", "href", "article", "posted", "comments", "img", "src", "alt",
        "для", "как", "что", "это", "или", "при", "над", "под", "читать", "далее",
    }
)

BAD_KEYWORD_PATTERNS = (
    "continue reading",
    "read more",
    "click here",
    "sign up",
    "log in",
    "subscribe",
    "newsletter",
    "div class",
    "class result",
    "result snippet",
    "img src",
)


def profile_search_context(profile: dict[str, Any]) -> dict[str, Any]:
    raw_answers = profile.get("raw_answers") or {}
    values = profile.get("user_values") or []
    platforms = profile.get("platforms") or []
    parts = [
        profile.get("niche"),
        profile.get("profession"),
        profile.get("goal"),
        profile.get("tone"),
        profile.get("audience"),
        profile.get("avoid"),
        ", ".join(values),
        ", ".join(platforms),
        ", ".join(raw_answers.get("social_links") or []),
    ]
    query = " ".join(str(part) for part in parts if part)
    return {
        "niche": profile.get("niche") or "общее",
        "query": query,
        "queries": build_profile_queries(profile),
        "sources": ["rss", "ddg"],
        "social_links": raw_answers.get("social_links") or [],
    }


def _compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def build_profile_queries(profile: dict[str, Any], broad: bool = False) -> list[str]:
    niche = _compact(profile.get("niche") or "personal brand")
    profession = _compact(profile.get("profession") or niche)
    goal = _compact(profile.get("goal") or "grow audience")
    audience = _compact(profile.get("audience") or "")
    platforms = profile.get("platforms") or []
    values = profile.get("user_values") or []
    raw_answers = profile.get("raw_answers") or {}
    region = _compact(raw_answers.get("region") or raw_answers.get("language") or "")
    platform_text = ", ".join(platforms) if platforms else "LinkedIn"
    value_text = ", ".join(values[:3]) if values else ""
    seeds = [
        f"{profession} how to find clients",
        f"{profession} personal brand LinkedIn",
        f"freelance {profession} content ideas",
        f"software developer client acquisition LinkedIn",
        f"{profession} personal brand {platform_text} trends",
        f"how {profession} {goal}",
        f"freelance {profession} content ideas",
        f"{profession} audience pain points {audience}",
        f"{profession} {goal} content strategy",
        f"{niche} creator trends {platform_text}",
        f"{profession} case studies {value_text}",
        f"{profession} LinkedIn content ideas",
        f"{profession} market trends {region}",
        f"{profession} как {goal}",
        f"личный бренд {profession}",
        f"контент идеи для {profession}",
        f"{profession} как найти клиентов",
    ]
    if broad:
        seeds.extend(
            [
                f"{niche} trends 2026",
                f"{niche} content marketing ideas",
                f"{niche} professional growth",
                "personal brand trends LinkedIn",
                "content ideas for experts",
            ]
        )
    unique: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        seed = _compact(seed)
        key = seed.lower()
        if seed and key not in seen:
            unique.append(seed)
            seen.add(key)
    return unique[:16 if broad else 10]


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"http\S+", " ", text)
    text = re.sub(r"[^\w\s\-]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _clean_keyword(value: Any) -> str:
    keyword = html.unescape(str(value or "")).strip().strip("'\"[]{}")
    keyword = re.sub(r"\\+u[0-9a-fA-F]{4}", " ", keyword)
    keyword = re.sub(r"[_|/]+", " ", keyword)
    keyword = re.sub(r"\s+", " ", keyword).strip(" ,.;:-")
    keyword = re.sub(r"(?<=[a-zа-я])(?=[A-ZА-Я])", " ", keyword)
    lower = keyword.lower()
    if not keyword or any(pattern in lower for pattern in BAD_KEYWORD_PATTERNS):
        return ""
    if lower.startswith(("http", "www.")) or len(keyword) > 48:
        return ""
    if re.search(r"\b(div|class|span|href|result__|snippet|img|src|alt)\b", lower):
        return ""
    words = [word for word in re.split(r"\s+", keyword) if word]
    if len(words) > 4:
        return ""
    if all(word.lower() in STOP_WORDS for word in words):
        return ""
    if len(set(words)) != len(words):
        keyword = " ".join(dict.fromkeys(words))
    return keyword


def clean_keywords(value: Any, fallback_text: str = "", max_keywords: int = 8) -> list[str]:
    raw: list[Any] = []
    if isinstance(value, list):
        raw = value
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    raw = parsed
            except Exception:
                raw = []
        if not raw:
            raw = re.split(r"[,;|]", stripped)
    if fallback_text:
        raw.extend(_keywords(fallback_text, top_n=max_keywords * 2))

    clean: list[str] = []
    seen: set[str] = set()
    for item in raw:
        keyword = _clean_keyword(item)
        key = keyword.lower()
        if keyword and key not in seen:
            clean.append(keyword)
            seen.add(key)
        if len(clean) >= max_keywords:
            break
    return clean


def _keywords(text: str, top_n: int = 8) -> list[str]:
    try:
        import yake

        extractor = yake.KeywordExtractor(lan="en", n=2, dedupLim=0.7, top=top_n, features=None)
        extracted = clean_keywords([kw for kw, _ in extractor.extract_keywords(text)], max_keywords=top_n)
        if extracted:
            return extracted
    except Exception:
        pass
    words = [word for word in _clean_text(text).split() if len(word) > 3 and word not in STOP_WORDS]
    return clean_keywords([word for word, _ in Counter(words).most_common(top_n * 2)], max_keywords=top_n)


def _fallback_posts(user_id: str, profile: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    title = f"{profile.get('profession') or 'Специалист'}: {profile.get('goal') or 'личный бренд'}"
    return [
        {
            "user_id": user_id,
            "source": "profile_context",
            "title": title,
            "content": context["query"] or title,
            "url": None,
            "score": 1,
            "comments": 0,
            "niche": context["niche"],
            "published_at": datetime.utcnow(),
        }
    ]


def _normalize_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return f"{parsed.netloc.lower()}{parsed.path}".rstrip("/")


def _normalize_post(raw: dict[str, Any], niche: str, source: str, query: str | None = None) -> dict[str, Any]:
    return {
        "source": raw.get("source") or source,
        "title": _compact(raw.get("title")),
        "content": _compact(raw.get("content") or raw.get("body")),
        "url": raw.get("url") or raw.get("href"),
        "score": raw.get("score") or 0,
        "comments": raw.get("comments") or 0,
        "published_at": raw.get("published_at"),
        "niche": niche,
        "query": query,
    }


def _dedupe_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for post in posts:
        title = _compact(post.get("title"))
        content = _compact(post.get("content") or post.get("body"))
        url = _normalize_url(post.get("url") or post.get("href"))
        key = url or f"{title[:90].lower()}::{content[:140].lower()}"
        if not title and not content:
            continue
        if key in seen:
            continue
        seen.add(key)
        unique.append(post)
    return unique


def _coerce_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


async def _insert_raw_posts(session: AsyncSession, user_id: str, posts: list[dict[str, Any]], niche: str) -> int:
    inserted = 0
    for post in posts:
        row = await fetch_all(
            session,
            """
            INSERT INTO raw_posts (user_id, source, title, content, url, score, comments, niche, published_at)
            VALUES (:user_id, :source, :title, :content, :url, :score, :comments, :niche, :published_at)
            RETURNING id
            """,
            {
                "user_id": user_id,
                "source": post.get("source", "legacy"),
                "title": post.get("title"),
                "content": post.get("content") or post.get("body"),
                "url": post.get("url") or post.get("href"),
                "score": post.get("score") or 0,
                "comments": post.get("comments") or 0,
                "niche": post.get("niche") or niche,
                "published_at": _coerce_datetime(post.get("published_at")),
            },
        )
        if row:
            post["_raw_post_id"] = row[0]["id"]
        inserted += 1
    return inserted


def _keyword_list(value: Any) -> list[str]:
    return clean_keywords(value)


def _post_source(post: dict[str, Any]) -> dict[str, Any]:
    return {"title": post.get("title"), "url": post.get("url"), "source": post.get("source")}


def _trend_response(trend: dict[str, Any], posts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    insights = trend.get("youtube_insights") or {}
    example_sources = [_post_source(post) for post in (posts or [])[:3]]
    return {
        "id": trend.get("id"),
        "topic": trend.get("topic"),
        "summary": trend.get("summary"),
        "keywords": _keyword_list(trend.get("keywords")),
        "source_count": trend.get("posts_count") or len(posts or []),
        "posts_count": trend.get("posts_count") or len(posts or []),
        "example_source": example_sources[0] if example_sources else None,
        "example_sources": example_sources,
        "collected_at": trend.get("collected_at").isoformat() if hasattr(trend.get("collected_at"), "isoformat") else trend.get("collected_at"),
        "expires_at": trend.get("expires_at").isoformat() if hasattr(trend.get("expires_at"), "isoformat") else trend.get("expires_at"),
        "score": trend.get("final_score"),
        "relevance_level": trend.get("relevance_level") or insights.get("relevance_level"),
        "relevance_score": trend.get("relevance_score") or insights.get("relevance_score"),
        "relevance_reason": trend.get("relevance_reason") or insights.get("relevance_reason"),
        "adaptation_suggestion": trend.get("adaptation_suggestion") or insights.get("adaptation_suggestion"),
    }


def _summarize_group(posts: list[dict[str, Any]], source: str) -> dict[str, Any] | None:
    if not posts:
        return None
    text = " ".join(_clean_text(f"{post.get('title') or ''} {post.get('content') or ''}") for post in posts)
    keywords = clean_keywords(_keywords(text), text)
    top_post = max(posts, key=lambda item: (item.get("score") or 0) + (item.get("comments") or 0) * 2)
    topic = (top_post.get("title") or "Profile trend")[:120]
    score = float(len(posts) * 2 + sum((post.get("score") or 0) for post in posts))
    return {
        "source": source,
        "topic": topic,
        "keywords": keywords,
        "posts_count": len(posts),
        "google_score": 0,
        "google_trend": "stable",
        "final_score": score,
        "youtube_insights": {},
        "summary": f"Тема '{topic[:60]}' основана на {len(posts)} материалах. Ключевые слова: {', '.join(keywords[:4])}",
    }


async def analyze_and_save_trends(
    session: AsyncSession,
    niche: str,
    limit: int = 120,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    posts = await fetch_all(
        session,
        """
        SELECT *
        FROM raw_posts
        WHERE niche = :niche
        ORDER BY collected_at DESC
        LIMIT :limit
        """,
        {"niche": niche, "limit": limit},
    )
    if not posts:
        return []

    groups: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        text = _clean_text(f"{post.get('title') or ''} {post.get('content') or ''}")
        key = (_keywords(text, top_n=1) or [post.get("source") or niche])[0]
        groups.setdefault(key, []).append(post)

    trends: list[dict[str, Any]] = []
    for key, grouped_posts in sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)[:8]:
        trend = _summarize_group(grouped_posts, source=niche or key)
        if not trend:
            continue
        row = await fetch_all(
            session,
            """
            INSERT INTO trends (user_id, source, topic, keywords, posts_count, google_score, google_trend, final_score, youtube_insights, summary)
            VALUES (:user_id, :source, :topic, CAST(:keywords AS JSONB), :posts_count, :google_score, :google_trend, :final_score, CAST(:youtube_insights AS JSONB), :summary)
            RETURNING *
            """,
            {**trend, "user_id": user_id},
        )
        if row:
            trends.append(row[0])
    return trends


def _collect_for_query(query: str, niche: str, max_results: int = 5) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    try:
        import requests

        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query, "kl": "us-en", "df": "w"},
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
            timeout=10,
        )
        response.raise_for_status()
        blocks = re.findall(r'<div class="result(?: results_links_deep)?".*?</div>\s*</div>', response.text, flags=re.S)
        for block in blocks[:max_results]:
            title_match = re.search(r'class="result__a"[^>]*>(.*?)</a>', block, flags=re.S)
            snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>|class="result__snippet"[^>]*>(.*?)</div>', block, flags=re.S)
            url_match = re.search(r'class="result__url"[^>]*>(.*?)</a>|class="result__url"[^>]*>(.*?)</span>', block, flags=re.S)
            title = re.sub(r"<[^>]+>", " ", title_match.group(1)) if title_match else ""
            snippet_raw = next((group for group in (snippet_match.groups() if snippet_match else []) if group), "")
            url_raw = next((group for group in (url_match.groups() if url_match else []) if group), "")
            posts.append(
                _normalize_post(
                    {
                        "title": html.unescape(_compact(re.sub(r"<[^>]+>", " ", title))),
                        "content": html.unescape(_compact(re.sub(r"<[^>]+>", " ", snippet_raw))),
                        "url": html.unescape(_compact(re.sub(r"<[^>]+>", " ", url_raw))),
                    },
                    niche,
                    "ddg_html",
                    query,
                )
            )
        if posts:
            return posts
    except Exception:
        pass
    try:
        from parsers.ddg_parser import _search_ddg_html, _search_ddgs

        raw_results: list[dict[str, Any]] = []
        try:
            raw_results = _search_ddgs(query, max_results)
            source = "ddg"
        except Exception:
            raw_results = _search_ddg_html(query, max_results)
            source = "ddg_html"
        posts.extend(_normalize_post(item, niche, source, query) for item in raw_results)
    except Exception:
        pass
    return posts


def _collect_rss(niche: str, max_per_feed: int = 8) -> list[dict[str, Any]]:
    try:
        import feedparser
        from parsers.rss_parser import NICHE_RSS_FEEDS

        feeds = NICHE_RSS_FEEDS.get(niche, NICHE_RSS_FEEDS.get("общее") or NICHE_RSS_FEEDS.get("РѕР±С‰РµРµ") or [])
        posts: list[dict[str, Any]] = []
        for feed_url in feeds:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_per_feed]:
                published = datetime.utcnow()
                if getattr(entry, "published_parsed", None):
                    try:
                        published = datetime(*entry.published_parsed[:6])
                    except Exception:
                        pass
                posts.append(
                    _normalize_post(
                        {
                            "source": "rss",
                            "title": entry.get("title", ""),
                            "content": (entry.get("summary", "") or "")[:1000],
                            "url": entry.get("link", ""),
                            "published_at": published,
                        },
                        niche,
                        "rss",
                    )
                )
        return posts
    except Exception:
        return []


def _collect_posts_for_profile(profile: dict[str, Any], context: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    errors: list[str] = []
    queries = list(context.get("queries") or [])
    posts: list[dict[str, Any]] = []
    for query in queries:
        posts.extend(_collect_for_query(query, context["niche"], max_results=5))
    posts.extend(_collect_rss(context["niche"], max_per_feed=8))
    posts = _dedupe_posts(posts)

    if len(posts) < 8:
        broad_queries = [query for query in build_profile_queries(profile, broad=True) if query not in queries]
        queries.extend(broad_queries)
        for query in broad_queries[:6]:
            posts.extend(_collect_for_query(query, context["niche"], max_results=5))
        posts = _dedupe_posts(posts)

    if len(posts) < 3:
        errors.append("limited_sources")
    return posts, queries, errors


def _terms(value: Any) -> set[str]:
    text = _clean_text(str(value or ""))
    return {word for word in text.split() if len(word) > 2 and word not in STOP_WORDS}


def _profile_relevance_terms(profile: dict[str, Any]) -> dict[str, set[str]]:
    profession = _terms(profile.get("profession")) | _terms(profile.get("niche"))
    goal = _terms(profile.get("goal"))
    audience = _terms(profile.get("audience"))
    platforms: set[str] = set()
    for platform in profile.get("platforms") or []:
        platforms |= _terms(platform)

    profile_text = _clean_text(" ".join(str(profile.get(key) or "") for key in ("profession", "niche", "goal", "audience")))
    if any(term in profile_text for term in ("python", "питон", "разработчик", "developer", "backend", "it")):
        profession |= {
            "python", "developer", "developers", "software", "engineering", "backend",
            "programming", "ai", "automation", "разработчик", "программист",
        }
    if any(term in profile_text for term in ("client", "clients", "клиент", "клиентов", "lead", "sales", "find")):
        goal |= {
            "client", "clients", "leads", "lead", "sales", "freelance", "consulting",
            "linkedin", "portfolio", "personal", "brand", "клиент", "клиентов",
            "лиды", "продажи", "личный", "бренд",
        }
    return {
        "profession": profession,
        "goal": goal,
        "audience": audience,
        "platforms": platforms,
        "avoid": _terms(profile.get("avoid")),
    }


def _score_relevance(trend: dict[str, Any], posts: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    source_text = " ".join(f"{post.get('title') or ''} {post.get('content') or ''}" for post in posts)
    keywords = clean_keywords(trend.get("keywords"), source_text)
    text = _clean_text(
        " ".join(
            [
                str(trend.get("topic") or ""),
                str(trend.get("summary") or ""),
                " ".join(keywords),
                " ".join(str(post.get("title") or "") for post in posts),
                " ".join(str(post.get("query") or "") for post in posts),
            ]
        )
    )
    terms = set(text.split())
    profile_terms = _profile_relevance_terms(profile)
    profession_hits = terms & profile_terms["profession"]
    goal_hits = terms & profile_terms["goal"]
    audience_hits = terms & profile_terms["audience"]
    platform_hits = terms & profile_terms["platforms"]
    avoid_hits = terms & profile_terms["avoid"]

    score = min(
        100,
        len(profession_hits) * 18
        + len(goal_hits) * 20
        + len(audience_hits) * 8
        + len(platform_hits) * 10
        + min(len(posts), 5) * 3,
    )
    if avoid_hits:
        score = max(0, score - len(avoid_hits) * 25)

    if profession_hits and goal_hits and (platform_hits or audience_hits or score >= 65):
        level = "high"
        reason = "Высокая релевантность: тема связана с вашей профессией, целью и каналами продвижения."
        suggestion = None
    elif profession_hits or (goal_hits and (platform_hits or audience_hits)) or score >= 35:
        level = "medium"
        reason = "Средняя релевантность: тема полезна для экспертного контента, но её нужно связать с вашей целью."
        suggestion = "Можно использовать как экспертный пост и показать, как эта тема помогает клиентам понять вашу экспертизу."
    else:
        level = "low"
        reason = "Низкая релевантность: связь с профессией и целью слабая."
        suggestion = None

    return {
        "keywords": keywords,
        "relevance_level": level,
        "relevance_score": round(float(score), 1),
        "relevance_reason": reason,
        "adaptation_suggestion": suggestion,
    }


def _source_excerpt(posts: list[dict[str, Any]], limit: int = 4) -> str:
    lines: list[str] = []
    for post in posts[:limit]:
        title = _compact(post.get("title"))
        content = _compact(post.get("content") or post.get("body"))
        if not title and not content:
            continue
        lines.append(f"- {title}: {content[:220]}")
    return "\n".join(lines)


def _template_trend_summary(trend: dict[str, Any], posts: list[dict[str, Any]], profile: dict[str, Any]) -> str:
    topic = _compact(trend.get("topic") or "тема")
    profession = _compact(profile.get("profession") or profile.get("niche") or "специалиста")
    goal = _compact(profile.get("goal") or "развивать профиль")
    platforms = ", ".join(profile.get("platforms") or []) or "выбранных платформах"
    keywords = clean_keywords(trend.get("keywords"), " ".join(f"{p.get('title') or ''} {p.get('content') or ''}" for p in posts), max_keywords=4)
    keyword_text = ", ".join(keywords[:3]) if keywords else "найденным материалам"

    intro = f"По найденным заголовкам и материалам видно, что тема «{topic}» связана с {keyword_text}."
    value = f"Для {profession} это можно использовать как экспертный контент на {platforms}: показать, почему тема важна для аудитории и как она помогает двигаться к цели «{goal}»."
    if trend.get("relevance_level") == "low":
        value = f"Связь с профилем пока слабая, поэтому тему стоит использовать осторожно или адаптировать под цель «{goal}»."
    return f"{intro} {value}"


def _normalize_summary(text: str) -> str:
    summary = re.sub(r"\s+", " ", (text or "").strip())
    summary = re.sub(r"^(summary|резюме)\s*:\s*", "", summary, flags=re.I)
    sentences = re.split(r"(?<=[.!?])\s+", summary)
    summary = " ".join(sentence for sentence in sentences[:4] if sentence).strip()
    return summary[:700]


async def _generate_trend_summary(trend: dict[str, Any], posts: list[dict[str, Any]], profile: dict[str, Any]) -> tuple[str, str]:
    fallback = _template_trend_summary(trend, posts, profile)
    source_excerpt = _source_excerpt(posts)
    if not source_excerpt:
        return fallback, "template"

    prompt = (
        "Создай короткое резюме тренда для карточки GhostWriter AI.\n"
        "Пиши по-русски, 2-4 предложения, без списков и без технических логов.\n"
        "Не выдумывай факты: опирайся только на тему и найденные источники. "
        "Если данных мало, начни с фразы: «По найденным заголовкам и материалам видно, что...».\n\n"
        f"Тема: {trend.get('topic')}\n"
        f"Ключевые слова: {', '.join(clean_keywords(trend.get('keywords'), max_keywords=6))}\n"
        f"Релевантность: {trend.get('relevance_level')} — {trend.get('relevance_reason')}\n"
        f"Адаптация: {trend.get('adaptation_suggestion') or '-'}\n"
        f"Профиль: профессия={profile.get('profession')}, ниша={profile.get('niche')}, "
        f"цель={profile.get('goal')}, аудитория={profile.get('audience')}, "
        f"платформы={profile.get('platforms')}, тон={profile.get('tone')}\n"
        f"Источники:\n{source_excerpt}\n"
    )
    try:
        text, _provider = await asyncio.wait_for(
            generate_text_with_fallback(
                prompt,
                system_prompt="You summarize trend clusters for social media content planning. Return only the user-facing Russian summary.",
            ),
            timeout=25,
        )
        summary = _normalize_summary(text)
        return (summary or fallback), "llm"
    except LLMUnavailable:
        return fallback, "template"
    except Exception:
        return fallback, "template"


def _group_posts(posts: list[dict[str, Any]], niche: str, profile: dict[str, Any]) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    try:
        cluster_count = min(10, max(3, len(posts) // 3))
        clusters = trend_adapter.cluster_posts(posts, n_clusters=cluster_count)
        grouped = list(clusters.values())
    except Exception:
        groups: dict[str, list[dict[str, Any]]] = {}
        for post in posts:
            text = _clean_text(f"{post.get('title') or ''} {post.get('content') or ''}")
            keys = _keywords(text, top_n=2)
            key = keys[0] if keys else (post.get("source") or niche)
            groups.setdefault(key, []).append(post)
        grouped = list(groups.values())
    grouped = sorted(grouped, key=lambda value: (len(value), sum((post.get("score") or 0) for post in value)), reverse=True)
    result: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for group_posts in grouped[:10]:
        try:
            agent_summary = trend_adapter.summarize_cluster(group_posts)
            trend = {
                "source": niche,
                "topic": agent_summary.get("topic") or (group_posts[0].get("title") or "Trend")[:120],
                "keywords": clean_keywords(agent_summary.get("keywords"), " ".join(f"{p.get('title') or ''} {p.get('content') or ''}" for p in group_posts)),
                "posts_count": agent_summary.get("posts_count") or len(group_posts),
                "google_score": 0,
                "google_trend": "stable",
                "final_score": float((agent_summary.get("posts_count") or len(group_posts)) * 2),
                "youtube_insights": {},
                "summary": agent_summary.get("summary"),
            }
        except Exception:
            trend = _summarize_group(group_posts, source=niche)
        if trend:
            relevance = _score_relevance(trend, group_posts, profile)
            trend["keywords"] = relevance["keywords"]
            trend["final_score"] = float(trend.get("final_score") or 0) + relevance["relevance_score"]
            trend["relevance_level"] = relevance["relevance_level"]
            trend["relevance_score"] = relevance["relevance_score"]
            trend["relevance_reason"] = relevance["relevance_reason"]
            trend["adaptation_suggestion"] = relevance["adaptation_suggestion"]
            trend["youtube_insights"] = {
                **(trend.get("youtube_insights") or {}),
                "relevance_level": relevance["relevance_level"],
                "relevance_score": relevance["relevance_score"],
                "relevance_reason": relevance["relevance_reason"],
                "adaptation_suggestion": relevance["adaptation_suggestion"],
            }
            result.append((trend, group_posts))
    priority = {"high": 0, "medium": 1, "low": 2}
    result.sort(key=lambda item: (priority.get(item[0].get("relevance_level"), 3), -(item[0].get("relevance_score") or 0), -len(item[1])))
    visible = [item for item in result if item[0].get("relevance_level") in {"high", "medium"}]
    if len(visible) < 5:
        visible.extend([item for item in result if item[0].get("relevance_level") == "low"][: 5 - len(visible)])
    return visible[:10]


async def find_and_save_trends(session: AsyncSession, user_id: str, profile: dict[str, Any], run_legacy: bool = True) -> dict[str, Any]:
    context = profile_search_context(profile)
    trend_run = await start_trend_run(session, user_id, profile)
    run_id = str(trend_run.get("id"))
    queries: list[str] = list(context.get("queries") or [])
    inserted = 0
    trends: list[dict[str, Any]] = []
    errors: list[str] = []
    summary_sources: list[str] = []
    try:
        posts, queries, errors = _collect_posts_for_profile(profile, context)
        if posts:
            inserted = await _insert_raw_posts(session, user_id, posts, context["niche"])
            for trend, grouped_posts in _group_posts(posts, context["niche"], profile):
                summary, summary_source = await _generate_trend_summary(trend, grouped_posts, profile)
                summary_sources.append(summary_source)
                trend["summary"] = summary
                trend["user_id"] = user_id
                trend["trend_run_id"] = run_id
                trend["youtube_insights"] = {
                    **(trend.get("youtube_insights") or {}),
                    "summary_source": summary_source,
                }
                row = await fetch_all(
                    session,
                    """
                    INSERT INTO trends
                        (user_id, trend_run_id, source, topic, keywords, posts_count, google_score,
                         google_trend, final_score, youtube_insights, summary)
                    VALUES
                        (:user_id, :trend_run_id, :source, :topic, CAST(:keywords AS JSONB),
                         :posts_count, :google_score, :google_trend, :final_score,
                         CAST(:youtube_insights AS JSONB), :summary)
                    RETURNING *
                    """,
                    trend,
                )
                if row:
                    raw_post_ids = [int(post["_raw_post_id"]) for post in grouped_posts if post.get("_raw_post_id")]
                    await link_trend_sources(
                        session,
                        int(row[0]["id"]),
                        raw_post_ids,
                        trend.get("relevance_score"),
                    )
                    trends.append(_trend_response(row[0], grouped_posts))
        trend_run = await finish_trend_run(session, run_id, queries, inserted, len(trends))
        result = {
            "status": "limited_sources" if len(trends) < 3 else "completed",
            "trend_run": trend_run,
            "context": {**context, "queries": queries},
            "raw_posts_inserted": inserted,
            "trends": trends,
            "errors": errors,
        }
        await save_generation_run(
            session,
            user_id=user_id,
            run_type="trend_search",
            provider="llm" if "llm" in summary_sources else "template",
            agent_name="trend_service+social_analyzer.trend_adapter",
            input_payload={"profile": profile, "queries": queries},
            output_payload={
                "trend_run_id": run_id,
                "raw_posts_found": inserted,
                "trends_found": len(trends),
                "trend_ids": [trend.get("id") for trend in trends],
            },
            status=result["status"],
            error_message="; ".join(errors) if errors else None,
        )
        return result
    except Exception as exc:
        trend_run = await fail_trend_run(session, run_id, str(exc), queries, inserted, len(trends))
        await save_generation_run(
            session,
            user_id=user_id,
            run_type="trend_search",
            provider=None,
            agent_name="trend_service+social_analyzer.trend_adapter",
            input_payload={"profile": profile, "queries": queries},
            output_payload={"trend_run_id": run_id, "raw_posts_found": inserted, "trends_found": len(trends)},
            status="failed",
            error_message=str(exc),
        )
        return {
            "status": "failed",
            "trend_run": trend_run,
            "context": {**context, "queries": queries},
            "raw_posts_inserted": inserted,
            "trends": trends,
            "errors": [str(exc)],
        }


async def active_trends(session: AsyncSession, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    return await fetch_all(
        session,
        """
        SELECT *
        FROM trends
        WHERE user_id = :user_id AND expires_at > NOW()
        ORDER BY final_score DESC
        LIMIT :limit
        """,
        {"user_id": user_id, "limit": limit},
    )
