"""
onboarding/dialog.py — переработан для v2.0

Умный онбординг: 4 обязательных вопроса вместо 9.
После вопроса о профессии система автоматически выводит
сектор, ценности и аудиторию — пользователь подтверждает кнопкой.

Опционально: пользователь может скинуть примеры постов
для анализа стиля (заменяет вопросы про тон и формат).
"""

from colorama import Fore, Style, init
from storage.database import save_user_profile, get_user_profile
from onboarding.inferencer import infer_profile
from onboarding.style_analyzer import analyze_style

init(autoreset=True)

# ── 4 обязательных вопроса ────────────────────────────────────────────

REQUIRED_QUESTIONS = [
    {
        "key":     "name",
        "text":    "Как тебя зовут?",
        "example": "Алексей",
    },
    {
        "key":     "profession",
        "text":    "Кем ты работаешь / чем занимаешься?",
        "example": "ML-инженер, следователь прокуратуры, учитель математики...",
    },
    {
        "key":     "goal",
        "text":    "Какова главная цель твоего личного бренда?",
        "example": "повысить зарплату / найти клиентов / стать экспертом в нише",
    },
    {
        "key":     "platforms",
        "text":    "На каких платформах будешь публиковаться? (через запятую)",
        "example": "LinkedIn, Telegram, Instagram",
    },
]

# Ниша для поиска трендов — нужна отдельно
NICHE_QUESTION = {
    "key":     "niche",
    "text":    "Выбери нишу для поиска трендов:",
    "choices": ["IT", "маркетинг", "финансы", "карьера", "государство", "образование", "медицина", "общее"],
}


def ask(question: dict) -> str:
    """Задаёт один вопрос и возвращает ответ."""
    print(f"\n{Fore.CYAN}❓ {question['text']}{Style.RESET_ALL}")

    if "choices" in question:
        for i, choice in enumerate(question["choices"], 1):
            print(f"   {Fore.YELLOW}{i}.{Style.RESET_ALL} {choice}")
        while True:
            raw = input(f"{Fore.GREEN}➤ {Style.RESET_ALL}").strip()
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(question["choices"]):
                    return question["choices"][idx]
            elif raw.lower() in [c.lower() for c in question["choices"]]:
                return raw.lower()
            print(f"  {Fore.RED}Введи число от 1 до {len(question['choices'])}{Style.RESET_ALL}")
    else:
        if "example" in question:
            print(f"   {Fore.WHITE}Например: {question['example']}{Style.RESET_ALL}")
        return input(f"{Fore.GREEN}➤ {Style.RESET_ALL}").strip()


