from __future__ import annotations

from typing import Any

from app.services.analyzer_adapter import analyzer_adapter
from app.services.content_planner_adapter import content_planner_adapter
from app.services.post_generator_adapter import post_generator_adapter


class SocialAnalyzerAdapter:
    """Compatibility facade over focused adapters for the original agents."""

    def available(self) -> bool:
        return analyzer_adapter.available()

    def onboarding_questions(self) -> list[dict[str, Any]]:
        return analyzer_adapter.onboarding_questions()

    def normalize_profile_answers(self, user_id: str, answers: dict[str, Any]) -> dict[str, Any]:
        return analyzer_adapter.normalize_profile_answers(user_id, answers)

    def build_content_plan(self, trends: list[dict[str, Any]], profile: dict[str, Any], posts_per_week: int = 5) -> list[dict[str, Any]]:
        return content_planner_adapter.build_content_plan(trends, profile, posts_per_week=posts_per_week)

    def generate_post(self, slot: dict[str, Any], profile: dict[str, Any], use_llm: bool = False) -> dict[str, Any]:
        return post_generator_adapter.generate_post(slot, profile, use_llm=use_llm)

    def run_legacy_parsers(self, niche: str, sources: list[str]) -> list[dict[str, Any]]:
        """Run original social_analyzer parsers for compatibility endpoints."""
        posts: list[dict[str, Any]] = []
        if "rss" in sources:
            from parsers.rss_parser import parse_rss

            posts.extend(parse_rss(niche=niche, max_per_feed=20))
        if "ddg" in sources:
            from parsers.ddg_parser import parse_ddg

            posts.extend(parse_ddg(niche=niche, max_results=20))
        if "reddit" in sources:
            from parsers.reddit_parser import parse_reddit

            posts.extend(parse_reddit(niche=niche, max_posts=40))
        return posts


adapter = SocialAnalyzerAdapter()
