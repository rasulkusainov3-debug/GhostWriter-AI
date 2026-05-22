"""
onboarding/dialog.py
Диалог с пользователем для сбора образа (если нет соц.сетей)
"""

from colorama import Fore, Style, init
from storage.database import save_user_profile, get_user_profile

init(autoreset=True)


QUESTIONS = [
    {
        "key":     "name",
        "text":    "Как тебя зовут?",
        "example": "Алексей",
    },
    {
        "key":     "profession",
        "text":    "Кем ты работаешь / в какой сфере?",
        "example": "Python-разработчик, маркетолог, финансовый аналитик...",
    },
    {
        "key":     "niche",
        "text":    "Выбери нишу для поиска трендов:",
        "choices": ["IT", "маркетинг", "финансы", "карьера", "общее"],
    },
    {
        "key":     "goal",
        "text":    "Какова главная цель твоего личного бренда?",
        "example": "повысить зарплату / найти клиентов / стать экспертом в нише",
    },
    {
        "key":     "audience",
        "text":    "Кто твоя целевая аудитория?",
        "example": "HR-менеджеры IT-компаний, начинающие разработчики...",
    },
    {
        "key":     "tone",
        "text":    "Выбери тон общения:",
        "choices": ["экспертный", "дружелюбный", "провокационный", "вдохновляющий", "нейтральный"],
    },
    {
        "key":     "values",
        "text":    "Перечисли 3-5 ценностей которые важно транслировать (через запятую):",
        "example": "честность, рост, практичность, открытость",
    },
    {
        "key":     "avoid",
        "text":    "Что точно НЕ хочешь публиковать?",
        "example": "политика, личная жизнь, жалобы на работодателей",
    },
    {
        "key":     "platforms",
        "text":    "На каких платформах будешь публиковаться? (через запятую)",
        "example": "LinkedIn, Telegram, Instagram",
    },
]


def ask(question: dict) -> str:
    """Задаёт один вопрос и возвращает ответ"""
    print(f"\n{Fore.CYAN}❓ {question['text']}{Style.RESET_ALL}")

    if "choices" in question:
        for i, choice in enumerate(question["choices"], 1):
            print(f"   {Fore.YELLOW}{i}.{Style.RESET_ALL} {choice}")
        while True:
            raw = input(f"{Fore.GREEN}➤ {Style.RESET_ALL}").strip()
            # Можно ввести цифру или текст
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
        answer = input(f"{Fore.GREEN}➤ {Style.RESET_ALL}").strip()
        return answer


def run_onboarding(user_id: str = "default") -> dict:
    """
    Запускает пошаговый диалог и сохраняет профиль в БД.
    Если профиль уже есть — предлагает обновить.
    """
    print(f"\n{'='*55}")
    print(f"{Fore.MAGENTA}  🎯  СОЗДАНИЕ ЛИЧНОГО ОБРАЗА{Style.RESET_ALL}")
    print(f"{'='*55}")
    print("Ответь на несколько вопросов — это займёт 2-3 минуты.")
    print("На их основе ИИ-агент будет генерировать посты под твой образ.\n")

    # Проверяем существующий профиль
    existing = get_user_profile(user_id)
    if existing:
        print(f"{Fore.YELLOW}⚡ У тебя уже есть профиль ({existing['name']}).{Style.RESET_ALL}")
        update = input("Обновить его? (да/нет): ").strip().lower()
        if update not in ("да", "д", "yes", "y"):
            print("✅ Используем существующий профиль.")
            return existing

    raw_answers = {}
    profile = {"user_id": user_id}

    for question in QUESTIONS:
        answer = ask(question)
        raw_answers[question["key"]] = answer
        profile[question["key"]] = answer

    # Разбираем списки
    profile["values"] = [v.strip() for v in profile.get("values", "").split(",") if v.strip()]
    profile["platforms"] = [p.strip() for p in profile.get("platforms", "").split(",") if p.strip()]
    profile["raw_answers"] = raw_answers

    # Сохраняем
    save_user_profile(profile)

    print(f"\n{'='*55}")
    print(f"{Fore.GREEN}✅ Профиль сохранён!{Style.RESET_ALL}")
    print(f"{'='*55}")
    print(f"  Имя:       {profile.get('name')}")
    print(f"  Профессия: {profile.get('profession')}")
    print(f"  Ниша:      {profile.get('niche')}")
    print(f"  Цель:      {profile.get('goal')}")
    print(f"  Тон:       {profile.get('tone')}")
    print(f"  Платформы: {', '.join(profile.get('platforms', []))}")

    return profile

