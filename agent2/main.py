"""
agent2/main.py — Агент 2 v2.0: Контент-планировщик и генератор постов

Новая схема генерации (три агента + сборщик):
  Блок A (0.3) — Агент 2: каркас + хук на основе тренда
  Блок B (0.3) — Агент 3: призма профессии и ценностей пользователя
  Блок C (0.4) — Агент 4: адаптация под аудиторию

Запуск:
  python agent2/main.py                  # все три агента + сборщик
  python agent2/main.py --no-llm         # только шаблоны
  python agent2/main.py --agents 2       # только Агент 2 (старый режим)
  python agent2/main.py --platform Telegram
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

class C:
    CYAN    = "\033[96m"
    YELLOW  = "\033[93m"
    GREEN   = "\033[92m"
    MAGENTA = "\033[95m"
    RED     = "\033[91m"
    RESET   = "\033[0m"

BASE   = Path(__file__).resolve().parent
DATA   = BASE.parent / "data"
OUTPUT = DATA / "generated_posts.json"

sys.path.insert(0, str(BASE.parent))

from agent2.planner.content_planner      import load_and_plan
from agent2.generator.template_generator import generate_from_template
from agent2.generator.llm_polisher       import polish_with_llm
from agent2.generator.post_assembler     import assemble_post, calc_assembly_score
from agent2.platforms.adapter            import adapt_for_platform, get_post_stats


def run(use_llm: bool = True, platform_filter: str = None,
        agents: str = "2,3,4") -> list:

    active_agents = [a.strip() for a in agents.split(",")]
    use_agent3 = "3" in active_agents
    use_agent4 = "4" in active_agents

    print(f"""
{C.MAGENTA}╔══════════════════════════════════════════════╗
║   ✍️   АГЕНТ 2: ГЕНЕРАТОР КОНТЕНТА  v2.0    ║
╚══════════════════════════════════════════════╝{C.RESET}""")
    print(f"  Активные агенты: {', '.join(active_agents)}")
    print(f"  Корень проекта:  {BASE.parent}")

    # ── Шаг 1: Загрузка данных ───────────────────────────────────────
    print(f"\n{C.CYAN}── Шаг 1/4: Загрузка данных и планирование{C.RESET}")
    try:
        data    = load_and_plan()
        plan    = data["plan"]
        profile = data["profile"]
    except (FileNotFoundError, ValueError) as e:
        print(f"{C.RED}❌ {e}{C.RESET}")
        sys.exit(1)

    if platform_filter:
        plan = [s for s in plan if s["platform"].lower() == platform_filter.lower()]

    print(f"  Постов в плане: {len(plan)}")
    print(f"  Платформы:      {', '.join(set(s['platform'] for s in plan))}")
    print(f"  Профиль:        {profile.get('name')} / {profile.get('profession')}")
    print(f"  Сектор:         {profile.get('sector', 'не задан')}")
    print(f"  Аудитория:      {profile.get('audience_type') or profile.get('audience', 'не задана')}")
    if plan:
        print(f"  Период:         {plan[0]['date']} — {plan[-1]['date']}")

    # ── Шаг 2: Контент-план ──────────────────────────────────────────
    print(f"\n{C.CYAN}── Шаг 2/4: Контент-план{C.RESET}")
    for s in plan:
        print(f"  {s['date']} {s['time']}  "
              f"{C.YELLOW}{s['platform']:12}{C.RESET}"
              f"[{s['format']:18}]  {s['post_idea'][:48]}...")

    # ── Шаг 3: Генерация ─────────────────────────────────────────────
    print(f"\n{C.CYAN}── Шаг 3/4: Генерация постов{C.RESET}")
    generated = []

    for slot in plan:
        print(f"\n  {C.YELLOW}→ {slot['platform']} / {slot['format']}{C.RESET}")

        # ── Блок A: Агент 2 — каркас ──────────────────────────────
        block_a = generate_from_template(slot, profile)
        if use_llm:
            block_a = polish_with_llm(block_a, slot, profile)
        print(f"    Блок A (Агент 2): {len(block_a)} симв")

        # ── Блок B: Агент 3 — призма пользователя ─────────────────
        block_b = ""
        if use_agent3:
            try:
                from agent3.generator.persona_generator import generate_persona_block
                block_b = generate_persona_block(slot, profile)
                print(f"    Блок B (Агент 3): {len(block_b)} симв")
            except Exception as e:
                print(f"    ⚠️  Агент 3 недоступен: {str(e)[:60]}")

        # ── Блок C: Агент 4 — призма аудитории ────────────────────
        block_c = ""
        if use_agent4:
            try:
                from agent4.generator.audience_generator import generate_audience_block
                block_c = generate_audience_block(slot, profile)
                print(f"    Блок C (Агент 4): {len(block_c)} симв")
            except Exception as e:
                print(f"    ⚠️  Агент 4 недоступен: {str(e)[:60]}")

        # ── Сборка ────────────────────────────────────────────────
        assembly_score = 0.0

        if block_b or block_c:
            # Три агента — используем сборщик
            b = block_b or ""
            c = block_c or ""
            final, assembly_score = assemble_post(block_a, b, c, slot)
            print(f"    assembly_score: {assembly_score}")
        else:
            # Только Агент 2 — старый режим
            final = block_a

        adapted = adapt_for_platform(final, slot["platform"])
        stats   = get_post_stats(adapted, slot["platform"])
        icon    = "✅" if stats["fits"] else "⚠️ "
        print(f"    {icon} {stats['chars']}/{stats['limit']} симв "
              f"({stats['used_pct']}%)  хэштегов: {stats['hashtags']}")

        generated.append({
            "slot_id":        slot["slot_id"],
            "date":           slot["date"],
            "time":           slot["time"],
            "platform":       slot["platform"],
            "format":         slot["format"],
            "trend_topic":    slot["trend"].get("topic", ""),
            "keywords":       slot["trend"].get("keywords", []),
            "post_idea":      slot["post_idea"],
            # Блоки для отладки
            "block_base":     block_a,
            "block_persona":  block_b,
            "block_audience": block_c,
            # Финальный текст
            "final_text":     adapted,
            "stats":          stats,
            "assembly_score": assembly_score,
            "status":         "ready",
            "generated_at":   datetime.now().isoformat(),
        })

    # ── Шаг 4: Сохранение ────────────────────────────────────────────
    print(f"\n{C.CYAN}── Шаг 4/4: Сохранение{C.RESET}")
    DATA.mkdir(exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(generated, f, ensure_ascii=False, indent=2)

    avg_score = (
        sum(p["assembly_score"] for p in generated) / len(generated)
        if generated else 0
    )

    print(f"\n{C.GREEN}{'='*52}")
    print(f"  🎉 Готово! Сгенерировано постов: {len(generated)}")
    print(f"  Средний assembly_score:          {avg_score:.2f}")
    print(f"  Файл: {OUTPUT}")
    print(f"{'='*52}{C.RESET}")

    if generated:
        p = generated[0]
        print(f"\n{C.CYAN}── Превью: {p['platform']} / {p['date']} {p['time']}{C.RESET}")
        print("─" * 52)
        print(p["final_text"][:700] + ("..." if len(p["final_text"]) > 700 else ""))
        print("─" * 52)

    return generated


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Агент 2 v2.0 — генератор контента")
    ap.add_argument("--no-llm",   action="store_true",
                    help="Только шаблоны, без LLM")
    ap.add_argument("--platform", type=str, default=None,
                    help="Генерировать только для одной платформы")
    ap.add_argument("--agents",   type=str, default="2,3,4",
                    help="Список агентов: 2 / 2,3 / 2,3,4 (по умолчанию: 2,3,4)")
    args = ap.parse_args()
    run(use_llm=not args.no_llm,
        platform_filter=args.platform,
        agents=args.agents)
