from __future__ import annotations

import json
from typing import Any

from app.services.analyzer_adapter import analyzer_adapter


class ContentPlannerAdapter:
    def __init__(self) -> None:
        self.base = analyzer_adapter

    def build_content_plan(self, trends: list[dict[str, Any]], profile: dict[str, Any], posts_per_week: int = 5) -> list[dict[str, Any]]:
        from agent2.planner.content_planner import build_content_plan

        return build_content_plan(self._normalize_trends(trends), self._legacy_profile(profile), posts_per_week=posts_per_week)

    def _normalize_trends(self, trends: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for trend in trends:
            item = dict(trend)
            keywords = item.get("keywords") or []
            if isinstance(keywords, str):
                try:
                    keywords = json.loads(keywords)
                except Exception:
                    keywords = [keywords]
            item["keywords"] = keywords
            normalized.append(item)
        return normalized

    def _legacy_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": profile.get("name"),
            "niche": profile.get("niche") or "общее",
            "profession": profile.get("profession") or "специалист",
            "goal": profile.get("goal") or "рост",
            "tone": profile.get("tone") or "экспертный",
            "audience": profile.get("audience") or "профессионалы",
            "values": profile.get("user_values") or [],
            "platforms": profile.get("platforms") or ["LinkedIn"],
            "analytics_feedback": profile.get("analytics_feedback") or {},
        }


content_planner_adapter = ContentPlannerAdapter()
