"""
core/google_photos.py

Google Photos Library API v1 wrapper.
Uses direct REST calls (the API is not in google-api-python-client's discovery).
"""

import asyncio
import logging
import requests

log = logging.getLogger(__name__)
PHOTOS_BASE = "https://photoslibrary.googleapis.com/v1"


def _headers():
    from cloud_auth.google_auth import load_credentials
    from google.auth.transport.requests import Request

    creds = load_credentials()
    if not creds:
        raise RuntimeError("Not connected to Google. Please connect first.")
    if creds.expired:
        creds.refresh(Request())
    return {"Authorization": f"Bearer {creds.token}"}


# ── List ──────────────────────────────────────────────────────────────────────

async def list_media_items(page_size: int = 50, page_token: str = None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _list_sync, page_size, page_token)


def _list_sync(page_size, page_token):
    params = {"pageSize": page_size}
    if page_token:
        params["pageToken"] = page_token
    resp = requests.get(f"{PHOTOS_BASE}/mediaItems", headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── Download original ────────────────────────────────────────────────────────

async def download_media(base_url: str, dest_path: str, is_video: bool = False):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download_sync, base_url, dest_path, is_video)


def _download_sync(base_url, dest_path, is_video):
    suffix = "=dv" if is_video else "=d"
    resp = requests.get(f"{base_url}{suffix}", stream=True, timeout=60)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
    return True


# ── Download thumbnail ───────────────────────────────────────────────────────

async def download_thumbnail(base_url: str, dest_path: str, size: int = 200):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _thumb_sync, base_url, dest_path, size)


def _thumb_sync(base_url, dest_path, size):
    url = f"{base_url}=w{size}-h{size}-c"
    resp = requests.get(url, stream=True, timeout=15)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
    return True
