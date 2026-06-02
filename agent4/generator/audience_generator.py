"""
agent4/generator/audience_generator.py

Генерирует 0.4 поста на языке конкретной аудитории.
Это главная часть поста: без жаргона, с пояснениями,
понятная любому читателю из указанной группы.

Адаптирует текст под четыре типа аудитории:
  - широкая публика      → объясняет термины, использует аналогии
  - молодые специалисты  → конкретные действия прямо сейчас
  - руководители         → сразу суть, данные, последствия
  - профессионалы        → детали, нюансы, без упрощений
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Профили аудиторий ─────────────────────────────────────────────────

AUDIENCE_PROFILES = {
    "широкая публика": {
        "level":       "novice",
        "instruction": (
            "Объясняй каждый специальный термин сразу после его упоминания в скобках. "
            "Используй аналогии из повседневной жизни. "
            "Пиши так, чтобы понял человек без профильного образования."
        ),
        "avoid": "профессиональный жаргон, аббревиатуры без расшифровки, сложные конструкции",
        "use":   "конкретные примеры из жизни, цифры, короткие истории, аналогии",
    },
    "молодые специалисты": {
        "level":       "intermediate",
        "instruction": (
            "Давай конкретные действия которые можно сделать прямо сейчас. "
            "Фокусируйся на практике, а не на теории. "
            "Признавай что путь непростой — это создаёт доверие."
        ),
        "avoid": "очевидные объяснения базовых понятий, менторский тон сверху вниз",
        "use":   "практические советы, что делать на этой неделе, честный опыт",
    },
    "руководители": {
        "level":       "expert",
        "instruction": (
            "Первые два предложения — главная мысль и вывод. Детали потом. "
            "Оперируй последствиями, цифрами и стратегическим контекстом. "
            "Уважай время читателя — убирай всё лишнее."
        ),
        "avoid": "длинные вступления, пространные объяснения, очевидные факты",
        "use":   "данные, последствия для бизнеса, стратегический контекст, ROI",
    },
    "профессионалы той же сферы": {
        "level":       "expert",
        "instruction": (
            "Говори на равных. Используй профессиональные термины без объяснений. "
            "Поднимай нюансы и спорные моменты которые знают только практики. "
            "Избегай упрощений которые звучат снисходительно."
        ),
        "avoid": "объяснения базовых понятий, излишние вступления",
        "use":   "детали, нюансы, спорные вопросы, конкретные кейсы из практики",
    },
}

DEFAULT_AUDIENCE = AUDIENCE_PROFILES["широкая публика"]

# ── Системный промпт ──────────────────────────────────────────────────

AUDIENCE_SYSTEM = "Ты опытный копирайтер. Пишешь понятно и по делу. Только текст без заголовков."

AUDIENCE_PROMPT = """Напиши основную часть поста для личного бренда.

Тема: {topic}
Ключевые слова: {keywords}
Профессия автора: {profession}
Аудитория: {audience_type}
Уровень: {level}

Правила:
{instruction}

Избегай: {avoid}
Используй: {use}

Объём: 5–7 предложений. Это главная часть — читатель должен получить реальную пользу.
Только текст блока, без заголовков, хэштегов и пояснений."""

# ── Запасные шаблоны (без LLM) ───────────────────────────────────────

AUDIENCE_TEMPLATES = {
    "novice": (
        "{topic_simple} — это тема которая касается каждого кто думает о карьере. "
        "Большинство людей {common_block}. "
        "На самом деле всё проще: начни с малого и делай это регулярно. "
        "Один небольшой шаг в неделю через год превращается в заметный результат. "
        "Если ты никогда не думал об этом раньше — самое время начать."
    ),
    "intermediate": (
        "Вот что реально работает прямо сейчас: {action}. "
        "Не жди идеальных условий — их не будет. "
        "Сделай одно конкретное действие сегодня и повтори завтра. "
        "Именно последовательность, а не интенсивность даёт результат. "
        "Что ты можешь сделать в ближайшие 24 часа?"
    ),
    "expert": (
        "Данные подтверждают: {topic} напрямую влияет на карьерные результаты. "
        "Ключевой фактор — системность, а не разовые усилия. "
        "Те кто выстраивает процесс, обгоняют тех кто действует ситуативно. "
        "Вопрос не в том делать это или нет — вопрос в том когда вы начнёте."
    ),
}


def _get_audience_profile(profile: dict) -> dict:
    """Определяет профиль аудитории из данных пользователя."""
    audience = (
        profile.get("audience_type")
        or profile.get("audience")
        or "широкая публика"
    ).lower()

    for key, ap in AUDIENCE_PROFILES.items():
        if key in audience or audience in key:
            return ap

    return DEFAULT_AUDIENCE


def _fallback_block(slot: dict, profile: dict, ap: dict) -> str:
    """Запасной шаблонный блок без LLM."""
    level    = ap.get("level", "novice")
    topic    = slot.get("trend", {}).get("topic", "карьерное развитие")[:60]
    action   = slot.get("post_idea", "работать над личным брендом")[:80]

    template = AUDIENCE_TEMPLATES.get(level, AUDIENCE_TEMPLATES["novice"])
    return template.format(
        topic_simple = topic,
        common_block = "не знают с чего начать",
        action       = action,
        topic        = topic,
    )


def generate_audience_block(slot: dict, profile: dict) -> str:
    """
    Генерирует главный блок поста (0.4) для аудитории пользователя.
    LLM (Ollama → Groq → Gemini) → шаблон.
    """
    ap = _get_audience_profile(profile)

    trend    = slot.get("trend", {})
    topic    = trend.get("topic", slot.get("post_idea", "карьерный рост"))[:80]
    keywords = ", ".join(trend.get("keywords", [])[:4])

    user_prompt = AUDIENCE_PROMPT.format(
        topic        = topic,
        keywords     = keywords or topic,
        profession   = profile.get("profession", "специалист"),
        audience_type= profile.get("audience_type") or profile.get("audience", "широкая публика"),
        level        = ap["level"],
        instruction  = ap["instruction"],
        avoid        = ap["avoid"],
        use          = ap["use"],
    )

    # Ollama
    try:
        import ollama as ol
        client = ol.Client(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
        client.list()
        resp = client.chat(
            model=os.getenv("OLLAMA_MODEL", "mistral"),
            messages=[
                {"role": "system", "content": AUDIENCE_SYSTEM},
                {"role": "user",   "content": user_prompt},
            ],
            options={"temperature": 0.72, "num_predict": 500},
        )
        result = resp["message"]["content"].strip()
        if result and len(result) > 80:
            print("    🏠 Агент 4 [Ollama] ✅")
            return result
    except Exception:
        pass

    # Groq
    try:
        key = os.getenv("GROQ_API_KEY", "")
        if key:
            from groq import Groq
            resp = Groq(api_key=key).chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": AUDIENCE_SYSTEM},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens=500,
                temperature=0.72,
            )
            result = resp.choices[0].message.content.strip()
            if result and len(result) > 80:
                print("    ⚡ Агент 4 [Groq] ✅")
                return result
    except Exception:
        pass

    # Gemini
    try:
        key = os.getenv("GEMINI_API_KEY", "")
        if key:
            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=AUDIENCE_SYSTEM)
            result = model.generate_content(user_prompt).text.strip()
            if result and len(result) > 80:
                print("    🌐 Агент 4 [Gemini] ✅")
                return result
    except Exception:
        pass

    # Шаблон
    result = _fallback_block(slot, profile, ap)
    print("    📋 Агент 4 [шаблон] ✅")
    return result
