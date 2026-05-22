"""
agent2/platforms/adapter.py
Адаптирует пост под требования платформы: лимиты, хэштеги, форматирование.
"""
import re

LIMITS = {"LinkedIn":3000,"Telegram":4096,"Instagram":2200}

def _truncate(text, max_chars):
    if len(text) <= max_chars: return text
    t = text[:max_chars-3]
    ls = t.rfind(" ")
    if ls > max_chars * 0.8: t = t[:ls]
    return t + "..."

def _linkedin(text):
    text = re.sub(r"\n{3,}", "\n\n", text)
    return _truncate(text, LIMITS["LinkedIn"])

def _telegram(text):
    text = re.sub(r"\n{3,}", "\n\n", text)
    return _truncate(text, LIMITS["Telegram"])

def _instagram(text):
    hashtags = re.findall(r"#\w+", text)
    clean    = re.sub(r"(#\w+\s?)+", "", text).strip()
    if hashtags: clean += "\n\n" + " ".join(hashtags)
    return _truncate(clean, LIMITS["Instagram"])

FORMATTERS = {"LinkedIn":_linkedin,"Telegram":_telegram,"Instagram":_instagram}

def adapt_for_platform(text, platform):
    return FORMATTERS.get(platform, _linkedin)(text)

def get_post_stats(text, platform):
    limit = LIMITS.get(platform, 3000)
    chars = len(text)
    return {"chars":chars,"limit":limit,"used_pct":round(chars/limit*100,1),
            "hashtags":len(re.findall(r"#\w+",text)),"fits":chars<=limit}
