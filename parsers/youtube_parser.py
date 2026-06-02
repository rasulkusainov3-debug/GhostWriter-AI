"""
parsers/youtube_parser.py

Парсит метаданные YouTube-видео через yt-dlp — без скачивания видео,
без API-ключей, полностью бесплатно.

Что собирает:
  - заголовок, описание, теги
  - просмотры, лайки, комментарии → engagement rate
  - длительность, дата публикации, канал
  - тип контента (short / standard / long-form)

Установка: pip install yt-dlp
"""

import re
from datetime import datetime, timedelta
from collections import Counter
from storage.database import save_raw_post

# ── Поисковые запросы по нишам ────────────────────────────────────────

NICHE_YT_QUERIES = {
    "IT": [
        "developer personal brand salary 2026",
        "software engineer linkedin tips",
        "python developer career growth",
        "tech salary negotiation",
    ],
    "маркетинг": [
        "digital marketing personal brand 2026",
        "smm trends content strategy",
        "marketing career growth tips",
    ],
    "финансы": [
        "personal finance career salary 2026",
        "finance professional linkedin",
        "financial analyst career growth",
    ],
    "карьера": [
        "personal brand career growth 2026",
        "linkedin profile optimization salary",
        "how to get promoted faster",
        "salary negotiation tips 2025",
    ],
    "общее": [
        "personal branding tips 2026",
        "productivity career growth",
        "professional self promotion",
    ],
}

# ── Классификация формата видео ───────────────────────────────────────

def classify_format(duration_sec: int) -> str:
    """Определяет формат видео по длительности"""
    if duration_sec <= 60:
        return "short"           # YouTube Shorts
    elif duration_sec <= 300:
        return "micro"           # до 5 минут
    elif duration_sec <= 1200:
        return "standard"        # 5-20 минут — самый популярный
    else:
        return "long-form"       # 20+ минут


def calc_engagement(views: int, likes: int, comments: int) -> float:
    """
    Считает engagement rate.
    Комментарий весит больше лайка — человек потратил время написать.
    """
    if not views:
        return 0.0
    weighted = likes + comments * 3
    return round(weighted / views * 100, 2)


# ── Парсинг через yt-dlp ──────────────────────────────────────────────

def fetch_youtube_metadata(query: str, max_results: int = 15,
                           days: int = 7) -> list[dict]:
    """
    Ищет видео по запросу и возвращает метаданные.
    Видео НЕ скачивается — только JSON с данными.
    """
    try:
        import yt_dlp
    except ImportError:
        print("  ⚠️  yt-dlp не установлен: pip install yt-dlp")
        return []

    search_url = f"ytsearch{max_results}:{query}"

    ydl_opts = {
        "quiet":        True,
        "no_warnings":  True,
        "extract_flat": False,   # False чтобы получить полные метаданные
        "skip_download": True,   # видео не скачиваем
        "ignoreerrors": True,    # не падаем на недоступных видео
        # Фильтр по дате — только свежие видео
        "daterange": yt_dlp.utils.DateRange(
            start=(datetime.now() - timedelta(days=days)).strftime("%Y%m%d"),
            end=datetime.now().strftime("%Y%m%d"),
        ),
    }

    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            entries = info.get("entries") or []

            for entry in entries:
                if not entry:
                    continue

                duration   = entry.get("duration") or 0
                views      = entry.get("view_count") or 0
                likes      = entry.get("like_count") or 0
                comments   = entry.get("comment_count") or 0
                upload_raw = entry.get("upload_date") or ""

                # Парсим дату
                try:
                    published = datetime.strptime(upload_raw, "%Y%m%d").isoformat()
                except Exception:
                    published = datetime.now().isoformat()

                results.append({
                    "id":           entry.get("id", ""),
                    "title":        entry.get("title", ""),
                    "description":  (entry.get("description") or "")[:500],
                    "tags":         entry.get("tags") or [],
                    "channel":      entry.get("channel") or entry.get("uploader", ""),
                    "url":          entry.get("webpage_url", ""),
                    "views":        views,
                    "likes":        likes,
                    "comments":     comments,
                    "duration_sec": duration,
                    "format":       classify_format(duration),
                    "engagement":   calc_engagement(views, likes, comments),
                    "published_at": published,
                })

    except Exception as e:
        print(f"  ⚠️  yt-dlp ошибка для '{query}': {e}")

    return results


# ── Сохранение в БД ───────────────────────────────────────────────────

