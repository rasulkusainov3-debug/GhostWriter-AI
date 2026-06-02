"""
parsers/google_trends_parser.py

Собирает данные из Google Trends через pytrends:
  - interest_over_time  — динамика интереса к ключевым словам за неделю
  - related_queries     — смежные запросы (что ещё ищут рядом с темой)
  - trending_searches   — что в тренде прямо сейчас в стране
  - realtime_trending   — горячие темы последних 24ч

Установка: pip install pytrends

Интеграция в trend_analyzer.py: данные Google Trends добавляются
как отдельный источник с весовым коэффициентом — чем выше интерес
по Trends, тем выше приоритет темы в итоговом списке трендов.
"""

import time
import random
from datetime import datetime
from storage.database import save_raw_post, save_trend

# Ниши → ключевые слова для Google Trends
NICHE_KEYWORDS = {
    "IT": [
        ["personal brand developer", "software engineer career"],
        ["salary negotiation tech",  "developer linkedin"],
        ["programming trends 2026",  "tech career growth"],
    ],
    "маркетинг": [
        ["digital marketing trends", "content marketing 2025"],
        ["SMM trends",               "social media marketing"],
        ["personal brand marketing", "influencer marketing"],
    ],
    "карьера": [
        ["personal brand career",    "linkedin tips"],
        ["salary negotiation",       "career growth"],
        ["how to get promoted",      "professional development"],
    ],
    "финансы": [
        ["personal finance 2026",    "investing career"],
        ["salary increase",          "financial freedom"],
    ],
    "общее": [
        ["personal branding",        "professional growth"],
        ["productivity tips",        "self improvement career"],
    ],
}

# Страны для поиска трендов (коды Google)
COUNTRY_CODES = {
    "ru": "russia",
    "kz": "kazakhstan",
    "us": "united_states",
    "global": "",            # пустая строка = весь мир
}


def _get_client(lang: str = "ru-RU", country_code: str = "ru"):
    """Создаёт клиент pytrends с правильными настройками."""
    from pytrends.request import TrendReq
    return TrendReq(
        hl=lang,
        tz=180,              # UTC+3 (Москва), для KZ используй 360 (UTC+6)
        timeout=(10, 30),    # connect timeout, read timeout
        retries=3,
        backoff_factor=1.0,  # пауза между ретраями: 1s, 2s, 4s
    )


def _safe_pause(min_sec: float = 1.5, max_sec: float = 4.0):
    """Пауза между запросами — Google блокирует при слишком частых обращениях."""
    time.sleep(random.uniform(min_sec, max_sec))


# ── 1. Динамика интереса к ключевым словам ────────────────────────────

def get_interest_over_time(keywords: list[str], timeframe: str = "now 7-d",
                           geo: str = "") -> dict:
    """
    Возвращает динамику интереса к ключевым словам за период.

    timeframe:
      "now 1-d"   — последние 24 часа
      "now 7-d"   — последняя неделя (рекомендуется)
      "today 1-m" — последний месяц
      "today 3-m" — последние 3 месяца

    geo: "" = весь мир, "RU" = Россия, "KZ" = Казахстан

    Возвращает:
    {
      "keyword1": {"avg": 72, "trend": "rising", "peak_day": "2025-04-20"},
      "keyword2": {"avg": 45, "trend": "stable",  "peak_day": "2025-04-18"},
    }
    """
    # Google Trends принимает максимум 5 ключевых слов за раз
    keywords = keywords[:5]

    try:
        pt = _get_client()
        pt.build_payload(keywords, timeframe=timeframe, geo=geo)
        df = pt.interest_over_time()

        if df.empty:
            print(f"  ⚠️  Google Trends: нет данных для {keywords}")
            return {}

        result = {}
        for kw in keywords:
            if kw not in df.columns:
                continue
            series = df[kw]
            avg    = int(series.mean())
            trend  = "rising" if series.iloc[-3:].mean() > series.iloc[:3].mean() else "stable"
            peak   = series.idxmax().strftime("%Y-%m-%d")
            result[kw] = {"avg": avg, "trend": trend, "peak_day": peak}

        print(f"  ✅ Trends interest_over_time: {len(result)} ключевых слов")
        return result

    except Exception as e:
        print(f"  ⚠️  interest_over_time: {type(e).__name__} — {str(e)[:80]}")
        return {}


