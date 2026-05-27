from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.services.llm.base import LLMUnavailable
from app.services.llm.factory import generate_text_with_fallback

WORD_RE = r"A-Za-zА-Яа-яЁё0-9"


class VisualAdapter:
    def __init__(self) -> None:
        self.root = Path(settings.social_analyzer_path).resolve()
        if self.root.exists() and str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))

    def _post_for_agent(self, post: dict[str, Any]) -> dict[str, Any]:
        return {
            "trend_topic": post.get("trend_topic") or post.get("format") or post.get("platform") or "professional content",
            "draft": post.get("draft_text") or post.get("final_text") or "",
            "final_text": post.get("final_text") or post.get("draft_text") or "",
        }

    def _profile_for_agent(self, profile: dict[str, Any] | None) -> dict[str, Any]:
        profile = profile or {}
        return {
            "name": profile.get("name") or "Author",
            "profession": profile.get("profession") or profile.get("niche") or "specialist",
            "goal": profile.get("goal") or "grow audience",
            "tone": profile.get("tone") or "professional",
            "audience": profile.get("audience") or "target audience",
            "values": profile.get("user_values") or profile.get("values") or [],
            "avoid": profile.get("avoid") or "",
            "platforms": profile.get("platforms") or [post_platform(profile)],
        }

    def _template_query(self, post: dict[str, Any], profile: dict[str, Any] | None) -> str:
        raw = " ".join(
            str(value or "")
            for value in [
                post.get("trend_topic"),
                post.get("final_text"),
                post.get("format"),
                post.get("platform"),
                (profile or {}).get("profession"),
                (profile or {}).get("niche"),
            ]
        )
        words = re.findall(f"[{WORD_RE}]+", raw.lower())
        stop = {
            "the",
            "and",
            "for",
            "with",
            "this",
            "that",
            "your",
            "you",
            "post",
            "linkedin",
            "telegram",
            "как",
            "для",
            "или",
            "про",
            "что",
            "это",
        }
        useful = [word for word in words if len(word) > 3 and word not in stop][:5]
        return " ".join(useful) if useful else "professional workspace"

    def _search_query(self, post: dict[str, Any], profile: dict[str, Any] | None) -> str:
        topic = (post.get("trend_topic") or post.get("format") or "").strip()
        profession = ((profile or {}).get("profession") or (profile or {}).get("niche") or "").strip()
        platform = (post.get("platform") or "").strip()
        query = " ".join(part for part in [topic, profession, "professional editorial visual", platform] if part)
        query = re.sub(r"\s+", " ", query).strip()
        return query[:180] if query else self._template_query(post, profile)

    def _safe_error(self, error: Exception | str) -> str:
        text = str(error)
        for secret in [settings.unsplash_access_key, settings.pexels_api_key]:
            if secret:
                text = text.replace(secret, "[redacted]")
        return text[:500]

    def _template_result(self, post: dict[str, Any], profile: dict[str, Any] | None) -> dict[str, Any]:
        query = self._template_query(post, profile)
        platform = post.get("platform") or "social media"
        prompt = (
            f"Create a clean professional visual for a {platform} post about "
            f"{post.get('trend_topic') or post.get('format') or query}. "
            f"Style: modern, credible, human, suitable for {(profile or {}).get('profession') or 'an expert'}."
        )
        metadata: dict[str, Any] = {"fallback": "template"}
        if not settings.unsplash_access_key and not settings.pexels_api_key:
            metadata["provider_configured"] = False
        return {
            "asset_type": "image",
            "provider": "template",
            "status": "idea",
            "image_prompt": prompt,
            "search_query": query,
            "preview_url": None,
            "source_url": None,
            "author": None,
            "alt_text": query,
            "metadata": metadata,
        }

    def _pexels_search(self, query: str) -> dict[str, Any] | None:
        if not settings.pexels_api_key:
            return None
        response = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": query, "per_page": 5, "orientation": "landscape"},
            headers={"Authorization": settings.pexels_api_key},
            timeout=12,
        )
        response.raise_for_status()
        photos = response.json().get("photos") or []
        if not photos:
            return None
        photo = photos[0]
        src = photo.get("src") or {}
        preview_url = src.get("large") or src.get("medium") or src.get("original")
        if not preview_url:
            return None
        return {
            "asset_type": "image",
            "provider": "pexels",
            "status": "selected",
            "image_prompt": None,
            "search_query": query,
            "preview_url": preview_url,
            "source_url": photo.get("url"),
            "author": photo.get("photographer"),
            "alt_text": photo.get("alt") or query,
            "metadata": {"pexels_id": photo.get("id"), "photographer_url": photo.get("photographer_url")},
        }

    def _unsplash_search(self, query: str) -> dict[str, Any] | None:
        if not settings.unsplash_access_key:
            return None
        response = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 5, "orientation": "landscape", "content_filter": "high"},
            headers={"Authorization": f"Client-ID {settings.unsplash_access_key}", "Accept-Version": "v1"},
            timeout=12,
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        if not results:
            return None
        image = results[0]
        urls = image.get("urls") or {}
        user = image.get("user") or {}
        links = image.get("links") or {}
        preview_url = urls.get("regular") or urls.get("small") or urls.get("thumb")
        if not preview_url:
            return None
        return {
            "asset_type": "image",
            "provider": "unsplash",
            "status": "selected",
            "image_prompt": None,
            "search_query": query,
            "preview_url": preview_url,
            "source_url": links.get("html"),
            "author": user.get("name") or user.get("username"),
            "alt_text": image.get("alt_description") or image.get("description") or query,
            "metadata": {
                "unsplash_id": image.get("id"),
                "author_url": (user.get("links") or {}).get("html"),
                "provider": "unsplash_search",
            },
        }

    def _agent2_unsplash(self, post: dict[str, Any], profile: dict[str, Any] | None) -> dict[str, Any] | None:
        if not (settings.gemini_api_key and settings.unsplash_access_key and self.root.exists()):
            return None
        from agent2_beautify import find_image, get_image_query

        agent_post = self._post_for_agent(post)
        query = get_image_query(agent_post, self._profile_for_agent(profile))
        image = find_image(query)
        if not image:
            return {
                "asset_type": "image",
                "provider": "unsplash",
                "status": "idea",
                "image_prompt": None,
                "search_query": query,
                "preview_url": None,
                "source_url": None,
                "author": None,
                "alt_text": query,
                "metadata": {"source": "agent2_beautify", "image_found": False},
            }
        return {
            "asset_type": "image",
            "provider": "unsplash",
            "status": "selected",
            "image_prompt": None,
            "search_query": query,
            "preview_url": image.get("url_regular") or image.get("url_small"),
            "source_url": image.get("unsplash_link") or image.get("url_full"),
            "author": image.get("author"),
            "alt_text": image.get("alt") or query,
            "metadata": {"source": "agent2_beautify", "raw": image},
        }

    async def _llm_visual_idea(self, post: dict[str, Any], profile: dict[str, Any] | None) -> dict[str, Any] | None:
        prompt = (
            "Create one concise image prompt and one 3-5 word English image search query for this social post. "
            "Return plain text with two lines: Prompt: ... and Query: ...\n"
            f"Post: {post.get('final_text') or post.get('draft_text') or ''}\n"
            f"Topic: {post.get('trend_topic') or ''}\n"
            f"Platform: {post.get('platform') or ''}\n"
            f"Profile: {profile or {}}"
        )
        try:
            text, provider = await generate_text_with_fallback(
                prompt,
                system_prompt="You create safe, professional visual ideas for social media posts.",
            )
        except LLMUnavailable:
            return None
        image_prompt = text.strip()
        query_match = re.search(r"Query:\s*(.+)", text, flags=re.IGNORECASE)
        query = query_match.group(1).strip() if query_match else self._template_query(post, profile)
        return {
            "asset_type": "image",
            "provider": provider,
            "status": "idea",
            "image_prompt": image_prompt,
            "search_query": query,
            "preview_url": None,
            "source_url": None,
            "author": None,
            "alt_text": query,
            "metadata": {"fallback": "llm"},
        }

    async def generate_visual(self, post: dict[str, Any], profile: dict[str, Any] | None) -> dict[str, Any]:
        errors: list[str] = []
        provider = settings.visual_provider.lower().strip()
        query = self._search_query(post, profile)

        if provider == "pexels":
            try:
                pexels = self._pexels_search(query)
                if pexels:
                    return pexels
            except Exception as exc:
                errors.append(f"pexels: {self._safe_error(exc)}")

        if provider != "pexels":
            try:
                unsplash = self._unsplash_search(query)
                if unsplash:
                    return unsplash
            except Exception as exc:
                errors.append(f"unsplash: {self._safe_error(exc)}")

        try:
            agent2_result = self._agent2_unsplash(post, profile)
            if agent2_result:
                return agent2_result
        except Exception as exc:
            errors.append(f"agent2_beautify: {self._safe_error(exc)}")

        if provider != "pexels":
            try:
                pexels = self._pexels_search(query)
                if pexels:
                    return pexels
            except Exception as exc:
                errors.append(f"pexels: {self._safe_error(exc)}")

        if provider == "pexels":
            try:
                unsplash = self._unsplash_search(query)
                if unsplash:
                    return unsplash
            except Exception as exc:
                errors.append(f"unsplash: {self._safe_error(exc)}")

        llm_result = await self._llm_visual_idea(post, profile)
        if llm_result:
            if errors:
                llm_result["metadata"] = {**llm_result["metadata"], "adapter_errors": errors[:3]}
            return llm_result

        template = self._template_result(post, profile)
        if errors:
            template["metadata"] = {**template["metadata"], "adapter_errors": errors[:3]}
        return template


def post_platform(profile: dict[str, Any] | None) -> str:
    platforms = (profile or {}).get("platforms") or []
    return platforms[0] if platforms else "LinkedIn"


visual_adapter = VisualAdapter()
