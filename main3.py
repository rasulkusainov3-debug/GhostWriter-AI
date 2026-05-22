import json
import os
import urllib.parse
import http.server
import requests
from pathlib import Path

# --- Настройки путей ---
BASE_DIR     = Path(__file__).parent
DATA_SOURCE  = BASE_DIR / "data"
IMAGES_DIR   = DATA_SOURCE / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

PORT = 8000

# ─── Слияние всех JSON в один ─────────────────────────────────────────────────

def merge_all_jsons():
    """
    Читает все 4 JSON-файла и собирает единый список постов.
    Каждый итоговый пост содержит:
      - все уникальные поля из generated_posts  (текст, черновик, статистика)
      - уникальные поля из content_plan         (формат, идея поста)
      - полный объект trend из content_plan     (источник, кол-во постов, summary)
      - доп. данные из trends_export            (если есть новые поля)
      - профиль пользователя (author)           из user_profile_export
    Дублирующиеся поля с одинаковым значением не повторяются.
    """

    # Загрузка файлов
    def load(name):
        p = DATA_SOURCE / name
        if not p.exists():
            print(f"  ⚠️  Файл не найден: {p}")
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    generated = load("generated_posts.json") or []
    plan      = load("content_plan.json")    or []
    trends_ex = load("trends_export.json")   or {}
    profile   = load("user_profile_export.json") or {}

    # trends_export → словарь по id для быстрого поиска
    trends_by_id = {t["id"]: t for t in trends_ex.get("trends", [])}

    # plan → словарь по slot_id
    plan_by_slot = {s["slot_id"]: s for s in plan}

    # Профиль — очищаем дубли внутри (raw_answers = то же самое что верхний уровень)
    clean_profile = {
        "name":       profile.get("name"),
        "profession": profile.get("profession"),
        "niche":      profile.get("niche"),
        "goal":       profile.get("goal"),
        "tone":       profile.get("tone"),
        "audience":   profile.get("audience"),
        "values":     profile.get("values", []),
        "avoid":      profile.get("avoid"),
        "platforms":  profile.get("platforms", []),
    }

    merged_posts = []

    for gp in generated:
        slot_id = gp["slot_id"]
        cp      = plan_by_slot.get(slot_id, {})
        cp_trend = cp.get("trend", {})

        # Берём полный тренд из trends_export если есть (там те же поля, но проверяем)
        full_trend = dict(cp_trend)
        trend_id   = cp_trend.get("id")
        if trend_id and trend_id in trends_by_id:
            ext = trends_by_id[trend_id]
            for k, v in ext.items():
                # добавляем только если поле отсутствует или значение отличается
                if k not in full_trend or full_trend[k] != v:
                    full_trend[k] = v

        # Парсим keywords из строки в список (они хранятся как JSON-строка)
        def parse_kw(raw):
            if isinstance(raw, list):
                return raw
            try:
                return json.loads(raw)
            except Exception:
                return [raw] if raw else []

        # ── Собираем итоговый пост ──────────────────────────────────────────
        post = {
            # Идентификация слота
            "slot_id":   slot_id,
            "date":      gp.get("date"),
            "time":      gp.get("time"),
            "platform":  gp.get("platform"),
            "format":    gp.get("format"),

            # Тренд (без дублей)
            "trend": {
                "id":          full_trend.get("id"),
                "source":      full_trend.get("source"),
                "topic":       full_trend.get("topic"),
                "keywords":    parse_kw(full_trend.get("keywords", "[]")),
                "posts_count": full_trend.get("posts_count"),
                "summary":     full_trend.get("summary"),
                "collected_at":full_trend.get("collected_at"),
                "expires_at":  full_trend.get("expires_at"),
            },

            # Идея поста (из content_plan; в generated_posts то же самое — не дублируем)
            "post_idea": cp.get("post_idea") or gp.get("post_idea"),

            # Тексты (только из generated_posts)
            "draft":        gp.get("draft"),
            "final_text":   gp.get("final_text"),

            # Статистика
            "stats": gp.get("stats"),

            # Статусы
            "status":       gp.get("status"),
            "generated_at": gp.get("generated_at"),

            # Автор — профиль пользователя
            "author": clean_profile,

            # Картинка (будет заполнена после генерации)
            "image_path": None,
        }

        merged_posts.append(post)

    return merged_posts, trends_ex, clean_profile


# ─── Генерация картинки ───────────────────────────────────────────────────────

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# Стоп-слова которые не помогают в поиске картинок
_STOP_WORDS = {
    "how", "to", "the", "a", "an", "i", "if", "it", "in", "on", "at",
    "of", "for", "and", "or", "is", "be", "so", "my", "you", "your",
    "would", "could", "full", "course", "feels", "start", "over", "with",
    "its", "its", "by", "from", "this", "that", "was", "were", "are",
    "what", "why", "when", "entire", "betting", "ever"
}

def _make_search_query(raw_topic: str) -> str:
    """Извлекает 2-3 ключевых слова из заголовка тренда для поиска картинки."""
    words = raw_topic.lower().replace("'", "").replace("'", "").split()
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 3][:3]
    return " ".join(keywords) if keywords else "technology workspace"