# ── 2. Смежные запросы ────────────────────────────────────────────────

def get_related_queries(keyword: str, geo: str = "") -> list[str]:
    """
    Возвращает топ смежных запросов для ключевого слова.
    Это золото для понимания что реально ищут люди рядом с темой.

    Например для "salary negotiation":
      ["salary negotiation script", "how to ask for raise", "salary increase email"]
    """
    try:
        pt = _get_client()
        pt.build_payload([keyword], timeframe="now 7-d", geo=geo)
        _safe_pause()
        rq = pt.related_queries()

        top = rq.get(keyword, {}).get("top")
        if top is None or top.empty:
            return []

        queries = top["query"].head(10).tolist()
        print(f"  ✅ Trends related_queries '{keyword}': {len(queries)} запросов")
        return queries

    except Exception as e:
        print(f"  ⚠️  related_queries '{keyword}': {str(e)[:80]}")
        return []


# ── 3. Что в тренде прямо сейчас ─────────────────────────────────────

def get_trending_now(country: str = "russia") -> list[str]:
    """
    Топ поисковых запросов прямо сейчас в стране.
    country: "russia", "kazakhstan", "united_states"

    Возвращает список топ-20 запросов.
    """
    try:
        pt = _get_client()
        df = pt.trending_searches(pn=country)
        topics = df[0].head(20).tolist()
        print(f"  ✅ Trends trending_now ({country}): {len(topics)} тем")
        return topics

    except Exception as e:
        print(f"  ⚠️  trending_searches: {str(e)[:80]}")
        return []


# ── 4. Горячие темы последних 24 часов ───────────────────────────────

def get_realtime_trending(geo: str = "RU", category: str = "all") -> list[dict]:
    """
    Горячие темы реального времени (последние 24ч).
    geo: "RU", "KZ", "US"
    category: "all", "b" (бизнес), "t" (технологии), "e" (развлечения)

    Возвращает список словарей с title и traffic.
    """
    try:
        pt = _get_client()
        df = pt.realtime_trending_searches(pn=geo)

        topics = []
        for _, row in df.head(15).iterrows():
            topics.append({
                "title":   str(row.get("title", "")),
                "traffic": str(row.get("traffic", "")),
            })

        print(f"  ✅ Trends realtime ({geo}): {len(topics)} горячих тем")
        return topics

    except Exception as e:
        print(f"  ⚠️  realtime_trending: {str(e)[:80]}")
        return []


# ── 5. Весовая интеграция с трендами из БД ────────────────────────────

def boost_trends_by_google(trends: list[dict], niche: str,
                           geo: str = "") -> list[dict]:
    """
    Повышает приоритет трендов из БД на основе данных Google Trends.

    Логика:
      - Берём ключевые слова каждого тренда
      - Проверяем их интерес в Google Trends
      - Добавляем поле google_score (0–100)
      - Сортируем по (posts_count × 0.6 + google_score × 0.4)

    Возвращает обогащённый и пересортированный список трендов.
    """
    if not trends:
        return trends

    print(f"\n  🔍 Обогащение трендов данными Google Trends (ниша: {niche})")

    # Собираем все ключевые слова из трендов (берём первое из каждого)
    all_keywords = []
    for t in trends:
        kw = t.get("keywords", [])
        if kw and isinstance(kw, list) and kw[0] not in all_keywords:
            all_keywords.append(kw[0])

    all_keywords = all_keywords[:5]  # Google Trends ограничение

    if not all_keywords:
        return trends

    # Получаем интерес из Google Trends
    interest = get_interest_over_time(all_keywords, timeframe="now 7-d", geo=geo)
    _safe_pause()

    # Добавляем google_score к каждому тренду
    for t in trends:
        kw_list = t.get("keywords", [])
        score   = 0
        trend_direction = "stable"

        for kw in kw_list[:3]:
            if kw in interest:
                score           = max(score, interest[kw]["avg"])
                trend_direction = interest[kw]["trend"]

        t["google_score"]     = score
        t["google_trend"]     = trend_direction   # "rising" или "stable"

    # Нормализуем posts_count для честного сравнения
    max_posts = max((t.get("posts_count", 0) for t in trends), default=1) or 1

    # Финальный рейтинг: 60% популярность постов + 40% Google интерес
    for t in trends:
        posts_norm  = (t.get("posts_count", 0) / max_posts) * 100
        google_norm = t.get("google_score", 0)
        # Бонус +20 если тренд растёт
        rising_bonus = 20 if t.get("google_trend") == "rising" else 0
        t["final_score"] = posts_norm * 0.6 + google_norm * 0.4 + rising_bonus

    boosted = sorted(trends, key=lambda t: t.get("final_score", 0), reverse=True)

    print(f"  ✅ Тренды пересортированы с учётом Google Trends")
    if boosted:
        top = boosted[0]
        print(f"     Топ-тренд: '{top.get('topic','')[:50]}'")
        print(f"     Google score: {top.get('google_score', 0)} | "
              f"Направление: {top.get('google_trend','?')} | "
              f"Итоговый рейтинг: {top.get('final_score', 0):.1f}")

    return boosted


