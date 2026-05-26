from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from app.core.config import settings


class AnalyzerAdapter:
    def __init__(self) -> None:
        self.root = Path(settings.social_analyzer_path).resolve()
        if self.root.exists() and str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))

    def available(self) -> bool:
        return self.root.exists()

    def onboarding_questions(self) -> list[dict[str, Any]]:
        try:
            from onboarding.dialog import QUESTIONS

            return QUESTIONS
        except Exception:
            return [
                {"key": "name", "text": "Как тебя зовут?"},
                {"key": "profession", "text": "Кем ты работаешь?"},
                {"key": "niche", "text": "Какая у тебя ниша?", "choices": ["IT", "маркетинг", "финансы", "карьера", "общее"]},
                {"key": "goal", "text": "Главная цель личного бренда?"},
                {"key": "audience", "text": "Кто твоя целевая аудитория?"},
                {"key": "tone", "text": "Какой тон общения?", "choices": ["экспертный", "дружелюбный", "провокационный"]},
                {"key": "values", "text": "Какие ценности важно транслировать?"},
                {"key": "avoid", "text": "Что не публиковать?"},
                {"key": "platforms", "text": "Где публиковаться?"},
            ]

    def normalize_profile_answers(self, user_id: str, answers: dict[str, Any]) -> dict[str, Any]:
        answers = {key: value.strip() if isinstance(value, str) else value for key, value in answers.items()}
        values = answers.get("values", [])
        platforms = answers.get("platforms", [])
        if isinstance(values, str):
            values = [item.strip() for item in values.split(",") if item.strip()]
        if isinstance(platforms, str):
            platforms = [item.strip() for item in platforms.split(",") if item.strip()]
        return {
            "user_id": user_id,
            "name": answers.get("name"),
            "niche": answers.get("niche"),
            "profession": answers.get("profession"),
            "goal": answers.get("goal"),
            "tone": answers.get("tone"),
            "audience": answers.get("audience"),
            "avoid": answers.get("avoid"),
            "user_values": values,
            "platforms": platforms,
            "raw_answers": answers,
        }


analyzer_adapter = AnalyzerAdapter()