def confirm_inferred(inferred: dict) -> dict:
    """
    Показывает выведенные данные и предлагает подтвердить или изменить.
    Возвращает финальный словарь с подтверждёнными данными.
    """
    print(f"\n{Fore.YELLOW}⚡ Система определила автоматически:{Style.RESET_ALL}")
    print(f"   Сектор:    {inferred.get('sector', '?')}")
    print(f"   Ценности:  {', '.join(inferred.get('prof_values', []))}")
    print(f"   Аудитория: {inferred.get('audience_type', '?')}")
    print(f"   Тон:       {inferred.get('tone', '?')}")

    print(f"\n   {Fore.GREEN}1. ✓ Всё верно{Style.RESET_ALL}")
    print(f"   {Fore.YELLOW}2. Изменить тон{Style.RESET_ALL}")
    print(f"   {Fore.YELLOW}3. Изменить аудиторию{Style.RESET_ALL}")
    print(f"   {Fore.YELLOW}4. Изменить ценности{Style.RESET_ALL}")
    print(f"   {Fore.YELLOW}5. Изменить всё вручную{Style.RESET_ALL}")

    choice = input(f"{Fore.GREEN}➤ {Style.RESET_ALL}").strip()

    if choice == "2":
        tones = ["экспертный", "дружелюбный", "провокационный", "вдохновляющий", "нейтральный"]
        for i, t in enumerate(tones, 1):
            print(f"   {i}. {t}")
        raw = input(f"{Fore.GREEN}➤ {Style.RESET_ALL}").strip()
        if raw.isdigit() and 0 < int(raw) <= len(tones):
            inferred["tone"] = tones[int(raw) - 1]

    elif choice == "3":
        audiences = ["широкая публика", "молодые специалисты", "руководители", "профессионалы той же сферы"]
        for i, a in enumerate(audiences, 1):
            print(f"   {i}. {a}")
        raw = input(f"{Fore.GREEN}➤ {Style.RESET_ALL}").strip()
        if raw.isdigit() and 0 < int(raw) <= len(audiences):
            inferred["audience_type"] = audiences[int(raw) - 1]

    elif choice == "4":
        print(f"   {Fore.WHITE}Введи 3-5 ценностей через запятую:{Style.RESET_ALL}")
        raw = input(f"{Fore.GREEN}➤ {Style.RESET_ALL}").strip()
        inferred["prof_values"] = [v.strip() for v in raw.split(",") if v.strip()]

    elif choice == "5":
        print(f"\n   {Fore.WHITE}Сектор (например: IT, медицина, образование):{Style.RESET_ALL}")
        inferred["sector"] = input(f"{Fore.GREEN}➤ {Style.RESET_ALL}").strip()

        print(f"   {Fore.WHITE}Ценности (через запятую):{Style.RESET_ALL}")
        raw_v = input(f"{Fore.GREEN}➤ {Style.RESET_ALL}").strip()
        inferred["prof_values"] = [v.strip() for v in raw_v.split(",") if v.strip()]

        audiences = ["широкая публика", "молодые специалисты", "руководители", "профессионалы той же сферы"]
        for i, a in enumerate(audiences, 1):
            print(f"   {i}. {a}")
        raw_a = input(f"{Fore.GREEN}➤ {Style.RESET_ALL}").strip()
        if raw_a.isdigit() and 0 < int(raw_a) <= len(audiences):
            inferred["audience_type"] = audiences[int(raw_a) - 1]

        tones = ["экспертный", "дружелюбный", "провокационный", "вдохновляющий", "нейтральный"]
        for i, t in enumerate(tones, 1):
            print(f"   {i}. {t}")
        raw_t = input(f"{Fore.GREEN}➤ {Style.RESET_ALL}").strip()
        if raw_t.isdigit() and 0 < int(raw_t) <= len(tones):
            inferred["tone"] = tones[int(raw_t) - 1]

    return inferred


def collect_example_posts() -> list[str]:
    """
    Предлагает пользователю скинуть примеры постов для анализа стиля.
    Возвращает список текстов постов.
    """
    print(f"\n{Fore.CYAN}📝 Опционально: покажи примеры постов{Style.RESET_ALL}")
    print("   Это помогает системе скопировать твой стиль письма.")
    print("   Можешь скинуть 1-3 своих поста или посты которые тебе нравятся.")
    print(f"   {Fore.WHITE}Пропустить? Просто нажми Enter.{Style.RESET_ALL}")

    posts = []
    for i in range(1, 4):
        print(f"\n   {Fore.YELLOW}Пост {i}/3{Style.RESET_ALL} (Enter — пропустить, 'готово' — закончить):")
        print("   Вставь текст поста и нажми Enter два раза:")
        lines = []
        while True:
            line = input()
            if line.lower() in ("готово", "done", ""):
                break
            lines.append(line)
        text = "\n".join(lines).strip()
        if text:
            posts.append(text)
        if not text and i == 1:
            break   # пользователь пропускает весь шаг
        if line.lower() in ("готово", "done"):
            break

    return posts


