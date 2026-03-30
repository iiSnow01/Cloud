import os
from telethon import TelegramClient
import logging

API_ID = 39473970
API_HASH = 'f09019994b7b065cf50c4e201b0ed649'
SESSION_NAME = 'cloudgram_session'

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

async def connect_client():
    await client.connect()
    if not await client.is_user_authorized():
        # This will need to trigger UI flow to ask for phone + code
        logging.warning("User is not authorized. Need phone login.")
    return client

def get_client():
    return client