def _pexels_search(query: str) -> str | None:
    """Ищет фото через Pexels API и возвращает прямую ссылку на файл."""
    if not PEXELS_API_KEY:
        return None
    try:
        q = urllib.parse.quote(query)
        url = f"https://api.pexels.com/v1/search?query={q}&per_page=5&orientation=landscape"
        r = requests.get(url, headers={"Authorization": PEXELS_API_KEY}, timeout=10)
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if photos:
            return photos[0]["src"]["large"]   # 940×627 без лимита
    except Exception as e:
        print(f"      ↳ Pexels API: ошибка — {e}")
    return None


def download_img(query, slot_id):
    """
    Скачивает реальную фотографию по теме поста.
    Стратегия (все источники бесплатны):
      1. Pexels API       — поиск по теме (нужен бесплатный ключ, 200 req/час)
      2. Unsplash Source  — поиск по теме без ключа (иногда даёт 503)
      3. Picsum Photos    — случайное красивое фото (всегда работает, запасной)
    """
    folder = IMAGES_DIR / slot_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "cover.jpg"

    # Короткий запрос из ключевых слов темы
    kw_query    = _make_search_query(query)
    clean_query = urllib.parse.quote(kw_query)

    print(f"   [⏳] Ищу фото для {slot_id}: «{query[:50]}» → ключ: «{kw_query}»")

    # ── 1. Pexels (поиск по теме) ──────────────────────────────────────────────
    if PEXELS_API_KEY:
        direct_url = _pexels_search(kw_query)
        if direct_url:
            try:
                r = requests.get(direct_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                if "image" in r.headers.get("Content-Type", "") and len(r.content) > 5000:
                    with open(path, "wb") as f:
                        f.write(r.content)
                    print(f"   [✅] Pexels → {path} ({len(r.content)//1024} KB)")
                    return str(path.relative_to(BASE_DIR)).replace("\\", "/")
            except Exception as e:
                print(f"      ↳ Pexels download: ошибка — {e}")

    # ── 2. Unsplash Source (поиск по теме, без ключа) ─────────────────────────
    fallbacks = [
        ("Unsplash",         f"https://source.unsplash.com/800x600/?{clean_query}"),
        ("Unsplash IT",      "https://source.unsplash.com/800x600/?technology,laptop"),
        ("Picsum",           f"https://picsum.photos/800/600?random={abs(hash(slot_id)) % 9999}"),
    ]

    for name, url in fallbacks:
        try:
            r = requests.get(url, timeout=20,
                             headers={"User-Agent": "Mozilla/5.0"},
                             allow_redirects=True)
            r.raise_for_status()
            ct = r.headers.get("Content-Type", "")
            if "image" not in ct:
                print(f"      ↳ {name}: не картинка, пропуск"); continue
            if len(r.content) < 5000:
                print(f"      ↳ {name}: файл слишком мал, пропуск"); continue
            with open(path, "wb") as f:
                f.write(r.content)
            print(f"   [✅] {name} → {path} ({len(r.content)//1024} KB)")
            return str(path.relative_to(BASE_DIR)).replace("\\", "/")
        except Exception as e:
            print(f"      ↳ {name}: ошибка — {e}")

    print(f"   [❌] Все источники недоступны для {slot_id}")
    return None


# ─── HTTP сервер ──────────────────────────────────────────────────────────────

class MyHandler(http.server.SimpleHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, fmt, *args):
        pass  # тихий режим

    def do_GET(self):
        # Отдаём объединённые данные для фронтенда
        if self.path == "/api/data":
            posts, trends_ex, profile = merge_all_jsons()
            self._send_json({
                "posts":   posts,
                "trends":  trends_ex.get("trends", []),
                "profile": profile,
                "meta": {
                    "niche":       trends_ex.get("niche"),
                    "exported_at": trends_ex.get("exported_at"),
                    "count":       trends_ex.get("count"),
                }
            })
        else:
            # Отдаём статические файлы (index.html)
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/beautify":
            print("\n🚀 Сигнал получен! Сливаю JSON-файлы и генерирую картинки...")

            posts, trends_ex, profile = merge_all_jsons()

            if not posts:
                self._send_err("Нет данных: проверь папку data/")
                return

            for p in posts:
                topic     = p["trend"]["topic"] or "IT Technology"
                slot_id   = p["slot_id"]
                img_path  = download_img(topic, slot_id)
                p["image_path"] = img_path

            # Сохраняем итоговый merged JSON
            out_file = DATA_SOURCE / "merged_posts.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(posts, f, ensure_ascii=False, indent=2)

            print(f"\n🏁 ГОТОВО!")
            print(f"   📄 JSON: {out_file}")
            print(f"   🖼  Картинки: {IMAGES_DIR}")
            self._send_json({"ok": True, "count": len(posts), "file": str(out_file)})

        else:
            self.send_error(404)

    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_err(self, msg):
        self._send_json({"ok": False, "error": msg})


if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"📡  СЕРВЕР: http://127.0.0.1:{PORT}")
    print(f"📂  Папка данных: {DATA_SOURCE}")
    print(f"{'='*55}")

    # Предварительный тест слияния
    posts, _, profile = merge_all_jsons()
    print(f"✅  JSON-файлы прочитаны: {len(posts)} постов, автор: {profile.get('name')}")
    print(f"    Поля одного поста: {list(posts[0].keys())}\n")

    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), MyHandler).serve_forever()