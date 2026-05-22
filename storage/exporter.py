"""
storage/exporter.py
Экспортирует данные в JSON-файлы для Агента 2 (контент-планировщика)
"""

import json
from pathlib import Path
from datetime import datetime
from storage.database import get_active_trends, get_user_profile

OUTPUT_DIR = Path(__file__).parent.parent / "data"


def export_for_agent2(user_id: str = "default", youtube_insights: dict = None) -> dict:
    """
    Собирает все данные и сохраняет в два JSON-файла:
    - data/trends_export.json
    - data/user_profile_export.json

    Возвращает словарь с путями к файлам.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    # ── Профиль пользователя ──────────────────────────────────────────
    profile = get_user_profile(user_id)
    if not profile:
        print("⚠️  Профиль не найден. Запусти онбординг.")
        profile = {}

    profile_path = OUTPUT_DIR / "user_profile_export.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    # ── Актуальные тренды ─────────────────────────────────────────────
    niche = profile.get("niche")
    trends = get_active_trends(niche=niche, limit=20)

    trends_export = {
        "exported_at":      datetime.now().isoformat(),
        "niche":            niche,
        "count":            len(trends),
        "trends":           trends,
        "youtube_insights": youtube_insights or {},
    }

    trends_path = OUTPUT_DIR / "trends_export.json"
    with open(trends_path, "w", encoding="utf-8") as f:
        json.dump(trends_export, f, ensure_ascii=False, indent=2)

    print(f"\n📦 Данные экспортированы для Агента 2:")
    print(f"   👤 Профиль:  {profile_path}")
    print(f"   📈 Тренды:   {trends_path} ({len(trends)} трендов)")

    return {
        "profile_path": str(profile_path),
        "trends_path":  str(trends_path),
        "profile":      profile,
        "trends":       trends,
    }
