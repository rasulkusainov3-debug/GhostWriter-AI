"""
agent2/generator/llm_polisher.py

LLM-полировщик с цепочкой: Ollama (локально) → Groq (облако) → Gemini (облако) → шаблон

Провайдеры:
  1. Ollama  — локально, бесплатно, без лимитов
               pip install ollama
               ollama pull mistral   (4GB, лучший RU)
               ollama pull llama3.2  (2GB, быстрее)
               ollama pull gemma2:2b (1.5GB, слабые машины)
  2. Groq    — облако, 14 400 req/day бесплатно
               pip install groq | ключ: console.groq.com
  3. Gemini  — облако, 1 500 req/day бесплатно
               pip install google-generativeai | ключ: aistudio.google.com
"""

import os
from dotenv import load_dotenv
load_dotenv()

OLLAMA_HOST  = os.getenv("OLLAMA_HOST",  "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
GROQ_MODEL   = "llama-3.1-8b-instant"
GEMINI_MODEL = "gemini-1.5-flash"

SYSTEM_PROMPT = """Ты опытный копирайтер для личного бренда в соцсетях.
Перепиши черновик поста: сохрани структуру и факты, убери канцелярит,
сделай первое предложение цепляющим. Не выдумывай цифры.
Хэштеги оставь в конце без изменений.
Верни ТОЛЬКО готовый текст. Никаких пояснений."""


def _prompt(draft, slot, profile):
    return f"""Перепиши черновик поста для личного бренда.

Контекст:
- Платформа: {slot.get("platform","LinkedIn")}
- Формат: {slot.get("format","пост")}
- Тон: {profile.get("tone","экспертный")}
- Профессия: {profile.get("profession","специалист")}
- Цель: {profile.get("goal","карьерный рост")}
- Аудитория: {profile.get("audience","профессионалы")}
- Ценности: {", ".join(profile.get("values",[]))}

Черновик:
---
{draft}
---
Только текст поста."""


# ── Ollama ────────────────────────────────────────────────────────────

def _ollama(draft, slot, profile):
    try:
        import ollama as ol
    except ImportError:
        raise RuntimeError("ollama не установлен: pip install ollama")
    client = ol.Client(host=OLLAMA_HOST)
    try:
        client.list()
    except Exception:
        raise RuntimeError(
            f"Ollama не запущена на {OLLAMA_HOST}. "
            f"Запусти: ollama serve && ollama pull {OLLAMA_MODEL}"
        )
    r = client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": _prompt(draft, slot, profile)},
        ],
        options={"temperature": 0.75, "num_predict": 800},
    )
    return r["message"]["content"].strip()


# ── Groq ──────────────────────────────────────────────────────────────

def _groq(draft, slot, profile):
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise ValueError("GROQ_API_KEY не задан — console.groq.com")
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq не установлен: pip install groq")
    r = Groq(api_key=key).chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": _prompt(draft, slot, profile)},
        ],
        max_tokens=800,
        temperature=0.75,
    )
    return r.choices[0].message.content.strip()


# ── Gemini ────────────────────────────────────────────────────────────

def _gemini(draft, slot, profile):
    key = os.getenv("GEMINI_API_KEY", "") 
    if not key:
        raise ValueError("GEMINI_API_KEY не задан — aistudio.google.com")
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError("google-generativeai не установлен")
    genai.configure(api_key=key)
    m = genai.GenerativeModel(GEMINI_MODEL, system_instruction=SYSTEM_PROMPT)
    return m.generate_content(_prompt(draft, slot, profile)).text.strip()


# ── Fallback-цепочка ──────────────────────────────────────────────────

PROVIDERS = [
    (_ollama, "Ollama (локально)", "🏠"),
    (_groq,   "Groq (облако)",     "⚡"),
    (_gemini, "Gemini (облако)",   "🌐"),
]


def polish_with_llm(draft, slot, profile):
    """Ollama → Groq → Gemini → возвращает оригинал если всё недоступно."""
    for fn, name, icon in PROVIDERS:
        try:
            result = fn(draft, slot, profile)
            if result and len(result) > 50:
                print(f"    {icon} [{name}] ✅")
                return result
        except RuntimeError as e:
            print(f"    ⏭  [{name}]: {str(e).splitlines()[0][:70]}")
        except Exception as e:
            print(f"    ⚠️  [{name}]: {type(e).__name__} — {str(e)[:60]}")
    print("    ℹ️  LLM недоступен — используем шаблон")
    return draft


# ── Диагностика ───────────────────────────────────────────────────────

def check_providers():
    """python agent2/generator/llm_polisher.py"""
    print("\n── Диагностика LLM-провайдеров ──────────────────\n")

    print("🏠 Ollama (локально)")
    try:
        import ollama as ol
        resp  = ol.Client(host=OLLAMA_HOST).list()
        names = [m["model"] for m in resp.get("models", [])]
        found = [m for m in names if OLLAMA_MODEL in m]
        if found:
            print(f"   ✅ Запущена, модель {OLLAMA_MODEL!r} найдена")
        else:
            print(f"   ⚠️  Запущена, но {OLLAMA_MODEL!r} не скачана")
            print(f"      Запусти: ollama pull {OLLAMA_MODEL}")
            if names:
                print(f"      Доступны: {chr(44).join(names[:4])}")
    except ImportError:
        print("   ❌ pip install ollama")
    except Exception:
        print(f"   ❌ Не запущена: ollama serve && ollama pull {OLLAMA_MODEL}")

    print("\n⚡ Groq (14 400 req/day бесплатно)")
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        print("   ❌ GROQ_API_KEY не задан → console.groq.com")
    else:
        try:
            from groq import Groq
            Groq(api_key=key).models.list()
            print("   ✅ Ключ валиден")
        except ImportError:
            print("   ❌ pip install groq")
        except Exception as e:
            print(f"   ⚠️  {str(e)[:60]}")

    print("\n🌐 Gemini (1 500 req/day бесплатно)")
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        print("   ❌ GEMINI_API_KEY не задан → aistudio.google.com")
    else:
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            print("   ✅ Ключ задан")
        except ImportError:
            print("   ❌ pip install google-generativeai")
        except Exception as e:
            print(f"   ⚠️  {str(e)[:60]}")

    print("\n─────────────────────────────────────────────────")
    print("Рекомендация: Ollama для работы оффлайн,")
    print("Groq как быстрый облачный запасной вариант.\n")


if __name__ == "__main__":
    check_providers()
