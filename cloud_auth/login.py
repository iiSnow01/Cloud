import json
import logging
import os

from telethon import TelegramClient
from runtime_paths import runtime_path

SESSION_NAME = runtime_path("cloudgram_session")
__all__ = ["get_client", "connect_client", "SESSION_NAME"]
TELEGRAM_CONFIG_PATH = runtime_path("telegram_api.json")
API_ID_ENV = "CLOUDGRAM_API_ID"
API_HASH_ENV = "CLOUDGRAM_API_HASH"

_client = None


def _load_api_credentials() -> tuple[int, str]:
    api_id = os.environ.get(API_ID_ENV)
    api_hash = os.environ.get(API_HASH_ENV)

    if (not api_id or not api_hash) and os.path.exists(TELEGRAM_CONFIG_PATH):
        with open(TELEGRAM_CONFIG_PATH, "r", encoding="utf-8") as handle:
            config = json.load(handle)
        api_id = api_id or config.get("api_id")
        api_hash = api_hash or config.get("api_hash")

    if not api_id or not api_hash:
        raise RuntimeError(
            "Telegram API credentials are missing. Set CLOUDGRAM_API_ID and "
            "CLOUDGRAM_API_HASH or create telegram_api.json from "
            "telegram_api.example.json."
        )

    try:
        return int(api_id), str(api_hash)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Telegram API ID must be a number.") from exc


def get_client():
    global _client
    if _client is None:
        print(">>> Debug: Initializing TelegramClient singleton (binding to qasync loop)...", flush=True)
        api_id, api_hash = _load_api_credentials()
        _client = TelegramClient(SESSION_NAME, api_id, api_hash)
    return _client


async def connect_client():
    client = get_client()
    await client.connect()
    if not await client.is_user_authorized():
        logging.warning("User is not authorized. Need phone login.")
    return client
