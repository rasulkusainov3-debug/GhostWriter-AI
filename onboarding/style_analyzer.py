"""
onboarding/style_analyzer.py

Анализирует примеры постов и извлекает стиль автора.
Заменяет вопросы про тон, формат, длину предложений.
Пользователь скидывает 1-3 примера — система копирует стиль.
"""

import json
import os
from dotenv import load_dotenv

load_dotenv()

STYLE_PROMPT = """Проанализируй этот пост и извлеки стиль автора.

Пост:
---
{post_text}
---

Верни ТОЛЬКО JSON без пояснений:
{{
  "tone": "экспертный / дружелюбный / провокационный / вдохновляющий / нейтральный",
  "sentence_length": "короткие / средние / длинные",
  "uses_lists": true или false,
  "uses_numbers": true или false,
  "opening_style": "вопрос / утверждение / история / факт",
  "vocabulary_level": "простой / профессиональный / смешанный",
  "personal_ratio": 0.7,
  "avg_post_length": "короткий / средний / длинный"
}}"""


def analyze_style(post_texts: list[str]) -> dict:
    """
    Анализирует список постов и возвращает усреднённый style_profile.
    Работает через LLM. При недоступности — возвращает дефолт.
    """
    DEFAULT_STYLE = {
        "tone":            "экспертный",
        "sentence_length": "средние",
        "uses_lists":      True,
        "uses_numbers":    False,
        "opening_style":   "утверждение",
        "vocabulary_level":"профессиональный",
        "personal_ratio":  0.5,
        "avg_post_length": "средний",
    }

    if not post_texts:
        return DEFAULT_STYLE

    results = []

    for post in post_texts[:3]:   # максимум 3 поста
        if len(post.strip()) < 50:
            continue

        # Пробуем Groq
        try:
            groq_key = os.getenv("GROQ_API_KEY", "")
            if groq_key:
                from groq import Groq
                resp = Groq(api_key=groq_key).chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": STYLE_PROMPT.format(post_text=post[:1500])}],
                    max_tokens=300,
                    temperature=0.2,
                )
                text = resp.choices[0].message.content.strip()
                text = text.replace("```json", "").replace("```", "").strip()
                results.append(json.loads(text))
                continue
        except Exception:
            pass

        # Пробуем Gemini
        try:
            gemini_key = os.getenv("GEMINI_API_KEY", "")
            if gemini_key:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                resp  = model.generate_content(STYLE_PROMPT.format(post_text=post[:1500]))
                text  = resp.text.strip().replace("```json", "").replace("```", "").strip()
                results.append(json.loads(text))
                continue
        except Exception:
            pass

    if not results:
        return DEFAULT_STYLE

    # Усредняем результаты нескольких постов
    merged = {}

    # Строковые поля — берём самое частое
    for key in ["tone", "sentence_length", "opening_style", "vocabulary_level", "avg_post_length"]:
        values = [r.get(key, "") for r in results if r.get(key)]
        merged[key] = max(set(values), key=values.count) if values else DEFAULT_STYLE[key]

    # Булевы поля — берём большинство
    for key in ["uses_lists", "uses_numbers"]:
        values = [r.get(key) for r in results if r.get(key) is not None]
        merged[key] = sum(1 for v in values if v) > len(values) / 2 if values else DEFAULT_STYLE[key]

    # Числа — среднее
    ratios = [r.get("personal_ratio", 0.5) for r in results]
    merged["personal_ratio"] = round(sum(ratios) / len(ratios), 2)

    return merged
