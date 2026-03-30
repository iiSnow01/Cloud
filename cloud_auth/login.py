import os
from telethon import TelegramClient
import logging

API_ID = 39473970
API_HASH = 'f09019994b7b065cf50c4e201b0ed649'
SESSION_NAME = 'cloudgram_session'

_client = None

def get_client():
    global _client
    if _client is None:
        print(">>> Debug: Initializing TelegramClient singleton (binding to qasync loop)...", flush=True)
        _client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    return _client

async def connect_client():
    client = get_client()
    await client.connect()
    if not await client.is_user_authorized():
        logging.warning("User is not authorized. Need phone login.")
    return client
