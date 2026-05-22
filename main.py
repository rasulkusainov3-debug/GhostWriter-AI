"""
main.py
Точка входа — запускает весь pipeline анализатора
"""

import sys
import argparse
from colorama import Fore, Style, init

init(autoreset=True)

# Инициализация БД при старте
from storage.database import init_db, cleanup_expired_trends

# Модули
from onboarding.dialog import run_onboarding
from parsers.rss_parser import parse_rss
from parsers.ddg_parser import parse_ddg
from analyzer.trend_analyzer import analyze_trends
from storage.exporter import export_for_agent2


def print_header():
    print(f"""
{Fore.MAGENTA}╔══════════════════════════════════════════════╗
║   🤖  SOCIAL MEDIA ANALYZER  v1.0           ║
║   Агент 1: Анализатор трендов и образа       ║
╚══════════════════════════════════════════════╝{Style.RESET_ALL}""")


def run_full_pipeline(user_id: str = "default", skip_onboarding: bool = False):
    """Запускает полный цикл: профиль → парсинг → анализ → экспорт"""

    print_header()

    # Инициализация
    init_db()
    cleanup_expired_trends()

    # ── ШАГ 1: Профиль пользователя ──────────────────────────────────
    if not skip_onboarding:
        print(f"\n{Fore.CYAN}── ШАГ 1/4: Профиль пользователя{Style.RESET_ALL}")
        profile = run_onboarding(user_id)
    else:
        from storage.database import get_user_profile
        profile = get_user_profile(user_id)
        if not profile:
            print(f"{Fore.RED}Профиль не найден. Запусти без --skip-onboarding{Style.RESET_ALL}")
            sys.exit(1)

    niche = profile.get("niche", "карьера")

    # ── ШАГ 2: Парсинг ───────────────────────────────────────────────
    print(f"\n{Fore.CYAN}── ШАГ 2/4: Сбор данных (ниша: {niche}){Style.RESET_ALL}")

    print(f"\n  {Fore.YELLOW}📡 RSS-ленты...{Style.RESET_ALL}")
    rss_posts = parse_rss(niche=niche, max_per_feed=30)

    print(f"\n  {Fore.YELLOW}🔍 DuckDuckGo поиск...{Style.RESET_ALL}")
    ddg_posts = parse_ddg(niche=niche, max_results=20)

    # YouTube метаданные (нужен yt-dlp, без API-ключей)
    youtube_insights = {}
    try:
        from parsers.youtube_parser import parse_youtube
        print(f"\n  {Fore.YELLOW}🎬 YouTube...{Style.RESET_ALL}")
        yt_result = parse_youtube(niche=niche, max_per_query=15, days=7)
        youtube_insights = yt_result.get("insights", {})
    except ImportError:
        print(f"  ⚠️  YouTube пропущен: pip install yt-dlp")
    except Exception as e:
        print(f"  ⚠️  YouTube пропущен: {e}")

    # Reddit опционально (нужны ключи)
    try:
        from parsers.reddit_parser import parse_reddit
        print(f"\n  {Fore.YELLOW}🔴 Reddit...{Style.RESET_ALL}")
        reddit_posts = parse_reddit(niche=niche, max_posts=50)
    except Exception as e:
        print(f"  ⚠️  Reddit пропущен: {e}")
        reddit_posts = []

    total = len(rss_posts) + len(ddg_posts) + len(reddit_posts)
    print(f"\n  ✅ Всего собрано: {total} текстовых материалов")

    # ── ШАГ 3: Анализ трендов ────────────────────────────────────────
    print(f"\n{Fore.CYAN}── ШАГ 3/4: Анализ трендов{Style.RESET_ALL}")
    trends = analyze_trends(niche=niche, days=7)

    if trends:
        print(f"\n  {Fore.YELLOW}🏆 Топ-3 тренда недели:{Style.RESET_ALL}")
        for i, t in enumerate(trends[:3], 1):
            print(f"  {i}. {t['topic'][:60]}")
            print(f"     Ключевые слова: {', '.join(t['keywords'][:4])}")
            print(f"     Постов: {t['posts_count']}, лучший день: {t.get('best_day', '?')}")


    from parsers.google_trends_parser import parse_google_trends, boost_trends_by_google

    google_data = parse_google_trends(niche=niche, geo="RU", country="russia")

    if trends and google_data.get("interest"):
        trends = boost_trends_by_google(trends, niche, geo="RU")

    # ── ШАГ 4: Экспорт для Агента 2 ──────────────────────────────────
    print(f"\n{Fore.CYAN}── ШАГ 4/4: Экспорт данных для Агента 2{Style.RESET_ALL}")
    result = export_for_agent2(user_id)

    print(f"\n{Fore.GREEN}{'='*50}")
    print(f"  🎉 ГОТОВО! Агент 1 завершил работу.")
    print(f"  Передай Агенту 2 следующие файлы:")
    print(f"  📄 {result['trends_path']}")
    print(f"  📄 {result['profile_path']}")
    print(f"{'='*50}{Style.RESET_ALL}\n")

    return result


# ── CLI ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Social Media Analyzer — Агент 1")
    parser.add_argument("--user-id",         default="default",
                        help="ID пользователя")
    parser.add_argument("--skip-onboarding", action="store_true",
                        help="Пропустить онбординг (использовать существующий профиль)")
    parser.add_argument("--only-analyze",    action="store_true",
                        help="Только анализ (без парсинга)")
    parser.add_argument("--only-export",     action="store_true",
                        help="Только экспорт данных")

    args = parser.parse_args()
    init_db()

    if args.only_analyze:
        cleanup_expired_trends()
        analyze_trends()
    elif args.only_export:
        export_for_agent2(args.user_id)
    else:
        run_full_pipeline(
            user_id=args.user_id,
            skip_onboarding=args.skip_onboarding,
        )
