from __future__ import annotations

import random
import re
from difflib import SequenceMatcher
from typing import Any

from app.services.analyzer_adapter import analyzer_adapter
from app.services.llm.base import LLMUnavailable
from app.services.llm.factory import generate_text_with_fallback


INVALID_OUTPUT_PHRASES = [
    "json data",
    "provided json",
    "i've analyzed",
    "i have analyzed",
    "overall structure",
    "key findings",
    "article highlights",
    "potential use cases",
    "potential uses",
    "important considerations",
    "this json represents",
    "the data represents",
    "key fields",
    "further considerations",
    "if you'd like",
    "this data could",
    "this topic could be used",
    "for a python developer, this is a strong content angle",
]

REGENERATION_MODES = {
    "create",
    "regenerate_full",
    "improve_current",
    "change_tone",
    "shorter",
    "more_expert",
    "more_human",
    "stronger_hook",
}


def normalize_generation_mode(mode: str | None) -> str:
    value = (mode or "create").strip().lower()
    return value if value in REGENERATION_MODES else "regenerate_full"


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip()) or default
    return str(value).strip() or default


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,;\n]", value) if item.strip()]
    return []


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text or ""))


def _looks_mojibake(text: str | None) -> bool:
    value = str(text or "")
    if not value:
        return True
    suspicious = len(re.findall(r"[РСÐÑ�]", value))
    return suspicious >= 8 and suspicious / max(len(value), 1) > 0.04


def looks_like_json_analysis(text: str | None) -> bool:
    value = str(text or "").strip()
    if not value:
        return True
    lower = value.lower()
    return _looks_mojibake(value) or any(phrase in lower for phrase in INVALID_OUTPUT_PHRASES)


