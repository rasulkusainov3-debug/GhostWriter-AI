"""
analyzer/trend_analyzer.py
Анализирует собранные посты: извлекает ключевые слова,
кластеризует темы, составляет саммари — без LLM
"""

import re
import json
from collections import Counter
from datetime import datetime

from storage.database import get_recent_posts, save_trend


# ── Очистка текста ────────────────────────────────────────────────────

STOP_WORDS = {
    "и", "в", "на", "с", "по", "для", "что", "как", "это", "не",
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "can", "could", "should", "may", "might", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "up", "about", "into",
    "через", "или", "но", "если", "то", "также", "уже", "свой",
    "этот", "который", "они", "мы", "вы", "я", "он", "она",
}


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)          # убрать HTML
    text = re.sub(r"http\S+", " ", text)           # убрать ссылки
    text = re.sub(r"[^\w\s\-]", " ", text)         # оставить буквы
    text = re.sub(r"\s+", " ", text)               # нормализовать пробелы
    return text.strip().lower()


# ── Извлечение ключевых слов через YAKE ──────────────────────────────

def extract_keywords_yake(text: str, top_n: int = 10) -> list[str]:
    """YAKE — статистический экстрактор, не требует обучения"""
    try:
        import yake
        kw_extractor = yake.KeywordExtractor(
            lan="en",
            n=2,           # биграммы
            dedupLim=0.7,
            top=top_n,
            features=None,
        )
        keywords = kw_extractor.extract_keywords(text)
        return [kw for kw, score in keywords]
    except ImportError:
        # Запасной вариант — просто частые слова
        return extract_keywords_simple(text, top_n)


def extract_keywords_simple(text: str, top_n: int = 10) -> list[str]:
    """Простой счётчик слов без зависимостей"""
    words = [w for w in text.split()
             if len(w) > 3 and w not in STOP_WORDS]
    return [word for word, _ in Counter(words).most_common(top_n)]


# ── TF-IDF кластеризация тем ──────────────────────────────────────────

def cluster_posts_by_topic(posts: list[dict],
                           n_clusters: int = 5) -> dict[int, list]:
    """
    Группирует посты по темам через TF-IDF + KMeans.
    Возвращает {cluster_id: [посты]}
    """
    if len(posts) < n_clusters:
        return {0: posts}

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans

        texts = [clean_text(f"{p['title']} {p['content']}") for p in posts]

        vectorizer = TfidfVectorizer(
            max_features=500,
            stop_words=list(STOP_WORDS),
            min_df=2,
        )
        X = vectorizer.fit_transform(texts)

        n = min(n_clusters, len(posts))
        kmeans = KMeans(n_clusters=n, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)

        clusters = {}
        for i, label in enumerate(labels):
            clusters.setdefault(label, []).append(posts[i])

        return clusters

    except ImportError:
        print("  ⚠️  scikit-learn не установлен, пропускаем кластеризацию")
        return {0: posts}


# ── Саммари кластера ──────────────────────────────────────────────────

def summarize_cluster(posts: list[dict]) -> dict:
    """
    Анализирует один кластер постов и возвращает саммари темы.
    """
    if not posts:
        return {}

    # Собираем весь текст кластера
    all_text = " ".join(
        clean_text(f"{p['title']} {p['content']}") for p in posts
    )

    # Ключевые слова
    keywords = extract_keywords_yake(all_text, top_n=8)

    # Самый популярный пост как "тема"
    top_post = max(posts, key=lambda p: (p.get("score") or 0) + (p.get("comments") or 0) * 2)
    topic_title = top_post["title"][:80]

    # Паттерны дней публикации
    days = []
    for p in posts:
        try:
            dt = datetime.fromisoformat(p.get("published_at") or "")
            days.append(dt.strftime("%A"))
        except Exception:
            pass
    best_day = Counter(days).most_common(1)[0][0] if days else "N/A"

    return {
        "topic":       topic_title,
        "keywords":    keywords,
        "posts_count": len(posts),
        "avg_score":   int(sum(p.get("score", 0) for p in posts) / len(posts)),
        "best_day":    best_day,
        "top_post_url": top_post.get("url", ""),
        "summary":     f"Тема '{topic_title[:40]}...' — {len(posts)} постов, "
                       f"ключевые слова: {', '.join(keywords[:4])}",
    }


# ── Главная функция анализа ───────────────────────────────────────────

def analyze_trends(niche: str = None, days: int = 7) -> list[dict]:
    """
    Берёт посты из БД за последние N дней,
    кластеризует и сохраняет тренды.
    Возвращает список найденных трендов.
    """
    print(f"\n📊 Анализируем посты за {days} дней (ниша: {niche or 'все'})...")

    posts = get_recent_posts(days=days, niche=niche, limit=300)
    if not posts:
        print("  ⚠️  Нет постов для анализа. Сначала запусти парсеры.")
        return []

    print(f"  Найдено {len(posts)} постов")

    # Кластеризация
    n = min(15, max(3, len(posts) // 20))
    clusters = cluster_posts_by_topic(posts, n_clusters=n)
    print(f"  Выделено {len(clusters)} тематических кластеров")

    trends = []
    for cluster_id, cluster_posts in clusters.items():
        result = summarize_cluster(cluster_posts)
        if not result:
            continue

        # Сохраняем в БД
        save_trend(
            source=niche or "mixed",
            topic=result["topic"],
            keywords=result["keywords"],
            posts_count=result["posts_count"],
            summary=result["summary"],
        )

        trends.append(result)
        print(f"  📌 Тренд [{cluster_id}]: {result['topic'][:50]}...")

    print(f"\n✅ Анализ завершён. Найдено {len(trends)} трендов.")
    return trends