# ── 6. Главная функция ────────────────────────────────────────────────

def parse_google_trends(niche: str = "карьера", geo: str = "RU",
                        country: str = "russia") -> dict:
    """
    Полный цикл сбора данных из Google Trends.

    Возвращает:
    {
      "trending_now":     [...],   # что ищут прямо сейчас
      "realtime":         [...],   # горячие темы 24ч
      "interest":         {...},   # динамика по ключевым словам
      "related_queries":  {...},   # смежные запросы
    }
    """
    print(f"\n  📈 Google Trends (ниша: {niche}, гео: {geo})")

    result = {
        "trending_now":    [],
        "realtime":        [],
        "interest":        {},
        "related_queries": {},
        "niche":           niche,
        "collected_at":    datetime.now().isoformat(),
    }

    # 1. Что в тренде прямо сейчас
    print("    → Топ запросов сейчас...")
    result["trending_now"] = get_trending_now(country)
    _safe_pause()

    # 2. Горячие темы реального времени
    print("    → Горячие темы 24ч...")
    result["realtime"] = get_realtime_trending(geo=geo.upper())
    _safe_pause()

    # 3. Динамика по нишевым ключевым словам
    kw_groups = NICHE_KEYWORDS.get(niche, NICHE_KEYWORDS["общее"])
    for group in kw_groups:
        print(f"    → Интерес к: {group}...")
        interest = get_interest_over_time(group, timeframe="now 7-d", geo=geo)
        result["interest"].update(interest)
        _safe_pause(2, 5)   # Google Trends агрессивно рейтлимитит

    # 4. Смежные запросы для топ-ключевых слов
    if result["interest"]:
        # Берём топ-2 слова по среднему интересу
        top_kw = sorted(result["interest"].items(),
                        key=lambda x: x[1]["avg"], reverse=True)[:2]
        for kw, _ in top_kw:
            print(f"    → Смежные запросы: '{kw}'...")
            result["related_queries"][kw] = get_related_queries(kw, geo=geo)
            _safe_pause(2, 5)

    # 5. Сохраняем связанные запросы как сырые посты (для анализатора)
    for kw, queries in result["related_queries"].items():
        for q in queries[:5]:
            save_raw_post(
                source="google_trends",
                title=q,
                content=f"Google Trends related query for '{kw}'",
                url=f"https://trends.google.com/trends/explore?q={q.replace(' ','+')}",
                score=result["interest"].get(kw, {}).get("avg", 0),
                comments=0,
                published_at=datetime.now().isoformat(),
                niche=niche,
            )

    total_signals = (len(result["trending_now"]) +
                     len(result["realtime"]) +
                     len(result["interest"]) +
                     sum(len(v) for v in result["related_queries"].values()))

    print(f"\n  ✅ Google Trends: {total_signals} сигналов собрано")
    return result


# ── Запуск напрямую для теста ─────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from storage.database import init_db
    init_db()

    result = parse_google_trends(niche="карьера", geo="RU", country="russia")
    print("\nРезультат:")
    print(f"  trending_now:    {len(result['trending_now'])} запросов")
    print(f"  realtime:        {len(result['realtime'])} тем")
    print(f"  interest:        {len(result['interest'])} ключевых слов")
    print(f"  related_queries: {sum(len(v) for v in result['related_queries'].values())} запросов")
