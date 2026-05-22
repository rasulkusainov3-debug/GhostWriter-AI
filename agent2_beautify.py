"""
agent2_beautify.py
Агент 2: улучшает посты с айдентикой пользователя + подбирает картинки
Использует: Google Gemini API (бесплатно) + Unsplash

Запуск:
  1. Получи ключ на https://aistudio.google.com/apikey
  2. set GEMINI_API_KEY=ВАШ_КЛЮЧ
  3. python agent2_beautify.py
"""

import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

# ─── НАСТРОЙКИ ────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"

GENERATED_POSTS_FILE = DATA_DIR / "generated_posts.json"
USER_PROFILE_FILE    = DATA_DIR / "user_profile_export.json"
OUTPUT_FILE          = DATA_DIR / "beautified_posts.json"

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL     = "gemini-2.0-flash"   # бесплатная модель, быстрая

UNSPLASH_ACCESS_KEY = os.getenv(
    "UNSPLASH_ACCESS_KEY",
    ""  # демо-ключ (60 req/час)
)

# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ──────────────────────────────────────────────────

def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  💾 Сохранено: {path}")


def call_gemini(prompt: str) -> str:
    """Вызов Google Gemini API (бесплатно, без сторонних библиотек)"""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 1000, "temperature": 0.8}
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"Gemini API ошибка {e.code}: {body}")


def beautify_post(post: dict, profile: dict) -> str:
    """Переписывает пост с живой айдентикой пользователя"""
    values = ", ".join(profile.get("values", []))
    platforms = ", ".join(profile.get("platforms", ["Telegram"]))

    prompt = f"""Ты помогаешь {profile['name']} — {profile['profession']} — написать пост для {platforms}.

ПРОФИЛЬ АВТОРА:
- Имя: {profile['name']}
- Профессия: {profile['profession']}
- Цель: {profile['goal']}
- Тон: {profile['tone']}
- Аудитория: {profile['audience']}
- Ценности: {values}
- Избегать: {profile['avoid']}

ТЕМА ТРЕНДА: {post['trend_topic']}

ЧЕРНОВИК (плохой, со скобками-заглушками):
{post['draft']}

ЗАДАЧА — перепиши пост полностью:
1. Убери все незакрытые [ скобки и заглушки — замени конкретикой из профиля
2. Тон — {profile['tone']}: провоцируй мысль, говори прямо, без воды
3. Добавь личный опыт {profile['name']} как {profile['profession']}
4. Ценности ({values}) должны звучать органично, не в лоб
5. Пиши для аудитории: {profile['audience']}
6. Заканчивай вопросом или провокацией к дискуссии
7. Хэштеги: 3-5 штук, релевантных IT и теме
8. Длина: 150-300 слов
9. НЕ используй: {profile['avoid']}
10. Верни ТОЛЬКО текст поста, без пояснений и заголовков"""

    return call_gemini(prompt)


def get_image_query(post: dict, profile: dict) -> str:
    """Генерирует поисковый запрос для картинки"""
    prompt = f"""Придумай короткий поисковый запрос на английском (3-5 слов) для Unsplash,
чтобы найти атмосферное профессиональное фото к посту.

Тема: {post['trend_topic']}
Профессия автора: {profile['profession']}

Верни ТОЛЬКО поисковый запрос, без кавычек и пояснений."""
    return call_gemini(prompt)


def find_image(query: str) -> dict | None:
    """Ищет фото на Unsplash"""
    q = urllib.parse.quote(query)
    url = (
        f"https://api.unsplash.com/search/photos"
        f"?query={q}&per_page=3&orientation=landscape"
        f"&client_id={UNSPLASH_ACCESS_KEY}"
    )
    try:
        req = urllib.request.Request(url, headers={"Accept-Version": "v1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            if results:
                img = results[0]
                return {
                    "url_small":     img["urls"]["small"],
                    "url_regular":   img["urls"]["regular"],
                    "url_full":      img["urls"]["full"],
                    "author":        img["user"]["name"],
                    "unsplash_link": img["links"]["html"],
                    "alt":           img.get("alt_description", query),
                }
    except Exception as e:
        print(f"    ⚠️  Unsplash ошибка: {e}")
    return None


# ─── ГЛАВНАЯ ЛОГИКА ───────────────────────────────────────────────────────────

def main():
    print("\n╔══════════════════════════════════════════════╗")
    print("║   ✨  АГЕНТ 2: Бьютификация постов          ║")
    print("║      (Google Gemini · бесплатно)            ║")
    print("╚══════════════════════════════════════════════╝\n")

    # Проверка API ключа
    if not GEMINI_API_KEY:
        print("❌ ОШИБКА: Не задан GEMINI_API_KEY\n")
        print("Как получить ключ (бесплатно, 1 минута):")
        print("  1. Зайди на https://aistudio.google.com/apikey")
        print("  2. Нажми 'Create API key'")
        print("  3. Скопируй ключ (начинается с AIza...)\n")
        print("Как задать в терминале (Windows):")
        print("  set GEMINI_API_KEY=AIza...ТВОЙ_КЛЮЧ\n")
        print("Затем снова запусти: python agent2_beautify.py")
        return

    # Загрузка данных
    print("📂 Загружаем данные...")
    posts   = load_json(GENERATED_POSTS_FILE)
    profile = load_json(USER_PROFILE_FILE)
    print(f"  👤 Профиль: {profile['name']} ({profile['profession']})")
    print(f"  📝 Постов к обработке: {len(posts)}\n")

    results = []

    for i, post in enumerate(posts, 1):
        slot  = post.get("slot_id", f"slot_{i}")
        topic = post.get("trend_topic", "")[:50]
        print(f"── [{i}/{len(posts)}] {slot}: {topic}...")

        result = dict(post)

        # 1. Бьютификация текста
        print("  ✍️  Переписываем с айдентикой...", end=" ", flush=True)
        try:
            result["beautified_text"] = beautify_post(post, profile)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            result["beautified_text"] = post.get("final_text", post.get("draft", ""))
            result["beautify_error"]  = str(e)

        time.sleep(0.5)

        # 2. Поиск картинки
        print("  🖼️  Ищем картинку...", end=" ", flush=True)
        try:
            img_query = get_image_query(post, profile)
            result["image_query"] = img_query
            image = find_image(img_query)
            if image:
                result["image"] = image
                print(f"✅ ({img_query})")
            else:
                print(f"⚠️  не найдено ({img_query})")
                result["image"] = None
        except Exception as e:
            print(f"❌ {e}")
            result["image"] = None
            result["image_error"] = str(e)

        results.append(result)
        print()
        time.sleep(1)

    # Сохранение
    save_json(results, OUTPUT_FILE)

    print(f"\n{'='*50}")
    print(f"🎉 ГОТОВО! Обработано {len(results)} постов.")
    print(f"📄 Результат: {OUTPUT_FILE}")
    print(f"{'='*50}\n")

    # Превью первого поста
    if results:
        print("── ПРЕВЬЮ первого поста ──────────────────────\n")
        print(results[0].get("beautified_text", ""))
        if results[0].get("image"):
            print(f"\n🖼️  Картинка: {results[0]['image']['url_regular']}")
            print(f"   Автор: {results[0]['image']['author']} (Unsplash)")


if __name__ == "__main__":
    main()