def run_onboarding(user_id: str = "default") -> dict:
    """
    Умный онбординг v2.0:
    1. 4 обязательных вопроса
    2. Инференс сектора/ценностей/аудитории → подтверждение
    3. Опциональный анализ примеров постов
    4. Сохранение расширенного профиля
    """
    print(f"\n{'='*55}")
    print(f"{Fore.MAGENTA}  🎯  СОЗДАНИЕ ЛИЧНОГО ОБРАЗА  v2.0{Style.RESET_ALL}")
    print(f"{'='*55}")
    print("Ответь на 4 вопроса — займёт 2-3 минуты.")
    print("Остальное система определит сама.\n")

    # Проверяем существующий профиль
    existing = get_user_profile(user_id)
    if existing:
        print(f"{Fore.YELLOW}⚡ У тебя уже есть профиль ({existing['name']}).{Style.RESET_ALL}")
        update = input("Обновить его? (да/нет): ").strip().lower()
        if update not in ("да", "д", "yes", "y"):
            print("✅ Используем существующий профиль.")
            return existing

    profile = {"user_id": user_id}
    raw_answers = {}

    # ── Шаг 1: 4 обязательных вопроса ────────────────────────────────
    for q in REQUIRED_QUESTIONS:
        answer = ask(q)
        profile[q["key"]] = answer
        raw_answers[q["key"]] = answer

    # ── Шаг 2: Ниша для трендов ───────────────────────────────────────
    niche = ask(NICHE_QUESTION)
    profile["niche"] = niche
    raw_answers["niche"] = niche

    # ── Шаг 3: Инференс из профессии ──────────────────────────────────
    print(f"\n{Fore.CYAN}🔍 Анализирую профессию...{Style.RESET_ALL}")
    inferred, method = infer_profile(profile["profession"])
    method_label = {"dict": "словарь", "llm": "ИИ", "default": "дефолт"}[method]
    print(f"   Метод: {method_label} (уверенность: {int(inferred.get('confidence', 0.5)*100)}%)")

    # Предлагаем подтвердить если уверенность высокая
    if inferred.get("confidence", 0) >= 0.7:
        inferred = confirm_inferred(inferred)
    else:
        # Низкая уверенность — просим заполнить вручную через confirm
        print(f"{Fore.YELLOW}  Уверенность низкая, уточни данные:{Style.RESET_ALL}")
        inferred = confirm_inferred(inferred)

    # Добавляем инференс в профиль
    profile["sector"]       = inferred.get("sector", "общее")
    profile["prof_values"]  = inferred.get("prof_values", [])
    profile["audience_type"]= inferred.get("audience_type", "широкая публика")
    profile["tone"]         = inferred.get("tone", "экспертный")

    # ── Шаг 4: Опциональный анализ стиля ──────────────────────────────
    example_posts = collect_example_posts()
    style_profile = {}

    if example_posts:
        print(f"\n{Fore.CYAN}✨ Анализирую стиль постов...{Style.RESET_ALL}")
        style_profile = analyze_style(example_posts)
        # Перекрываем тон из анализа стиля
        if style_profile.get("tone"):
            profile["tone"] = style_profile["tone"]
        print(f"   Стиль: {style_profile.get('tone')}, "
              f"предложения: {style_profile.get('sentence_length')}, "
              f"личного опыта: {int(style_profile.get('personal_ratio', 0.5)*100)}%")

    profile["style_profile"] = style_profile
    profile["example_posts"] = example_posts

    # ── Совместимость со старым форматом ─────────────────────────────
    # Старые поля которые ожидает Агент 2
    profile["values"]   = profile["prof_values"]
    profile["audience"] = profile["audience_type"]
    profile["avoid"]    = profile.get("avoid", "")
    profile["platforms"] = [p.strip() for p in profile.get("platforms", "").split(",") if p.strip()]
    profile["raw_answers"] = raw_answers

    # ── Сохраняем ─────────────────────────────────────────────────────
    save_user_profile(profile)

    print(f"\n{'='*55}")
    print(f"{Fore.GREEN}✅ Профиль сохранён!{Style.RESET_ALL}")
    print(f"{'='*55}")
    print(f"  Имя:        {profile.get('name')}")
    print(f"  Профессия:  {profile.get('profession')}")
    print(f"  Сектор:     {profile.get('sector')}")
    print(f"  Ниша:       {profile.get('niche')}")
    print(f"  Цель:       {profile.get('goal')}")
    print(f"  Тон:        {profile.get('tone')}")
    print(f"  Аудитория:  {profile.get('audience_type')}")
    print(f"  Ценности:   {', '.join(profile.get('prof_values', []))}")
    print(f"  Платформы:  {', '.join(profile.get('platforms', []))}")

    return profile
