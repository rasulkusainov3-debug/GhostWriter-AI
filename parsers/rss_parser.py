"""
parsers/rss_parser.py
Парсит RSS-ленты популярных платформ — Medium, Habr, vc.ru, Dev.to
"""

import feedparser
import requests
from datetime import datetime
from storage.database import save_raw_post

# RSS-ленты по нишам
NICHE_RSS_FEEDS = {
    "IT": [
        "https://dev.to/feed",
        "https://habr.com/ru/rss/flows/develop/all/",
        "https://medium.com/feed/tag/software-engineering",
    ],
    "карьера": [
        "https://habr.com/ru/rss/flows/career/all/",
        "https://medium.com/feed/tag/career",
        "https://medium.com/feed/tag/personal-development",
    ],
    "маркетинг": [
        "https://vc.ru/rss",
        "https://medium.com/feed/tag/marketing",
        "https://medium.com/feed/tag/social-media",
    ],
    "финансы": [
        "https://medium.com/feed/tag/personal-finance",
        "https://medium.com/feed/tag/investing",
    ],
    "общее": [
        "https://medium.com/feed/tag/productivity",
        "https://medium.com/feed/tag/self-improvement",
    ],
}


def parse_rss(niche: str = "карьера", max_per_feed: int = 30) -> list[dict]:
    """
    Забирает свежие статьи из RSS-лент по нише.
    Возвращает список постов и сохраняет в БД.
    """
    feeds = NICHE_RSS_FEEDS.get(niche, NICHE_RSS_FEEDS["общее"])
    all_posts = []

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            count = 0

            for entry in feed.entries[:max_per_feed]:
                # Дата публикации
                published = ""
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6]).isoformat()
                else:
                    published = datetime.now().isoformat()

                # Контент
                content = ""
                if hasattr(entry, "summary"):
                    content = entry.summary[:1000]
                elif hasattr(entry, "content"):
                    content = entry.content[0].value[:1000]

                data = {
                    "source":       "rss",
                    "title":        entry.get("title", ""),
                    "content":      content,
                    "url":          entry.get("link", ""),
                    "score":        0,
                    "comments":     0,
                    "published_at": published,
                    "niche":        niche,
                }
                all_posts.append(data)
                save_raw_post(**data)
                count += 1

            domain = feed_url.split("/")[2]
            print(f"  ✅ RSS {domain}: получено {count} статей")

        except Exception as e:
            print(f"  ⚠️  RSS {feed_url}: ошибка — {e}")

    return all_posts
