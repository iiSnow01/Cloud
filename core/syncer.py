"""
core/syncer.py

Syncs the local SQLite DB from the Telegram "Saved Messages" channel.
Called on every startup so the file history is always accurate — even if
the DB was wiped or the app was reinstalled.
"""

import os
import logging
from db.local_db import init_db, upsert_file

log = logging.getLogger(__name__)


def _classify_ext(ext: str) -> str:
    ext = ext.lower()
    if ext in {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'}:
        return 'folder'
    if ext in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.heic'}:
        return 'image'
    if ext in {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv'}:
        return 'video'
    return 'document'


async def sync_from_telegram(status_callback=None):
    """
    Iterate through all messages in Saved Messages that contain a file,
    and insert/update them in the local DB.

    status_callback(str) -- optional; called with a human-readable progress string.
    """
    from cloud_auth.login import get_client

    client = get_client()
    if not client.is_connected():
        await client.connect()

    if status_callback:
        status_callback("Syncing files from Telegram…")

    count = 0
    try:
        async for message in client.iter_messages('me', limit=None):
            if not message.media:
                continue

            # Try to get document attributes first (most reliable)
            doc = getattr(message, 'document', None) or getattr(message, 'video', None)

            if doc:
                # Telethon document
                file_name = None
                for attr in getattr(doc, 'attributes', []):
                    fn = getattr(attr, 'file_name', None)
                    if fn:
                        file_name = fn
                        break
                file_size = getattr(doc, 'size', 0)
                ext = os.path.splitext(file_name or '')[1]
                file_type = _classify_ext(ext)
            elif getattr(message, 'photo', None):
                # Compressed photo
                photo = message.photo
                file_name = f"photo_{message.id}.jpg"
                file_size = getattr(photo, 'size', 0) or 0  # not always reliable
                file_type = 'image'
            else:
                continue  # other media we don't handle (polls, geo, stickers…)

            if not file_name:
                file_name = f"file_{message.id}"

            # uploaded_at from the Telegram message date
            uploaded_at = message.date.strftime("%Y-%m-%d %H:%M:%S") if message.date else None

            upsert_file(
                message_id=message.id,
                file_name=file_name,
                file_size=file_size,
                file_type=file_type,
                uploaded_at=uploaded_at,
            )
            count += 1

            if status_callback and count % 20 == 0:
                status_callback(f"Synced {count} files…")

    except Exception as e:
        log.error("sync_from_telegram error: %s", e)

    if status_callback:
        status_callback(f"Sync complete — {count} file(s) indexed.")

    log.info("sync_from_telegram: indexed %d files", count)
    return count
