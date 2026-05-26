from __future__ import annotations

from typing import Any

from app.services.analyzer_adapter import analyzer_adapter


class TrendAdapter:
    def __init__(self) -> None:
        self.base = analyzer_adapter

    def available(self) -> bool:
        return self.base.available()

    def cluster_posts(self, posts: list[dict[str, Any]], n_clusters: int = 8) -> dict[int, list[dict[str, Any]]]:
        from analyzer.trend_analyzer import cluster_posts_by_topic

        normalized = [self._normalize_for_agent(post) for post in posts]
        return cluster_posts_by_topic(normalized, n_clusters=n_clusters)

    def summarize_cluster(self, posts: list[dict[str, Any]]) -> dict[str, Any]:
        from analyzer.trend_analyzer import summarize_cluster

        return summarize_cluster([self._normalize_for_agent(post) for post in posts])

    def _normalize_for_agent(self, post: dict[str, Any]) -> dict[str, Any]:
        return {
            **post,
            "title": post.get("title") or "",
            "content": post.get("content") or post.get("body") or "",
            "url": post.get("url") or post.get("href") or "",
            "score": post.get("score") or 0,
            "comments": post.get("comments") or 0,
            "published_at": post.get("published_at") or "",
        }


trend_adapter = TrendAdapter()
