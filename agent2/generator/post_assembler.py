"""
agent2/generator/post_assembler.py — M4: Сборщик постов

Склеивает три блока в единый связный пост:
  Блок A (0.3) — Агент 2: хук + тренд + каркас
  Блок B (0.3) — Агент 3: призма пользователя
  Блок C (0.4) — Агент 4: призма аудитории

Два режима сборки:
  1. LLM — добавляет плавные переходы, убирает повторы
  2. Конкатенация — простая склейка если LLM недоступен
"""

import re
import os
from dotenv import load_dotenv

load_dotenv()

PLATFORM_LIMITS = {
    "LinkedIn":  3000,
    "Telegram":  4096,
    "Instagram": 2200,
}

# ── Промпт сборщика ───────────────────────────────────────────────────

ASSEMBLER_SYSTEM = "Ты редактор. Склеиваешь фрагменты поста в единый связный текст. Только финальный текст."

ASSEMBLER_PROMPT = """Собери три блока в единый связный пост для {platform}.

Блок A — хук и тренд (30% поста):
{block_a}

Блок B — профессиональная призма автора (30% поста):
{block_b}

Блок C — для аудитории, главная часть (40% поста):
{block_c}

Правила сборки:
- Порядок строго: A → B → C
- Между блоками добавь плавный переход (одно короткое предложение-мостик)
- Убери повторяющиеся мысли если они есть в нескольких блоках
- Хэштеги из Блока A поставь в самый конец
- Итоговый текст не должен превышать {char_limit} символов
- Только текст поста, без заголовков и пояснений"""


# ── Контроль длины ────────────────────────────────────────────────────

def _extract_hashtags(text: str) -> tuple[str, str]:
    """Разделяет текст и хэштеги."""
    tags   = re.findall(r"#\w+", text)
    body   = re.sub(r"(#\w+\s?)+", "", text).strip()
    return body, " ".join(tags)


def validate_and_trim(block_a: str, block_b: str, block_c: str,
                      platform: str) -> tuple[str, str, str]:
    """
    Проверяет что сумма блоков вписывается в лимит платформы.
    При превышении — обрезает пропорционально долям.
    """
    limit = PLATFORM_LIMITS.get(platform, 3000)
    total = len(block_a) + len(block_b) + len(block_c)

    if total <= limit:
        return block_a, block_b, block_c

    # Обрезаем с запасом на переходы (150 симв)
    available = limit - 150
    ta = int(available * 0.27)   # 0.3 × 0.9
    tb = int(available * 0.27)
    tc = int(available * 0.46)   # 0.4 × больше — аудиторный блок важнее

    def trim(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        cut = text[:max_len]
        last_space = cut.rfind(" ")
        return (cut[:last_space] if last_space > max_len * 0.8 else cut) + "..."

    return trim(block_a, ta), trim(block_b, tb), trim(block_c, tc)


# ── Метрика качества сборки ───────────────────────────────────────────

def calc_assembly_score(final_text: str,
                        block_a: str, block_b: str, block_c: str) -> float:
    """
    Проверяет что ключевые слова каждого блока попали в финальный текст.
    Возвращает 0.0–1.0.
    """
    from collections import Counter

    def top_words(text: str, n: int = 3) -> list[str]:
        words = re.findall(r"\b\w{4,}\b", text.lower())
        stop  = {"это", "того", "тебя", "свой", "свою", "that", "this", "with", "have", "from"}
        words = [w for w in words if w not in stop]
        return [w for w, _ in Counter(words).most_common(n)]

    final_lower = final_text.lower()
    score = 0
    total = 0

    for block in [block_a, block_b, block_c]:
        for kw in top_words(block):
            total += 1
            if kw in final_lower:
                score += 1

    return round(score / total, 2) if total else 0.0


# ── LLM сборка ────────────────────────────────────────────────────────

def _assemble_with_llm(block_a: str, block_b: str, block_c: str,
                       platform: str) -> str | None:
    """Пробует собрать пост через LLM. Возвращает None при ошибке."""
    limit       = PLATFORM_LIMITS.get(platform, 3000)
    user_prompt = ASSEMBLER_PROMPT.format(
        platform   = platform,
        block_a    = block_a,
        block_b    = block_b,
        block_c    = block_c,
        char_limit = limit,
    )

    # Ollama
    try:
        import ollama as ol
        client = ol.Client(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
        client.list()
        resp = client.chat(
            model=os.getenv("OLLAMA_MODEL", "mistral"),
            messages=[
                {"role": "system", "content": ASSEMBLER_SYSTEM},
                {"role": "user",   "content": user_prompt},
            ],
            options={"temperature": 0.5, "num_predict": 800},
        )
        result = resp["message"]["content"].strip()
        if result and len(result) > 100:
            print("    🏠 Сборщик [Ollama] ✅")
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
                    {"role": "system", "content": ASSEMBLER_SYSTEM},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens=800,
                temperature=0.5,
            )
            result = resp.choices[0].message.content.strip()
            if result and len(result) > 100:
                print("    ⚡ Сборщик [Groq] ✅")
                return result
    except Exception:
        pass

    # Gemini
    try:
        key = os.getenv("GEMINI_API_KEY", "")
        if key:
            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=ASSEMBLER_SYSTEM)
            result = model.generate_content(user_prompt).text.strip()
            if result and len(result) > 100:
                print("    🌐 Сборщик [Gemini] ✅")
                return result
    except Exception:
        pass

    return None


# ── Простая конкатенация (запасной) ──────────────────────────────────

def _simple_concat(block_a: str, block_b: str, block_c: str) -> str:
    """Склеивает блоки с переносами. Хэштеги всегда в конце."""
    body_a, hashtags = _extract_hashtags(block_a)
    body_b, _        = _extract_hashtags(block_b)
    body_c, _        = _extract_hashtags(block_c)

    parts = [p.strip() for p in [body_a, body_b, body_c] if p.strip()]
    text  = "\n\n".join(parts)
    if hashtags:
        text += f"\n\n{hashtags}"
    return text


# ── Главная функция ───────────────────────────────────────────────────

def assemble_post(block_a: str, block_b: str, block_c: str,
                  slot: dict) -> tuple[str, float]:
    """
    Собирает финальный пост из трёх блоков.
    Возвращает (final_text, assembly_score).
    """
    platform = slot.get("platform", "LinkedIn")

    # Проверяем и обрезаем блоки
    block_a, block_b, block_c = validate_and_trim(block_a, block_b, block_c, platform)

    # Пробуем LLM сборку
    final = _assemble_with_llm(block_a, block_b, block_c, platform)

    if not final:
        # Конкатенация
        final = _simple_concat(block_a, block_b, block_c)
        print("    📎 Сборщик [конкатенация] ✅")

    # Финальная проверка лимита
    limit = PLATFORM_LIMITS.get(platform, 3000)
    if len(final) > limit:
        final = final[:limit - 3].rsplit(" ", 1)[0] + "..."

    score = calc_assembly_score(final, block_a, block_b, block_c)
    return final, score
