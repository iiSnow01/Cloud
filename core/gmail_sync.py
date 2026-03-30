"""
core/gmail_sync.py

Gmail API wrapper via google-api-python-client.
Lists messages that have attachments and lets you download them.
"""

import asyncio
import base64
import logging

log = logging.getLogger(__name__)


def _service():
    from cloud_auth.google_auth import load_credentials
    from googleapiclient.discovery import build

    creds = load_credentials()
    if not creds:
        raise RuntimeError("Not connected to Google. Please connect first.")
    return build("gmail", "v1", credentials=creds)


# ── List messages with attachments ────────────────────────────────────────────

async def list_messages_with_attachments(max_results: int = 30):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _list_sync, max_results)


def _list_sync(max_results):
    svc = _service()
    result = svc.users().messages().list(
        userId="me", q="has:attachment", maxResults=max_results
    ).execute()

    messages = result.get("messages", [])
    items = []

    for msg in messages:
        try:
            full = svc.users().messages().get(
                userId="me", id=msg["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in full.get("payload", {}).get("headers", [])}
            attachments = _walk_parts(svc, msg["id"], full["payload"])
            if attachments:
                items.append({
                    "id": msg["id"],
                    "subject": headers.get("Subject", "(no subject)"),
                    "from": headers.get("From", "Unknown"),
                    "date": headers.get("Date", ""),
                    "attachments": attachments,
                })
        except Exception as e:
            log.warning("Skipping message %s: %s", msg["id"], e)
            continue

    return items


def _walk_parts(svc, msg_id, payload):
    result = []

    def recurse(part):
        if part.get("filename"):
            result.append({
                "message_id": msg_id,
                "attachment_id": part.get("body", {}).get("attachmentId", ""),
                "filename": part["filename"],
                "mime_type": part.get("mimeType", ""),
                "size": part.get("body", {}).get("size", 0),
            })
        for sub in part.get("parts", []):
            recurse(sub)

    recurse(payload)
    return result


# ── Download an attachment ────────────────────────────────────────────────────

async def download_attachment(message_id: str, attachment_id: str, dest_path: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _dl_sync, message_id, attachment_id, dest_path)


def _dl_sync(message_id, attachment_id, dest_path):
    svc = _service()
    att = svc.users().messages().attachments().get(
        userId="me", messageId=message_id, id=attachment_id
    ).execute()
    data = base64.urlsafe_b64decode(att["data"])
    with open(dest_path, "wb") as f:
        f.write(data)
    return True
