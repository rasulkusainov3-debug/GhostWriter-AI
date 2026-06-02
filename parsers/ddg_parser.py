"""
parsers/ddg_parser.py

Поиск актуальных публикаций.

Решение проблемы "Exception occurred in previous call":
  - Старый пакет duckduckgo-search конфликтует с новым ddgs
  - Удали старый: pip uninstall duckduckgo-search
  - Установи новый: pip install ddgs

Три слоя запасных вариантов:
  1. ddgs (новый пакет) — основной
  2. requests + DDG HTML парсинг — если ddgs заблокирован
  3. RSS-ленты новостей по нише — всегда работает без ключей
"""

import time
import random
import re
from datetime import datetime, timedelta
from storage.database import save_raw_post

NICHE_QUERIES = {
    "IT":        ["software developer salary 2026", "tech career growth tips",
                  "programming trends 2026", "developer personal brand"],
    "карьера":   ["personal brand career growth 2026", "LinkedIn tips salary",
                  "salary negotiation tips 2026", "professional self promotion"],
    "маркетинг": ["digital marketing trends 2026", "content marketing strategy",
                  "SMM trends social media 2026"],
    "финансы":   ["personal finance tips 2026", "investing career growth"],
    "общее":     ["personal branding tips 2026", "productivity career",
                  "professional growth tips"],
}

# Запасные RSS-ленты новостей — работают без ключей и без DDG
FALLBACK_RSS = {
    "IT":        ["https://dev.to/feed/tag/career",
                  "https://dev.to/feed/tag/productivity"],
    "маркетинг": ["https://feeds.feedburner.com/MarketingLand",
                  "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"],
    "карьера":   ["https://feeds.feedburner.com/entrepreneur/latest",
                  "https://medium.com/feed/tag/career-advice"],
    "финансы":   ["https://feeds.feedburner.com/entrepreneur/latest"],
    "общее":     ["https://medium.com/feed/tag/self-improvement",
                  "https://medium.com/feed/tag/productivity"],
}


# ── Слой 1: ddgs ─────────────────────────────────────────────────────

def _search_ddgs(query: str, max_results: int) -> list[dict]:
    """Поиск через новый пакет ddgs с retry при rate limit."""
    try:
        from ddgs import DDGS
    except ImportError:
        raise RuntimeError("ddgs не установлен: pip install ddgs")

    for attempt in range(3):
        try:
            with DDGS() as d:
                results = list(d.text(
                    query,
                    max_results=max_results,
                    timelimit="w",
                ))
            return results
        except Exception as e:
            err = str(e).lower()
            # rate limit или предыдущая ошибка сессии
            if any(x in err for x in ["ratelimit", "403", "previous call", "202"]):
                wait = 3.0 * (attempt + 1) + random.uniform(1, 3)
                print(f"    ⏳ DDG rate limit (попытка {attempt+1}/3), ждём {wait:.0f}с...")
                time.sleep(wait)
            else:
                raise
    return []


# ── Слой 2: requests + DDG HTML (без библиотеки) ─────────────────────

def _search_ddg_html(query: str, max_results: int) -> list[dict]:
    """
    Прямой запрос к DDG HTML-версии через requests.
    Работает когда ddgs-библиотека заблокирована, но сам DDG доступен.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError("requests или beautifulsoup4 не установлены")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/122.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    params = {"q": query, "kl": "us-en", "df": "w"}
    resp = requests.get("https://html.duckduckgo.com/html/",
                        params=params, headers=headers, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for item in soup.select(".result")[:max_results]:
        title = item.select_one(".result__title")
        snippet = item.select_one(".result__snippet")
        link = item.select_one(".result__url")
        if title:
            results.append({
                "title": title.get_text(strip=True),
                "body":  snippet.get_text(strip=True) if snippet else "",
                "href":  link.get_text(strip=True) if link else "",
            })
    return results


# ── Слой 3: RSS новостей (всегда работает) ───────────────────────────

def _search_rss_fallback(niche: str, max_results: int) -> list[dict]:
    """
    Парсит RSS-ленты новостей как запасной источник.
    Не требует никаких ключей или внешних библиотек.
    """
    import feedparser

    feeds = FALLBACK_RSS.get(niche, FALLBACK_RSS["общее"])
    results = []

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[: max_results // len(feeds) + 1]:
                published = datetime.now().isoformat()
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6]).isoformat()
                    except Exception:
                        pass
                results.append({
                    "title": entry.get("title", ""),
                    "body":  entry.get("summary", "")[:500],
                    "href":  entry.get("link", ""),
                    "published_at": published,
                })
        except Exception:
            continue

    return results[:max_results]


# ── Основная функция ──────────────────────────────────────────────────

def parse_ddg(niche: str = "карьера", max_results: int = 20) -> list[dict]:
    """
    Поиск актуальных материалов с тремя уровнями запасных вариантов.

    Порядок попыток:
      1. ddgs (новый пакет)
      2. requests + DDG HTML
      3. RSS-ленты новостей по нише
    """
    all_posts = []
    queries = NICHE_QUERIES.get(niche, NICHE_QUERIES["общее"])
    per_query = max(1, max_results // len(queries))

    for i, query in enumerate(queries):
        # Пауза между запросами — защита от бана
        if i > 0:
            time.sleep(random.uniform(1.5, 3.0))

        raw_results = []
        used_method = ""

        # Попытка 1: ddgs
        try:
            raw_results = _search_ddgs(query, per_query)
            used_method = "ddgs"
        except Exception as e1:
            # Попытка 2: requests + HTML
            try:
                raw_results = _search_ddg_html(query, per_query)
                used_method = "ddg-html"
            except Exception as e2:
                # Попытка 3: RSS fallback (один раз на всю нишу, не на каждый запрос)
                if i == 0:
                    print(f"  ⚠️  DDG недоступен ({type(e1).__name__}), переключаемся на RSS-запасник")
                    raw_results = _search_rss_fallback(niche, max_results)
                    used_method = "rss-fallback"
                    # Сохраняем все результаты fallback сразу и выходим
                    for r in raw_results:
                        data = {
                            "source":       "rss_fallback",
                            "title":        r.get("title", ""),
                            "content":      r.get("body", "")[:1000],
                            "url":          r.get("href", ""),
                            "score":        0,
                            "comments":     0,
                            "published_at": r.get("published_at", datetime.now().isoformat()),
                            "niche":        niche,
                        }
                        all_posts.append(data)
                        save_raw_post(**data)
                    print(f"  ✅ RSS-запасник: {len(raw_results)} статей")
                    return all_posts

        # Сохраняем результаты
        for r in raw_results:
            data = {
                "source":       f"ddg_{used_method}",
                "title":        r.get("title", ""),
                "content":      r.get("body", "")[:1000],
                "url":          r.get("href", ""),
                "score":        0,
                "comments":     0,
                "published_at": r.get("published_at", datetime.now().isoformat()),
                "niche":        niche,
            }
            all_posts.append(data)
            save_raw_post(**data)

        if raw_results:
            print(f"  ✅ DDG [{used_method}] '{query[:35]}': {len(raw_results)} результатов")
        else:
            print(f"  ⚠️  DDG '{query[:35]}': 0 результатов")

    return all_posts
