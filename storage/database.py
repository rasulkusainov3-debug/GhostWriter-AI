"""
storage/database.py
Управление SQLite базой данных — тренды, профили, посты
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "data" / "analyzer.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # доступ по именам колонок
    return conn


def init_db():
    """Создаёт все таблицы при первом запуске"""
    conn = get_connection()
    cursor = conn.cursor()

    # ── Тренды (живут 14 дней, потом удаляются) ──────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trends (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT NOT NULL,          -- 'reddit', 'rss', 'ddg'
            topic       TEXT NOT NULL,
            keywords    TEXT NOT NULL,          -- JSON-список ключевых слов
            posts_count INTEGER DEFAULT 0,
            summary     TEXT,                   -- краткое саммари темы
            collected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at   DATETIME NOT NULL
        )
    """)

    # ── Сырые посты (для анализа) ─────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_posts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT NOT NULL,
            title       TEXT,
            content     TEXT,
            url         TEXT,
            score       INTEGER DEFAULT 0,      -- лайки/просмотры
            comments    INTEGER DEFAULT 0,
            published_at DATETIME,
            collected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            niche       TEXT                    -- тематика для фильтрации
        )
    """)

    # ── Профиль пользователя (постоянный) ────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id      TEXT PRIMARY KEY,
            name         TEXT,
            niche        TEXT,
            profession   TEXT,
            goal         TEXT,
            tone         TEXT,
            audience     TEXT,
            user_values  TEXT,
            avoid        TEXT,
            platforms    TEXT,
            raw_answers  TEXT,
            -- v2.0: новые поля умного онбординга
            sector       TEXT,
            prof_values  TEXT,
            audience_type TEXT,
            audience_level TEXT,
            style_profile TEXT,
            example_posts TEXT,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── История сгенерированных постов ───────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generated_posts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            platform    TEXT,                   -- linkedin, telegram, instagram
            content     TEXT NOT NULL,
            status      TEXT DEFAULT 'draft',   -- draft / approved / published
            trend_id    INTEGER,                -- на каком тренде основан
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user_profiles(user_id),
            FOREIGN KEY (trend_id) REFERENCES trends(id)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")


# ── Операции с трендами ───────────────────────────────────────────────

def save_trend(source: str, topic: str, keywords: list,
               posts_count: int, summary: str, ttl_days: int = 14):
    conn = get_connection()
    expires = datetime.now() + timedelta(days=ttl_days)
    conn.execute("""
        INSERT INTO trends (source, topic, keywords, posts_count, summary, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (source, topic, json.dumps(keywords, ensure_ascii=False),
          posts_count, summary, expires.isoformat()))
    conn.commit()
    conn.close()


def get_active_trends(niche: str = None, limit: int = 20) -> list:
    """Возвращает тренды которые ещё не устарели"""
    conn = get_connection()
    now = datetime.now().isoformat()
    if niche:
        rows = conn.execute("""
            SELECT * FROM trends
            WHERE expires_at > ? AND (topic LIKE ? OR keywords LIKE ?)
            ORDER BY posts_count DESC LIMIT ?
        """, (now, f"%{niche}%", f"%{niche}%", limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM trends
            WHERE expires_at > ?
            ORDER BY posts_count DESC LIMIT ?
        """, (now, limit)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def cleanup_expired_trends():
    """Удаляет устаревшие тренды"""
    conn = get_connection()
    deleted = conn.execute(
        "DELETE FROM trends WHERE expires_at < ?",
        (datetime.now().isoformat(),)
    ).rowcount
    conn.commit()
    conn.close()
    if deleted:
        print(f"🗑️  Удалено устаревших трендов: {deleted}")


# ── Операции с постами ────────────────────────────────────────────────

def save_raw_post(source: str, title: str, content: str,
                  url: str, score: int, comments: int,
                  published_at: str, niche: str = None):
    conn = get_connection()
    conn.execute("""
        INSERT INTO raw_posts (source, title, content, url, score, comments, published_at, niche)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (source, title, content, url, score, comments, published_at, niche))
    conn.commit()
    conn.close()


def get_recent_posts(days: int = 7, niche: str = None, limit: int = 200) -> list:
    conn = get_connection()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    if niche:
        rows = conn.execute("""
            SELECT * FROM raw_posts
            WHERE collected_at > ? AND (niche = ? OR niche IS NULL)
            ORDER BY score DESC LIMIT ?
        """, (since, niche, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM raw_posts
            WHERE collected_at > ?
            ORDER BY score DESC LIMIT ?
        """, (since, limit)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ── Операции с профилями ──────────────────────────────────────────────

def save_user_profile(profile: dict):
    conn = get_connection()
    conn.execute("""
        INSERT INTO user_profiles
            (user_id, name, niche, profession, goal, tone, audience, user_values, avoid, platforms, raw_answers,
             sector, prof_values, audience_type, audience_level, style_profile, example_posts, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name=excluded.name, niche=excluded.niche,
            profession=excluded.profession, goal=excluded.goal,
            tone=excluded.tone, audience=excluded.audience,
            user_values=excluded.user_values, avoid=excluded.avoid,
            platforms=excluded.platforms, raw_answers=excluded.raw_answers,
            sector=excluded.sector, prof_values=excluded.prof_values,
            audience_type=excluded.audience_type, audience_level=excluded.audience_level,
            style_profile=excluded.style_profile, example_posts=excluded.example_posts,
            updated_at=excluded.updated_at
    """, (
        profile.get("user_id", "default"),
        profile.get("name"),
        profile.get("niche"),
        profile.get("profession"),
        profile.get("goal"),
        profile.get("tone"),
        profile.get("audience"),
        json.dumps(profile.get("values", []), ensure_ascii=False),
        profile.get("avoid"),
        json.dumps(profile.get("platforms", []), ensure_ascii=False),
        json.dumps(profile.get("raw_answers", {}), ensure_ascii=False),
        profile.get("sector"),
        json.dumps(profile.get("prof_values", []), ensure_ascii=False),
        profile.get("audience_type"),
        profile.get("audience_level"),
        json.dumps(profile.get("style_profile", {}), ensure_ascii=False),
        json.dumps(profile.get("example_posts", []), ensure_ascii=False),
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()


def get_user_profile(user_id: str = "default") -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    profile = dict(row)
    profile["values"] = json.loads(profile["user_values"] or "[]")
    profile["platforms"] = json.loads(profile["platforms"] or "[]")
    profile["raw_answers"] = json.loads(profile["raw_answers"] or "{}")
    return profile
