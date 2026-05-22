"""
agent2/main.py  —  Агент 2: Контент-планировщик и генератор постов

Читает от Агента 1:
  data/trends_export.json          — тренды недели
  data/user_profile_export.json    — профиль пользователя

Что делает:
  1. Строит контент-план на неделю
  2. Генерирует черновики через шаблоны (без LLM)
  3. Полирует через Groq/Gemini (опционально)
  4. Адаптирует под платформу
  5. Сохраняет в data/generated_posts.json

Запуск:
  python agent2/main.py
  python agent2/main.py --no-llm
  python agent2/main.py --platform LinkedIn
"""
import sys, json, argparse
from pathlib import Path
from datetime import datetime

# Цвета (без colorama — работает везде)
class C:
    CYAN    = "\033[96m"
    YELLOW  = "\033[93m"
    GREEN   = "\033[92m"
    MAGENTA = "\033[95m"
    RED     = "\033[91m"
    RESET   = "\033[0m"

# Путь к данным — папка data/ рядом с agent2/
BASE   = Path(__file__).parent
DATA   = BASE.parent / "data"
OUTPUT = DATA / "generated_posts.json"

sys.path.insert(0, str(BASE.parent))

from agent2.planner.content_planner      import load_and_plan
from agent2.generator.template_generator import generate_from_template
from agent2.generator.llm_polisher       import polish_with_llm
from agent2.platforms.adapter            import adapt_for_platform, get_post_stats


def run(use_llm=True, platform_filter=None):
    print(f"""
{C.MAGENTA}╔══════════════════════════════════════════════╗
║   ✍️   АГЕНТ 2: ГЕНЕРАТОР КОНТЕНТА  v1.0    ║
╚══════════════════════════════════════════════╝{C.RESET}""")

    # ── Шаг 1: Загрузка и план ───────────────────────────────────────
    print(f"\n{C.CYAN}── Шаг 1/4: Загрузка данных и планирование{C.RESET}")
    try:
        data    = load_and_plan()
        plan    = data["plan"]
        profile = data["profile"]
    except (FileNotFoundError, ValueError) as e:
        print(f"{C.RED}❌ {e}{C.RESET}"); sys.exit(1)

    if platform_filter:
        plan = [s for s in plan if s["platform"].lower() == platform_filter.lower()]

    print(f"  Постов в плане:  {len(plan)}")
    print(f"  Платформы:       {', '.join(set(s['platform'] for s in plan))}")
    if plan:
        print(f"  Период:          {plan[0]['date']} — {plan[-1]['date']}")

    # ── Шаг 2: Контент-план ──────────────────────────────────────────
    print(f"\n{C.CYAN}── Шаг 2/4: Контент-план{C.RESET}")
    for s in plan:
        print(f"  {s['date']} {s['time']}  "
              f"{C.YELLOW}{s['platform']:12}{C.RESET}"
              f"[{s['format']:18}]  {s['post_idea'][:50]}...")

    # ── Шаг 3: Генерация ─────────────────────────────────────────────
    print(f"\n{C.CYAN}── Шаг 3/4: Генерация постов{C.RESET}")
    generated = []

    for slot in plan:
        print(f"\n  {C.YELLOW}→ {slot['platform']} / {slot['format']}{C.RESET}")

        draft = generate_from_template(slot, profile)
        print(f"    Шаблон: {len(draft)} символов")

        final = draft
        if use_llm:
            final = polish_with_llm(draft, slot, profile)
            if final != draft:
                print(f"    После LLM: {len(final)} символов")

        adapted = adapt_for_platform(final, slot["platform"])
        stats   = get_post_stats(adapted, slot["platform"])
        icon    = "✅" if stats["fits"] else "⚠️ "
        print(f"    {icon} {stats['chars']}/{stats['limit']} симв "
              f"({stats['used_pct']}%)  хэштегов: {stats['hashtags']}")

        generated.append({
            "slot_id":      slot["slot_id"],
            "date":         slot["date"],
            "time":         slot["time"],
            "platform":     slot["platform"],
            "format":       slot["format"],
            "trend_topic":  slot["trend"].get("topic",""),
            "keywords":     slot["trend"].get("keywords",[]),
            "post_idea":    slot["post_idea"],
            "draft":        draft,
            "final_text":   adapted,
            "stats":        stats,
            "status":       "ready",
            "generated_at": datetime.now().isoformat(),
        })

    # ── Шаг 4: Сохранение ────────────────────────────────────────────
    print(f"\n{C.CYAN}── Шаг 4/4: Сохранение{C.RESET}")
    DATA.mkdir(exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(generated, f, ensure_ascii=False, indent=2)

    print(f"\n{C.GREEN}{'='*50}")
    print(f"  🎉 Готово! Сгенерировано постов: {len(generated)}")
    print(f"  Файл: {OUTPUT}")
    print(f"{'='*50}{C.RESET}")

    # Превью первого поста
    if generated:
        p = generated[0]
        print(f"\n{C.CYAN}── Превью: {p['platform']} / {p['date']} {p['time']}{C.RESET}")
        print("─" * 50)
        print(p["final_text"][:600] + ("..." if len(p["final_text"]) > 600 else ""))
        print("─" * 50)

    return generated


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Агент 2 — генератор контента")
    ap.add_argument("--no-llm",   action="store_true", help="Только шаблоны")
    ap.add_argument("--platform", type=str, default=None, help="Конкретная платформа")
    args = ap.parse_args()
    run(use_llm=not args.no_llm, platform_filter=args.platform)
