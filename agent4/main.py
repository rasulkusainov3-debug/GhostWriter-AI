"""
agent4/main.py — Агент 4: Призма аудитории

Принимает слот контент-плана и профиль пользователя.
Возвращает главный текстовый блок 0.4 поста на языке
конкретной аудитории — без жаргона, с пояснениями.
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))

from agent4.generator.audience_generator import generate_audience_block


def run_agent4(slot: dict, profile: dict) -> str:
    """
    Точка входа Агента 4.
    Возвращает главный текстовый блок — призма аудитории (0.4 поста).
    """
    block = generate_audience_block(slot, profile)
    print(f"    Агент 4: {len(block)} символов")
    return block


if __name__ == "__main__":
    import json
    from pathlib import Path

    DATA = BASE.parent / "data"
    profile_path = DATA / "user_profile_export.json"
    trends_path  = DATA / "trends_export.json"

    if not profile_path.exists():
        print("❌ Запусти Агент 1 сначала")
        sys.exit(1)

    with open(profile_path, encoding="utf-8") as f:
        profile = json.load(f)
    with open(trends_path, encoding="utf-8") as f:
        trends = json.load(f).get("trends", [])

    if not trends:
        print("❌ Нет трендов")
        sys.exit(1)

    test_slot = {
        "platform": profile.get("platforms", ["LinkedIn"])[0] if profile.get("platforms") else "LinkedIn",
        "format":   "кейс",
        "trend":    trends[0],
        "post_idea": trends[0].get("topic", ""),
    }

    print(f"\n🔍 Тест Агента 4")
    print(f"  Профессия:  {profile.get('profession')}")
    print(f"  Аудитория:  {profile.get('audience_type') or profile.get('audience', 'не задана')}")
    print(f"  Тренд:      {trends[0].get('topic', '')[:50]}")
    print()

    block = run_agent4(test_slot, profile)
    print("\n── Результат ──────────────────────────────")
    print(block)
    print("────────────────────────────────────────────")
