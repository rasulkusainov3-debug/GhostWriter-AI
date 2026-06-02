"""
agent3/main.py — Агент 3: Призма пользователя

Принимает слот контент-плана и профиль пользователя.
Возвращает текстовый блок 0.3 поста через призму
профессиональных ценностей автора.
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))

from agent3.generator.persona_generator import generate_persona_block


def run_agent3(slot: dict, profile: dict) -> str:
    """
    Точка входа Агента 3.
    Возвращает текстовый блок — призма пользователя (0.3 поста).
    """
    block = generate_persona_block(slot, profile)
    print(f"    Агент 3: {len(block)} символов")
    return block


if __name__ == "__main__":
    # Тест с тестовыми данными
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

    print(f"\n🔍 Тест Агента 3")
    print(f"  Профессия: {profile.get('profession')}")
    print(f"  Сектор:    {profile.get('sector', 'не задан')}")
    print(f"  Тренд:     {trends[0].get('topic', '')[:50]}")
    print()

    block = run_agent3(test_slot, profile)
    print("\n── Результат ──────────────────────────────")
    print(block)
    print("────────────────────────────────────────────")