def _too_similar(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    if min(len(left), len(right)) < 120:
        return False
    return SequenceMatcher(None, left.strip().lower(), right.strip().lower()).ratio() > 0.86


def _clean_keywords(value: Any) -> list[str]:
    keywords = _list(value)
    cleaned: list[str] = []
    for item in keywords:
        item = re.sub(r"[\[\]{}\"]", "", item)
        item = re.sub(r"\s+", " ", item).strip(" ,.;:-")
        lower = item.lower()
        if item and lower not in {word.lower() for word in cleaned}:
            cleaned.append(item)
    return cleaned[:6]


def _brief(slot: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    trend = slot.get("trend") or {}
    platforms = _list(profile.get("platforms"))
    platform = _text(slot.get("platform"), platforms[0] if platforms else "LinkedIn")
    topic = _text(trend.get("topic") or slot.get("post_idea"), "Professional insight")
    summary = _text(trend.get("summary"), "")
    keywords = _clean_keywords(trend.get("keywords"))
    personality = profile.get("personality_brief") or slot.get("personality_brief") or {}
    personality = personality if isinstance(personality, dict) else {}
    avoid_phrases = [*_list(profile.get("avoid")), *_list(personality.get("avoid_phrases"))]
    avoid_phrases = list(dict.fromkeys(item for item in avoid_phrases if item))
    return {
        "name": _text(profile.get("name"), ""),
        "niche": _text(profile.get("niche"), "IT"),
        "profession": _text(profile.get("profession"), "specialist"),
        "goal": _text(profile.get("goal"), "grow a professional profile"),
        "audience": _text(profile.get("audience"), "professional audience"),
        "tone": _text(profile.get("tone"), "expert but human"),
        "values": _list(profile.get("user_values") or profile.get("values")),
        "avoid": _text(profile.get("avoid"), ""),
        "platform": platform,
        "format": _text(slot.get("format"), "post"),
        "topic": topic,
        "summary": summary,
        "relevance_reason": _text(trend.get("relevance_reason"), ""),
        "keywords": keywords,
        "analytics_feedback": profile.get("analytics_feedback") or slot.get("analytics_feedback") or {},
        "personality_brief": personality,
        "avoid_phrases": avoid_phrases,
    }


def _ru(brief: dict[str, Any]) -> bool:
    joined = " ".join(_text(brief.get(key)) for key in ("profession", "goal", "audience", "tone", "topic", "summary"))
    return _has_cyrillic(joined)


def build_structured_draft(slot: dict[str, Any], profile: dict[str, Any], mode: str = "create", current_text: str | None = None) -> str:
    brief = _brief(slot, profile)
    personality = brief.get("personality_brief") or {}
    preferred_structure = _list(personality.get("preferred_structure"))
    voice = _text(personality.get("voice"), brief["tone"])
    writing_style = _text(personality.get("writing_style"), "")
    if _ru(brief):
        return "\n".join(
            [
                "Рабочий черновик",
                f"Тема: {brief['topic']}",
                f"Аудитория: {brief['audience']}",
                f"Цель: {brief['goal']}",
                f"Стиль автора: {voice}",
                f"Подача: {writing_style or 'короткие абзацы, практическая польза, понятный вывод'}",
                f"Предпочтительная структура: {', '.join(preferred_structure) if preferred_structure else 'hook, insight, example, CTA'}",
                f"Угол подачи: показать практическую пользу темы для клиентов и экспертность {brief['profession']}.",
                f"Ключевая мысль: {brief['summary'] or 'тему нужно связать с реальной задачей аудитории.'}",
                "Хук: начать с проблемы, которую узнает аудитория.",
                "CTA: задать вопрос или предложить начать с одной измеримой задачи.",
            ]
        )
    return "\n".join(
        [
            "Working draft",
            f"Topic: {brief['topic']}",
            f"Audience: {brief['audience']}",
            f"Goal: {brief['goal']}",
            f"Author voice: {voice}",
            f"Writing style: {writing_style or 'short paragraphs, practical value, clear takeaway'}",
            f"Preferred structure: {', '.join(preferred_structure) if preferred_structure else 'hook, insight, example, CTA'}",
            f"Angle: connect the trend to practical client value and {brief['profession']} expertise.",
            f"Key insight: {brief['summary'] or 'connect the topic to a real audience problem.'}",
            "Hook: start with a recognizable problem.",
            "CTA: ask a useful question or suggest one measurable next step.",
        ]
    )


def _hashtags(brief: dict[str, Any]) -> str:
    words = []
    for item in [brief.get("profession"), brief.get("niche"), *(brief.get("keywords") or [])]:
        normalized = re.sub(r"[^A-Za-zА-Яа-я0-9]+", "", _text(item))
        if normalized and len(normalized) <= 28 and normalized.lower() not in {word.lower() for word in words}:
            words.append(normalized)
    if not words:
        words = ["personalbrand", "content"]
    return " ".join(f"#{word}" for word in words[:4])


def build_fallback_social_post(
    slot: dict[str, Any],
    profile: dict[str, Any],
    mode: str = "create",
    current_text: str | None = None,
) -> str:
    brief = _brief(slot, profile)
    mode = normalize_generation_mode(mode)
    platform = _text(brief.get("platform"), "LinkedIn").lower()
    topic = _text(brief.get("topic"), "этой теме" if _ru(brief) else "this topic")
    summary = _text(brief.get("summary"))
    profession = _text(brief.get("profession"), "специалиста" if _ru(brief) else "specialist")
    goal = _text(brief.get("goal"), "развивать профиль" if _ru(brief) else "grow a professional profile")
    audience = _text(brief.get("audience"), "аудитории" if _ru(brief) else "the audience")
    personality = brief.get("personality_brief") or {}
    preferred_structure = [item.lower() for item in _list(personality.get("preferred_structure"))]
    voice = _text(personality.get("voice"), brief.get("tone"))
    case_or_example = any(
        marker in " ".join(preferred_structure)
        for marker in ["case", "кейс", "example", "пример", "practical"]
    )
    friendly = any(marker in voice.lower() for marker in ["дружелюб", "тепл", "friendly", "warm"])

    ru = _ru(brief)
    angle_ru = random.choice(
        [
            "через практическую пользу для бизнеса",
            "через ошибку, которую легко узнать",
            "через понятный первый шаг",
            "через экспертный разбор без лишней теории",
        ]
    )
    angle_en = random.choice(
        [
            "through practical business value",
            "through a mistake the audience recognizes",
            "through one clear first step",
            "through an expert explanation without extra theory",
        ]
    )

    if ru:
        if mode == "shorter" or platform == "telegram":
            example_line = (
                "Добавьте короткий пример из практики: какая задача была, что изменили и какой результат получили."
                if case_or_example
                else "Начните с одного процесса, одного результата и одного понятного примера."
            )
            return (
                f"{topic}: важна не сама технология, а то, какую задачу она решает.\n\n"
                f"{summary or 'По найденным материалам видно, что тема становится заметнее для профессиональной аудитории.'}\n\n"
                f"Практическая ценность здесь в том, что экспертность {profession} можно показать через понятный результат, а не через абстрактную теорию. Цель: {goal}.\n\n"
                f"{example_line}"
            )
        if mode == "more_human":
            return (
                f"Я всё чаще замечаю одну вещь вокруг темы «{topic}»: людям не нужна ещё одна сложная теория.\n\n"
                f"Им нужно понять, как это помогает решить конкретную задачу. {summary or ''}\n\n"
                f"Как {profession}, я бы объяснял это через простой пример из практики: что было сложно, что изменили, какой результат получили.\n\n"
                f"Такой контент помогает не просто рассказывать о себе, а вызывать доверие у {audience}.\n\n"
                "А вы чаще доверяете экспертам после теории или после понятного кейса?"
            ).strip()
        if mode == "more_expert":
            return (
                f"{topic} становится сильной темой для экспертного контента.\n\n"
                f"Главный вопрос не в том, насколько тема модная. Важно, как она влияет на реальные процессы: скорость, стоимость, качество решений и понятность результата.\n\n"
                f"{summary or 'По найденным материалам видно, что вокруг темы растёт практический интерес.'}\n\n"
                f"Здесь хорошо видно мышление {profession}: где есть риск, где польза, и как связать технологию с бизнес-задачей клиента.\n\n"
                f"Если ваша цель - {goal}, такой пост лучше строить вокруг конкретного вывода, а не вокруг пересказа новости.\n\n"
                f"{_hashtags(brief)}"
            )
        if mode == "stronger_hook":
            hook = f"Многие обсуждают «{topic}», но почти никто не говорит о главном."
        elif mode == "improve_current" and current_text and not looks_like_json_analysis(current_text):
            hook = "Я бы усилил этот пост так: меньше общих слов, больше практической пользы."
        else:
            hook = f"{topic} - это не просто тренд, а повод показать реальную экспертизу."
        if friendly and mode not in {"more_expert", "stronger_hook"}:
            hook = f"Давайте простыми словами: {hook}"
        return (
            f"{hook}\n\n"
            f"{summary or 'По найденным материалам видно, что тема набирает внимание у профессиональной аудитории.'}\n\n"
            f"Сильный угол подачи для эксперта - {angle_ru}: объяснить, какую проблему это решает, где есть ограничения и какой первый шаг можно сделать без хаоса.\n\n"
            f"Если цель - {goal}, такой пост должен не пересказывать новость, а показывать вашу логику: как вы думаете, выбираете решения и помогаете {audience} получить результат.\n\n"
            "С чего бы вы начали внедрение такой идеи в реальный процесс?"
        )

    if mode == "shorter" or platform == "telegram":
        example_line = (
            "Add one practical example: the starting problem, the change, and the result."
            if case_or_example
            else "Start with one process, one measurable result, and one clear next step."
        )
        return (
            f"{topic} matters when it solves a concrete problem.\n\n"
            f"{summary or 'The materials show growing practical interest around this topic.'}\n\n"
            f"The useful angle is simple: connect the idea to outcomes your audience can understand, and show how {profession} expertise turns it into practice.\n\n"
            f"{example_line}"
        )
    if mode == "more_human":
        return (
            f"I keep seeing the same thing around {topic}: people do not need another abstract explanation.\n\n"
            f"They need to understand what changes in real work. {summary or ''}\n\n"
            f"As a {profession}, I would turn this into a practical story: what was difficult, what changed, and what result became easier to achieve.\n\n"
            "That is the kind of content that builds trust, not just visibility.\n\n"
            "What makes you trust an expert faster: theory or a clear example?"
        ).strip()
    if mode == "more_expert":
        return (
            f"{topic} is becoming a useful expert-content theme.\n\n"
            "The point is not whether the topic is fashionable. The point is how it affects real systems: reliability, cost, speed, quality, and business workflow integration.\n\n"
            f"{summary or 'The collected sources show practical interest around this topic.'}\n\n"
            f"This is a chance to show judgment: where the risk is, where the value is, and how {profession} expertise turns a trend into a working solution.\n\n"
            f"If the goal is to {goal}, the post should focus on a concrete insight instead of repeating the news.\n\n"
            f"{_hashtags(brief)}"
        )
    hook = (
        f"Many people talk about {topic}, but the useful question is different."
        if mode == "stronger_hook"
        else f"{topic} is not just a trend. It is a chance to show practical expertise."
    )
    if friendly and mode not in {"more_expert", "stronger_hook"}:
        hook = f"Let’s keep it simple: {hook}"
    return (
        f"{hook}\n\n"
        f"{summary or 'The sources show growing attention from professional audiences.'}\n\n"
        f"The strongest angle is {angle_en}: explain what problem this solves, where the limits are, and what first step makes sense. That is where {profession} expertise becomes visible.\n\n"
        f"If your goal is to {goal}, this kind of post should not simply report the trend. It should show how you think, how you choose tools, and how you help {audience} get a result.\n\n"
        "Where would you start if you had to apply this in a real workflow?"
    )


def _system_prompt() -> str:
    return (
        "You are writing a social media post for the end user.\n"
        "The provided trend/profile data is internal context only.\n"
        "Do not explain the JSON.\n"
        "Do not analyze the input data.\n"
        "Do not describe fields, structure, or potential uses of the data.\n"
        "Do not mention backend metadata, schemas, IDs, or data structures.\n"
        "Combine the selected platform style with the user's personality brief.\n"
        "Use style examples only as writing-pattern guidance; do not copy them.\n"
        "Write only the final social media post for the selected platform."
    )


def _mode_instruction(mode: str) -> str:
    return {
        "regenerate_full": "Create a meaningfully new angle/version. Do not merely swap words.",
        "improve_current": "Improve the current final text while preserving the core idea.",
        "change_tone": "Rewrite with the requested tone while keeping the idea.",
        "shorter": "Make the post shorter and more direct.",
        "more_expert": "Make the post more expert, concrete, and credible.",
        "more_human": "Make the post warmer, more personal, and less corporate.",
        "stronger_hook": "Create a stronger opening hook and keep the rest concise.",
        "create": "Create a ready-to-publish social media post.",
    }.get(mode, "Create a ready-to-publish social media post.")


def _llm_prompt(
    slot: dict[str, Any],
    profile: dict[str, Any],
    draft_text: str,
    mode: str,
    current_text: str | None,
    stricter: bool = False,
) -> str:
    brief = _brief(slot, profile)
    personality = brief.get("personality_brief") or {}
    preferred_structure = _list(personality.get("preferred_structure"))
    vocabulary_preferences = _list(personality.get("vocabulary_preferences"))
    avoid_phrases = _list(personality.get("avoid_phrases") or brief.get("avoid_phrases"))
    examples = personality.get("examples") if isinstance(personality.get("examples"), list) else []
    lines = [
        "Internal content brief:",
        f"- Platform: {brief['platform']}",
        f"- Format: {brief['format']}",
        f"- Profession: {brief['profession']}",
        f"- Goal: {brief['goal']}",
        f"- Audience: {brief['audience']}",
        f"- Tone: {brief['tone']}",
        f"- Topic: {brief['topic']}",
        f"- Trend summary: {brief['summary'] or 'Limited source summary available.'}",
        f"- Relevance reason: {brief['relevance_reason'] or 'Use only if it helps the post.'}",
        f"- Keywords: {', '.join(brief['keywords']) or 'none'}",
        f"- Analytics guidance: {_text((brief.get('analytics_feedback') or {}).get('guidance'), 'none')}",
        f"- Personality voice: {_text(personality.get('voice'), brief['tone'])}",
        f"- Writing style: {_text(personality.get('writing_style'), 'short paragraphs, practical insight, clear CTA')}",
        f"- Preferred structure: {', '.join(preferred_structure) if preferred_structure else 'hook, insight, example, CTA'}",
        f"- Vocabulary preferences: {', '.join(vocabulary_preferences) or 'none'}",
        f"- Avoid phrases/topics: {', '.join(avoid_phrases) or 'none'}",
        "",
        f"Task: {_mode_instruction(mode)}",
        "",
        "Draft / working note:",
        draft_text,
    ]
    if examples:
        lines.extend(["", "Approved/edited style examples to imitate as pattern only, not copy:"])
        for example in examples[:3]:
            lines.append(f"- [{example.get('platform') or 'post'}] {example.get('text') or ''}")
    if current_text:
        lines.extend(["", "Current final text to improve or avoid repeating:", current_text])
    if stricter:
        lines.extend(
            [
                "",
                "Strict retry rules:",
                "- Output only the post text.",
                "- No headings like Overall Structure, Key Findings, Potential Use Cases, or Important Considerations.",
                "- No explanation of the brief.",
                "- No meta sentence such as 'this could be used' or 'for a developer this is a strong content angle'.",
            ]
        )
    return "\n".join(lines)


def _legacy_template(slot: dict[str, Any], profile: dict[str, Any]) -> str:
    analyzer_adapter.available()
    try:
        from agent2.generator.template_generator import generate_from_template

        return generate_from_template(slot, profile)
    except Exception:
        return ""


def _adapt_for_platform(text: str, platform: str) -> tuple[str, dict[str, Any]]:
    analyzer_adapter.available()
    try:
        from agent2.platforms.adapter import adapt_for_platform, get_post_stats

        adapted = adapt_for_platform(text, platform)
        return adapted, get_post_stats(adapted, platform)
    except Exception:
        limit = 4096 if platform.lower() == "telegram" else 3000
        adapted = text[: limit - 3] + "..." if len(text) > limit else text
        return adapted, {"chars": len(adapted), "limit": limit, "used_pct": round(len(adapted) / limit * 100, 1), "hashtags": adapted.count("#"), "fits": len(adapted) <= limit}


class PostGeneratorAdapter:
    def _legacy_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": profile.get("name"),
            "niche": profile.get("niche") or "IT",
            "profession": profile.get("profession") or "specialist",
            "goal": profile.get("goal") or "grow professional visibility",
            "tone": profile.get("tone") or "expert but human",
            "audience": profile.get("audience") or "professional audience",
            "values": profile.get("user_values") or profile.get("values") or [],
            "platforms": profile.get("platforms") or ["LinkedIn"],
            "analytics_feedback": profile.get("analytics_feedback") or {},
        }

    async def generate_post_async(
        self,
        slot: dict[str, Any],
        profile: dict[str, Any],
        use_llm: bool = False,
        mode: str = "create",
        current_text: str | None = None,
    ) -> dict[str, Any]:
        mode = normalize_generation_mode(mode)
        legacy_profile = self._legacy_profile(profile)
        raw_draft = _legacy_template(slot, legacy_profile)
        invalid_output_detected = looks_like_json_analysis(raw_draft)
        draft_source = "agent2_template"
        if invalid_output_detected:
            draft_text = build_structured_draft(slot, profile, mode=mode, current_text=current_text)
            draft_source = "structured_brief"
        else:
            draft_text = raw_draft

        fallback_used = False
        provider = "template"
        final_text = ""
        if use_llm:
            try:
                prompt = _llm_prompt(slot, profile, draft_text, mode, current_text)
                candidate, provider = await generate_text_with_fallback(prompt, system_prompt=_system_prompt())
                if looks_like_json_analysis(candidate) or _too_similar(candidate, current_text):
                    invalid_output_detected = True
                    retry_prompt = _llm_prompt(slot, profile, draft_text, mode, current_text, stricter=True)
                    candidate, provider = await generate_text_with_fallback(retry_prompt, system_prompt=_system_prompt())
                if not looks_like_json_analysis(candidate) and not _too_similar(candidate, current_text):
                    final_text = candidate.strip()
                else:
                    invalid_output_detected = True
            except LLMUnavailable:
                fallback_used = True
            except Exception:
                fallback_used = True

        if not final_text:
            fallback_used = True
            final_text = build_fallback_social_post(slot, profile, mode=mode, current_text=current_text)
            provider = "template"

        adapted, stats = _adapt_for_platform(final_text, _text(slot.get("platform"), "LinkedIn"))
        if looks_like_json_analysis(adapted):
            invalid_output_detected = True
            fallback_used = True
            adapted, stats = _adapt_for_platform(build_fallback_social_post(slot, profile, mode=mode, current_text=current_text), _text(slot.get("platform"), "LinkedIn"))
            provider = "template"

        personality = (profile.get("personality_brief") or slot.get("personality_brief") or {})
        stats = {
            **stats,
            "generation_mode": mode,
            "draft_source": draft_source,
            "fallback_used": fallback_used,
            "invalid_output_detected": invalid_output_detected,
            "provider_used": provider,
            "personality_source": personality.get("source") if isinstance(personality, dict) else None,
            "style_examples_used": len(personality.get("examples") or []) if isinstance(personality, dict) else 0,
        }
        return {
            "draft_text": draft_text.strip(),
            "final_text": adapted.strip(),
            "llm_provider": provider,
            "stats": stats,
        }

    def generate_post(
        self,
        slot: dict[str, Any],
        profile: dict[str, Any],
        use_llm: bool = False,
        mode: str = "create",
        current_text: str | None = None,
    ) -> dict[str, Any]:
        mode = normalize_generation_mode(mode)
        legacy_profile = self._legacy_profile(profile)
        raw_draft = _legacy_template(slot, legacy_profile)
        invalid_output_detected = looks_like_json_analysis(raw_draft)
        draft_source = "agent2_template"
        if invalid_output_detected:
            draft_text = build_structured_draft(slot, profile, mode=mode, current_text=current_text)
            draft_source = "structured_brief"
        else:
            draft_text = raw_draft
        final_text = build_fallback_social_post(slot, profile, mode=mode, current_text=current_text)
        adapted, stats = _adapt_for_platform(final_text, _text(slot.get("platform"), "LinkedIn"))
        personality = (profile.get("personality_brief") or slot.get("personality_brief") or {})
        return {
            "draft_text": draft_text.strip(),
            "final_text": adapted.strip(),
            "llm_provider": "template",
            "stats": {
                **stats,
                "generation_mode": mode,
                "draft_source": draft_source,
                "fallback_used": True,
                "invalid_output_detected": invalid_output_detected,
                "provider_used": "template",
                "personality_source": personality.get("source") if isinstance(personality, dict) else None,
                "style_examples_used": len(personality.get("examples") or []) if isinstance(personality, dict) else 0,
            },
        }


post_generator_adapter = PostGeneratorAdapter()
