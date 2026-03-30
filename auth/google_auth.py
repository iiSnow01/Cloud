"""
auth/google_auth.py

Handles Google OAuth2 authentication.
One credentials.json covers Gmail + Google Photos (different scopes, same flow).

To set up:
  1. Go to https://console.cloud.google.com
  2. Create a project → Enable "Gmail API" and "Photos Library API"
  3. OAuth consent screen → External → add your email as test user
  4. Credentials → Create OAuth 2.0 Client ID → Desktop app
  5. Download JSON → save as  google_credentials.json  next to main.py
"""

import os
import asyncio
import logging

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/photoslibrary.readonly",
    "https://mail.google.com/",
]

CREDENTIALS_PATH = "google_credentials.json"
TOKEN_PATH = "google_token.json"


def load_credentials():
    """Return valid Credentials or None (silently refreshes if expired)."""
    if not os.path.exists(TOKEN_PATH):
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_token(creds)
            return creds
    except Exception as e:
        log.warning("load_credentials failed: %s", e)
    return None


def is_google_connected() -> bool:
    creds = load_credentials()
    return creds is not None and creds.valid


def _save_token(creds):
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())


def disconnect_google():
    if os.path.exists(TOKEN_PATH):
        os.remove(TOKEN_PATH)
        log.info("Google token removed.")


async def connect_google_async():
    """
    Run the browser OAuth flow in a thread so the Qt event loop isn't blocked.
    Raises FileNotFoundError if google_credentials.json is missing.
    """
    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"'{CREDENTIALS_PATH}' not found in the app folder.\n\n"
            "Steps to fix:\n"
            "  1. Go to console.cloud.google.com\n"
            "  2. Create a project → Enable Gmail API + Photos Library API\n"
            "  3. OAuth consent screen → External → add your email as test user\n"
            "  4. Credentials → Create OAuth 2.0 Client ID → Desktop app\n"
            "  5. Download JSON → rename to  google_credentials.json\n"
            "  6. Place it next to main.py and try again."
        )
    loop = asyncio.get_event_loop()
    creds = await loop.run_in_executor(None, _run_oauth_flow)
    return creds


def _run_oauth_flow():
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    log.info("Google OAuth complete — token saved.")
    return creds
