"""
agent2/planner/content_planner.py
Читает тренды + профиль → строит контент-план на неделю.
"""
import json, random
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"

PLATFORM_RULES = {
    "LinkedIn":  {"max_chars":3000,"best_days":["Tuesday","Wednesday","Thursday"],"best_times":["08:00","12:00","17:00"],"formats":["кейс","совет","история","список","мнение"],"hashtag_max":5},
    "Telegram":  {"max_chars":4096,"best_days":["Monday","Wednesday","Friday"],"best_times":["09:00","13:00","20:00"],"formats":["короткий совет","разбор","вопрос аудитории","история"],"hashtag_max":3},
    "Instagram": {"max_chars":2200,"best_days":["Tuesday","Thursday","Saturday"],"best_times":["11:00","14:00","19:00"],"formats":["история успеха","карусель","совет","мнение"],"hashtag_max":15},
}

FORMAT_BY_TREND = {
    "salary":["кейс","история","совет"],"linkedin":["совет","кейс","список"],
    "brand":["история","мнение","кейс"],"skills":["список","совет","разбор"],
    "negotiation":["история","кейс","совет"],"career":["кейс","список","мнение"],
    "default":["кейс","совет","история"],
}

def _detect_type(keywords):
    s = " ".join(keywords).lower()
    for t in ["salary","linkedin","brand","skills","negotiation","career"]:
        if t in s: return t
    return "default"

def _next_best_day(from_date, best_days):
    day_map = {"Monday":0,"Tuesday":1,"Wednesday":2,"Thursday":3,"Friday":4,"Saturday":5,"Sunday":6}
    targets = {day_map[d] for d in best_days}
    for i in range(1, 8):
        c = from_date + timedelta(days=i)
        if c.weekday() in targets: return c
    return from_date + timedelta(days=1)

def build_content_plan(trends, profile, posts_per_week=5, start_date=None):
    if start_date is None: start_date = datetime.now()
    platforms = profile.get("platforms", ["LinkedIn"]) or ["LinkedIn"]
    top = sorted(trends, key=lambda t: t.get("posts_count",0), reverse=True)[:posts_per_week]
    plan, current = [], start_date
    for i, trend in enumerate(top):
        platform = platforms[i % len(platforms)]
        rules = PLATFORM_RULES.get(platform, PLATFORM_RULES["LinkedIn"])
        pub_date = _next_best_day(current, rules["best_days"])
        pub_time = random.choice(rules["best_times"])
        current = pub_date
        trend_type = _detect_type(trend.get("keywords",[]))
        fmt_pool = FORMAT_BY_TREND.get(trend_type, FORMAT_BY_TREND["default"])
        available = [f for f in fmt_pool if f in rules["formats"]] or fmt_pool
        fmt = available[i % len(available)]
        kw = trend.get("keywords",[])[:2]
        idea = (f"{fmt.capitalize()}: как {profile.get('profession','специалист')} "
                f"использует {', '.join(kw)} для «{profile.get('goal','роста')}»")
        plan.append({"slot_id":f"slot_{i+1}","date":pub_date.strftime("%Y-%m-%d"),
                     "time":pub_time,"platform":platform,"format":fmt,
                     "trend":trend,"post_idea":idea,"status":"planned"})
    return plan

def load_and_plan():
    profile_path = DATA_DIR / "user_profile_export.json"
    trends_path  = DATA_DIR / "trends_export.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"Профиль не найден: {profile_path}\nСначала запусти Агент 1.")
    if not trends_path.exists():
        raise FileNotFoundError(f"Тренды не найдены: {trends_path}\nСначала запусти Агент 1.")
    with open(profile_path, encoding="utf-8") as f: profile = json.load(f)
    with open(trends_path,  encoding="utf-8") as f: td = json.load(f)
    trends = td.get("trends", [])
    if not trends: raise ValueError("Трендов нет — запусти Агент 1.")
    plan = build_content_plan(trends, profile)
    out = DATA_DIR / "content_plan.json"
    with open(out, "w", encoding="utf-8") as f: json.dump(plan, f, ensure_ascii=False, indent=2)
    print(f"  ✅ Контент-план сохранён: {out}")
    return {"plan": plan, "profile": profile, "trends": trends}
