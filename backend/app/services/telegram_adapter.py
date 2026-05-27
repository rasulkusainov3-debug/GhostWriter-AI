from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from app.core.config import settings

TELEGRAM_CAPTION_LIMIT = 1024
TELEGRAM_MESSAGE_LIMIT = 4096


@dataclass
class TelegramPublishError(Exception):
    message: str
    transient: bool = False
    photo_failed: bool = False

    def __str__(self) -> str:
        return self.message


def sanitize_telegram_error(error: Exception | str) -> str:
    text = str(error)
    token = settings.telegram_bot_token
    if token:
        text = text.replace(token, "[redacted]")
    text = text.replace("/bot", "/bot[redacted]")
    return text[:1000]


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    suffix = "\n\n..."
    return text[: max(0, limit - len(suffix))].rstrip() + suffix


def _telegram_url(method: str) -> str:
    base = settings.telegram_api_base_url.rstrip("/")
    return f"{base}/bot{settings.telegram_bot_token}/{method}"


def _friendly_telegram_error(description: str) -> str:
    lowered = description.lower()
    if "chat not found" in lowered:
        return "Telegram destination was not found. Check the chat ID or @channel and make sure the bot was added."
    if "not enough rights" in lowered or "not an administrator" in lowered or "need administrator" in lowered:
        return "Telegram bot does not have permission to publish. Add the bot as an admin with posting rights."
    if "bot was blocked" in lowered or "bot is not a member" in lowered or "user is deactivated" in lowered:
        return "Telegram bot cannot access this chat. Add the bot to the chat/channel and allow it to post."
    if "wrong file identifier" in lowered or "failed to get http url content" in lowered:
        return "Telegram could not use the selected visual URL. The post can still be sent as text."
    return description


def _is_transient_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


def _extract_error(response: requests.Response) -> TelegramPublishError:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    description = _friendly_telegram_error(str(payload.get("description") or response.reason or "Telegram request failed"))
    return TelegramPublishError(sanitize_telegram_error(description), transient=_is_transient_status(response.status_code))


def _post_telegram(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.telegram_bot_token:
        raise TelegramPublishError("Telegram bot token is not configured", transient=False)
    try:
        response = requests.post(_telegram_url(method), json=payload, timeout=20)
    except requests.Timeout as exc:
        raise TelegramPublishError("Telegram request timed out", transient=True) from exc
    except requests.RequestException as exc:
        raise TelegramPublishError(sanitize_telegram_error(exc), transient=True) from exc
    if not response.ok:
        raise _extract_error(response)
    data = response.json()
    if not data.get("ok"):
        raise TelegramPublishError(sanitize_telegram_error(data.get("description") or "Telegram returned an error"), transient=False)
    return data


def _message_id(result: dict[str, Any]) -> str | None:
    message_id = (result.get("result") or {}).get("message_id")
    return str(message_id) if message_id is not None else None


def _normalize_t_me_url(value: str) -> str | None:
    parsed = urlparse(value.strip())
    if parsed.netloc.lower() not in {"t.me", "www.t.me"}:
        return None
    slug = parsed.path.strip("/").split("/", 1)[0].strip()
    if not slug or slug.startswith("+") or slug.lower() == "joinchat":
        raise TelegramPublishError(
            "Telegram invite links cannot be used for publishing. Use a public @channel username or numeric chat ID.",
            transient=False,
        )
    return slug if slug.startswith("@") or slug.startswith("-") else f"@{slug}"


def _target_chat(schedule: dict[str, Any]) -> str | None:
    account = schedule.get("social_account") or {}
    external_id = (account.get("external_account_id") or "").strip()
    if external_id:
        if "t.me/" in external_id:
            return _normalize_t_me_url(external_id)
        if any(char.isspace() for char in external_id):
            raise TelegramPublishError("Telegram chat ID or @channel must not contain spaces.", transient=False)
        return external_id
    account_url = (account.get("account_url") or "").strip()
    if "t.me/" in account_url:
        return _normalize_t_me_url(account_url)
    return None


def _external_post_url(chat_id: str, message_id: str | None) -> str | None:
    if not message_id or not chat_id.startswith("@"):
        return None
    return f"https://t.me/{chat_id.lstrip('@')}/{message_id}"


class TelegramAdapter:
    async def publish(self, schedule: dict[str, Any]) -> dict[str, Any]:
        chat_id = _target_chat(schedule)
        if not chat_id:
            raise TelegramPublishError("Telegram chat ID or @channel is missing", transient=False)

        payload = schedule.get("payload") or {}
        text = (payload.get("final_text") or "").strip()
        if not text:
            raise TelegramPublishError("Post text is empty", transient=False)

        asset = payload.get("selected_asset") or {}
        preview_url = (asset.get("preview_url") or "").strip()

        if settings.telegram_dry_run:
            message_id = f"dry-run-{schedule.get('id')}"
            return {
                "dry_run": True,
                "simulated": True,
                "method": "sendPhoto" if preview_url else "sendMessage",
                "message_id": message_id,
                "external_post_url": None,
                "used_photo": bool(preview_url),
                "message": "Dry-run: Telegram API was not called.",
            }

        if preview_url:
            try:
                photo_payload = {
                    "chat_id": chat_id,
                    "photo": preview_url,
                    "caption": _truncate(text, TELEGRAM_CAPTION_LIMIT),
                }
                data = await asyncio.to_thread(_post_telegram, "sendPhoto", photo_payload)
                message_id = _message_id(data)
                return {
                    "dry_run": False,
                    "simulated": False,
                    "method": "sendPhoto",
                    "message_id": message_id,
                    "external_post_url": _external_post_url(chat_id, message_id),
                    "used_photo": True,
                }
            except TelegramPublishError as exc:
                exc.photo_failed = True

        message_payload = {"chat_id": chat_id, "text": _truncate(text, TELEGRAM_MESSAGE_LIMIT)}
        data = await asyncio.to_thread(_post_telegram, "sendMessage", message_payload)
        message_id = _message_id(data)
        return {
            "dry_run": False,
            "simulated": False,
            "method": "sendMessage",
            "message_id": message_id,
            "external_post_url": _external_post_url(chat_id, message_id),
            "used_photo": False,
        }


telegram_adapter = TelegramAdapter()
