"""
parsers/reddit_parser.py
Парсит посты с Reddit по заданным сабреддитам и ключевым словам.

Установка: pip install praw
Бесплатные ключи: https://www.reddit.com/prefs/apps (тип: script)

Частые проблемы и решения:
  - 401 Unauthorized  → неверные client_id / client_secret в .env
  - 403 Forbidden     → приложение не того типа (нужен "script")
  - prawcore.exceptions.ResponseException → истёк токен, praw обновит сам
  - OAuthException    → проверь user_agent, он должен быть уникальным
"""

import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from storage.database import save_raw_post

load_dotenv()

NICHE_SUBREDDITS = {
    "IT":        ["programming", "cscareerquestions", "ExperiencedDevs", "webdev"],
    "маркетинг": ["marketing", "digital_marketing", "SEO", "socialmedia"],
    "финансы":   ["personalfinance", "financialindependence", "investing"],
    "карьера":   ["careerguidance", "jobs", "resumes", "ITCareerQuestions"],
    "общее":     ["productivity", "selfimprovement", "Entrepreneur"],
}


def _check_credentials() -> tuple[bool, str]:
    """Проверяет наличие и базовую корректность ключей."""
    cid = os.getenv("REDDIT_CLIENT_ID", "")
    sec = os.getenv("REDDIT_CLIENT_SECRET", "")
    if not cid or cid == "your_client_id":
        return False, "REDDIT_CLIENT_ID не задан в .env"
    if not sec or sec == "your_client_secret":
        return False, "REDDIT_CLIENT_SECRET не задан в .env"
    if len(cid) < 10:
        return False, f"REDDIT_CLIENT_ID слишком короткий: '{cid}' — скорее всего скопирован неверно"
    return True, "ok"


def get_reddit_client():
    ok, msg = _check_credentials()
    if not ok:
        raise ValueError(msg)

    import praw
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT", "social_analyzer/1.0 by YourUsername"),
        # read-only режим — логин не нужен
    )


def parse_reddit(niche: str = "карьера", days: int = 7,
                 max_posts: int = 100) -> list[dict]:
    """
    Парсит топ-посты за последние N дней из сабреддитов по нише.
    Возвращает список постов и сохраняет их в БД.
    """
    subreddits = NICHE_SUBREDDITS.get(niche, NICHE_SUBREDDITS["общее"])
    all_posts = []

    # ── Проверка ключей ──────────────────────────────────────────────
    ok, msg = _check_credentials()
    if not ok:
        print(f"  ⚠️  Reddit: {msg}")
        print("  📋 Как получить ключи (2 минуты, бесплатно):")
        print("     1. Войди на https://www.reddit.com/prefs/apps")
        print("     2. Нажми 'create another app'")
        print("     3. Тип: script, redirect: http://localhost:8080")
        print("     4. Скопируй client_id (под названием) и client_secret")
        print("     5. Вставь в .env файл")
        return _mock_posts(niche)

    # ── Подключение ───────────────────────────────────────────────────
    try:
        import praw
        import prawcore
    except ImportError:
        print("  ⚠️  Reddit: установи praw — pip install praw")
        return []

    try:
        reddit = get_reddit_client()
        # Быстрая проверка подключения
        _ = reddit.user.me()  # вернёт None в read-only, но не упадёт при верных ключах
    except Exception as e:
        err = str(e)
        if "401" in err:
            print("  ❌ Reddit: неверные client_id или client_secret (401 Unauthorized)")
        elif "403" in err:
            print("  ❌ Reddit: приложение должно быть типа 'script' (403 Forbidden)")
        else:
            print(f"  ❌ Reddit: ошибка подключения — {err[:100]}")
        print("  ℹ️  Используем моковые данные")
        return _mock_posts(niche)

    # ── Парсинг постов ────────────────────────────────────────────────
    cutoff = datetime.now() - timedelta(days=days)
    per_sub = max(10, max_posts // len(subreddits))

    for sub_name in subreddits:
        try:
            sub = reddit.subreddit(sub_name)
            count = 0

            for post in sub.top(time_filter="week", limit=per_sub):
                created = datetime.fromtimestamp(post.created_utc)
                if created < cutoff:
                    continue

                data = {
                    "source":       "reddit",
                    "title":        post.title,
                    "content":      (post.selftext or "")[:1000],
                    "url":          f"https://reddit.com{post.permalink}",
                    "score":        post.score,
                    "comments":     post.num_comments,
                    "published_at": created.isoformat(),
                    "niche":        niche,
                }
                all_posts.append(data)
                save_raw_post(**data)
                count += 1

            print(f"  ✅ r/{sub_name}: {count} постов")

            # Пауза между сабреддитами — защита от rate limit Reddit
            time.sleep(1.0)

        except Exception as e:
            err = str(e).lower()
            if "redirect" in err or "private" in err:
                print(f"  ⚠️  r/{sub_name}: сабреддит приватный или не существует")
            elif "ratelimit" in err:
                print(f"  ⏳ r/{sub_name}: rate limit, ждём 10с...")
                time.sleep(10)
            else:
                print(f"  ⚠️  r/{sub_name}: {type(e).__name__} — {str(e)[:80]}")
            continue

    return all_posts


def _mock_posts(niche: str) -> list[dict]:
    """Тестовые данные когда нет API-ключей — чтобы пайплайн не останавливался."""
    mock = [
        {
            "source":       "reddit_mock",
            "title":        f"[{niche}] Как я поднял зарплату на 40% за 6 месяцев через LinkedIn",
            "content":      "Начал вести LinkedIn: публиковал кейсы каждую неделю, выступал на митапах...",
            "url":          "https://reddit.com/mock/1",
            "score":        1200, "comments": 234,
            "published_at": datetime.now().isoformat(),
            "niche":        niche,
        },
        {
            "source":       "reddit_mock",
            "title":        f"[{niche}] Топ-5 навыков которые работодатели ищут в 2025",
            "content":      "На основе 300 вакансий: AI-инструменты, коммуникация, data literacy...",
            "url":          "https://reddit.com/mock/2",
            "score":        890, "comments": 156,
            "published_at": datetime.now().isoformat(),
            "niche":        niche,
        },
    ]
    for p in mock:
        save_raw_post(**p)
    print(f"  ℹ️  Reddit: загружены {len(mock)} тестовых поста (заглушка)")
    return mock
