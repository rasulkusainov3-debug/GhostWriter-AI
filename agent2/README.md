# Агент 2 — Генератор контента

Читает данные от Агента 1 и генерирует готовые посты для соцсетей.

## Структура

```
agent2/
├── main.py                        ← запускай это
├── planner/
│   └── content_planner.py         ← контент-план на неделю
├── generator/
│   ├── template_generator.py      ← генерация через шаблоны (без LLM)
│   └── llm_polisher.py            ← полировка через Groq/Gemini
└── platforms/
    └── adapter.py                 ← адаптация под LinkedIn/Telegram/Instagram
```

## Быстрый старт

```bash
# 1. Сначала запусти Агент 1 (data/ должна содержать JSON-файлы)
python main.py   # Агент 1

# 2. Запусти Агент 2
python agent2/main.py

# Только шаблоны, без LLM
python agent2/main.py --no-llm

# Только LinkedIn
python agent2/main.py --platform LinkedIn
```

## .env ключи (опционально — для LLM-полировки)

```
# Groq (рекомендуется): https://console.groq.com — бесплатно
GROQ_API_KEY=gsk_...

# Gemini (запасной): https://aistudio.google.com — бесплатно
GEMINI_API_KEY=AIza...
```

Без ключей агент всё равно работает — через шаблоны.

## Что на выходе

`data/generated_posts.json` — список готовых постов:

```json
[
  {
    "slot_id":    "slot_1",
    "date":       "2025-04-22",
    "time":       "08:00",
    "platform":   "LinkedIn",
    "format":     "кейс",
    "trend_topic": "How I got a 40% salary raise",
    "keywords":   ["salary negotiation", "personal brand"],
    "final_text": "Я вырос по зарплате на 40%...",
    "stats":      { "chars": 847, "limit": 3000, "fits": true }
  }
]
```

## Как это работает

```
trends_export.json  ──┐
                       ├─► content_planner  ──► план слотов
user_profile.json  ───┘         │
                                 ▼
                    template_generator  ──► черновик
                                 │
                                 ▼ (если есть ключ)
                        llm_polisher    ──► полированный текст
                                 │
                                 ▼
                      platform adapter  ──► готовый пост
```