def save_video_to_db(video: dict, niche: str):
    """Сохраняет видео как raw_post с расширенным контентом"""
    # Собираем всё в контент для анализатора
    content = " ".join([
        video.get("description", ""),
        " ".join(video.get("tags", [])),
        f"format:{video.get('format', '')}",
        f"engagement:{video.get('engagement', 0)}",
    ])[:1000]

    save_raw_post(
        source="youtube",
        title=video["title"],
        content=content,
        url=video["url"],
        score=video["views"] // 100,   # нормализуем к масштабу Reddit
        comments=video["comments"],
        published_at=video["published_at"],
        niche=niche,
    )


# ── Аналитика видео-трендов ───────────────────────────────────────────

def analyze_video_trends(videos: list[dict]) -> dict:
    """
    Анализирует набор видео и возвращает инсайты:
    - лучший формат (short / standard / long-form)
    - топ теги
    - средний engagement
    - лучшее время публикации
    """
    if not videos:
        return {}

    # Лучший формат по engagement
    format_engagement: dict[str, list] = {}
    for v in videos:
        fmt = v.get("format", "standard")
        format_engagement.setdefault(fmt, []).append(v.get("engagement", 0))

    best_format = max(
        format_engagement,
        key=lambda f: sum(format_engagement[f]) / len(format_engagement[f])
    )
    avg_engagement_by_format = {
        fmt: round(sum(vals) / len(vals), 2)
        for fmt, vals in format_engagement.items()
    }

    # Топ теги
    all_tags = []
    for v in videos:
        all_tags.extend(v.get("tags", []))
    top_tags = [tag for tag, _ in Counter(all_tags).most_common(10)]

    # Средний engagement
    engagements = [v.get("engagement", 0) for v in videos if v.get("engagement")]
    avg_engagement = round(sum(engagements) / len(engagements), 2) if engagements else 0

    # Топ видео
    top_video = max(videos, key=lambda v: v.get("views", 0))

    # Паттерны по дням недели
    days = []
    for v in videos:
        try:
            dt = datetime.fromisoformat(v.get("published_at", ""))
            days.append(dt.strftime("%A"))
        except Exception:
            pass
    best_day = Counter(days).most_common(1)[0][0] if days else "N/A"

    return {
        "total_videos":            len(videos),
        "best_format":             best_format,
        "avg_engagement_by_format": avg_engagement_by_format,
        "avg_engagement":          avg_engagement,
        "top_tags":                top_tags,
        "best_posting_day":        best_day,
        "top_video": {
            "title":      top_video.get("title", ""),
            "views":      top_video.get("views", 0),
            "engagement": top_video.get("engagement", 0),
            "format":     top_video.get("format", ""),
            "url":        top_video.get("url", ""),
        },
    }


# ── Главная функция ───────────────────────────────────────────────────

def parse_youtube(niche: str = "карьера", max_per_query: int = 15,
                  days: int = 7) -> dict:
    """
    Полный цикл: поиск → парсинг метаданных → сохранение → аналитика.

    Возвращает:
      {
        "videos":   [...],   # список видео с метаданными
        "insights": {...},   # аналитика трендов
      }
    """
    queries = NICHE_YT_QUERIES.get(niche, NICHE_YT_QUERIES["общее"])
    all_videos = []

    print(f"\n  🎬 YouTube парсер (ниша: {niche})")

    for query in queries:
        print(f"    🔍 Поиск: '{query}'")
        videos = fetch_youtube_metadata(query, max_results=max_per_query, days=days)

        for v in videos:
            save_video_to_db(v, niche)

        all_videos.extend(videos)
        print(f"       ✅ Найдено {len(videos)} видео")

    # Убираем дубликаты по id
    seen = set()
    unique = []
    for v in all_videos:
        if v["id"] not in seen:
            seen.add(v["id"])
            unique.append(v)

    insights = analyze_video_trends(unique)

    print(f"\n  📊 YouTube инсайты:")
    print(f"     Всего видео:     {insights.get('total_videos', 0)}")
    print(f"     Лучший формат:   {insights.get('best_format', '?')} "
          f"(engagement: {insights.get('avg_engagement_by_format', {}).get(insights.get('best_format', ''), '?')}%)")
    print(f"     Средний ER:      {insights.get('avg_engagement', 0)}%")
    print(f"     Топ теги:        {', '.join(insights.get('top_tags', [])[:5])}")
    if insights.get("top_video"):
        tv = insights["top_video"]
        print(f"     Топ видео:       {tv['title'][:50]} ({tv['views']:,} views)")

    return {"videos": unique, "insights": insights}


# ── Запуск напрямую для теста ─────────────────────────────────────────

if __name__ == "__main__":
    from storage.database import init_db
    init_db()
    result = parse_youtube(niche="карьера", max_per_query=10, days=14)
    print(f"\nИтого видео: {len(result['videos'])}")
