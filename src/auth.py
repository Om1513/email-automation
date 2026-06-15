"""
OAuth 2.0 authentication against the Gmail API.

Flow:
  1. If ``token.json`` exists and is valid, use it.
  2. If it is expired but has a refresh token, refresh silently.
  3. Otherwise run the installed-app (desktop) consent flow using
     ``credentials.json`` and persist the resulting token to ``token.json``.

The returned service is also verified against ``config.EXPECTED_SENDER`` so we
never operate on the wrong mailbox.
"""

from __future__ import annotations

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from . import config
from .logger import get_logger

log = get_logger("auth")


class AuthError(Exception):
    """Raised when authentication cannot be completed."""


def _load_credentials(token_file: str) -> Credentials:
    """Obtain valid OAuth credentials, running the consent flow if needed."""
    creds: Credentials | None = None
    token_name = os.path.basename(token_file)

    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, config.SCOPES)
            log.debug("Loaded existing token from %s", token_name)
        except Exception as exc:  # corrupt/incompatible token file
            log.warning("Could not load %s (%s); re-authenticating.", token_name, exc)
            creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            log.info("Access token expired; refreshing silently.")
            creds.refresh(Request())
            _save_token(creds, token_file)
            return creds
        except Exception as exc:
            log.warning("Token refresh failed (%s); falling back to consent flow.", exc)

    # Full consent flow.
    if not os.path.exists(config.CREDENTIALS_FILE):
        raise AuthError(
            "credentials.json not found in the project root. Download your "
            "Desktop OAuth client from Google Cloud Console and place it at "
            f"{config.CREDENTIALS_FILE}"
        )

    log.info("Starting OAuth consent flow (a browser window will open).")
    flow = InstalledAppFlow.from_client_secrets_file(
        config.CREDENTIALS_FILE, config.SCOPES
    )
    creds = flow.run_local_server(port=0)
    _save_token(creds, token_file)
    return creds


def _save_token(creds: Credentials, token_file: str) -> None:
    """Persist credentials to the token file (never logged)."""
    with open(token_file, "w", encoding="utf-8") as fh:
        fh.write(creds.to_json())
    # Tighten permissions where the OS supports it.
    try:
        os.chmod(token_file, 0o600)
    except OSError:
        pass
    log.debug("Saved OAuth token to %s", os.path.basename(token_file))


def get_gmail_service(
    expected_sender: str = config.EXPECTED_SENDER, token_file: str | None = None
):
    """Authenticate and return a verified Gmail API service object.

    ``token_file`` defaults to the token file for ``expected_sender`` so each
    account's credentials are stored separately. Raises ``AuthError`` if the
    authenticated account does not match ``expected_sender``.
    """
    if token_file is None:
        token_file = config.token_file_for(expected_sender)
    creds = _load_credentials(token_file)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    try:
        profile = service.users().getProfile(userId="me").execute()
    except Exception as exc:
        raise AuthError(f"Failed to read Gmail profile: {exc}") from exc

    authenticated = (profile.get("emailAddress") or "").lower()
    if authenticated != expected_sender.lower():
        raise AuthError(
            "Authenticated Gmail account does not match the expected sender.\n"
            f"  expected: {expected_sender}\n"
            f"  actual:   {authenticated or '(unknown)'}\n"
            "Delete token.json and re-authenticate with the correct account."
        )

    log.info("Authenticated as %s", authenticated)
    return service
