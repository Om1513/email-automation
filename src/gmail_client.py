"""
Thin wrapper around the Gmail API surface we use.

Keeping all Google API calls behind this class means the rest of the codebase
talks in terms of "create a draft" / "send a draft" rather than raw resource
chains, and makes the API easy to mock in tests.
"""

from __future__ import annotations

from typing import Dict

from googleapiclient.errors import HttpError

from .email_builder import build_mime_message, encode_message
from .logger import get_logger

log = get_logger("gmail")


class GmailClientError(Exception):
    """Raised when a Gmail API operation fails."""


class GmailClient:
    """Wraps an authenticated Gmail API service object."""

    def __init__(self, service, sender: str):
        self._service = service
        self._sender = sender

    def create_draft(
        self, *, to: str, subject: str, body: str, resume_path: str
    ) -> Dict[str, str]:
        """Create a Gmail draft with the resume attached.

        Returns ``{"draft_id": ..., "message_id": ...}``.
        """
        mime = build_mime_message(
            sender=self._sender,
            to=to,
            subject=subject,
            body=body,
            resume_path=resume_path,
        )
        draft_body = {"message": encode_message(mime)}

        try:
            draft = (
                self._service.users()
                .drafts()
                .create(userId="me", body=draft_body)
                .execute()
            )
        except HttpError as exc:
            raise GmailClientError(f"Gmail API error creating draft: {exc}") from exc

        message = draft.get("message", {}) or {}
        result = {
            "draft_id": draft.get("id", ""),
            "message_id": message.get("id", ""),
        }
        # Note: we deliberately do not log the recipient's body content here.
        log.debug("Created draft %s (message %s)", result["draft_id"], result["message_id"])
        return result

    def delete_draft(self, draft_id: str) -> None:
        """Delete an existing draft by id. Missing drafts are ignored."""
        if not draft_id:
            return
        try:
            self._service.users().drafts().delete(userId="me", id=draft_id).execute()
            log.debug("Deleted old draft %s", draft_id)
        except HttpError as exc:
            # 404 = already gone; treat as success so --force stays idempotent.
            if getattr(exc, "status_code", None) == 404 or "404" in str(exc):
                log.debug("Old draft %s already absent.", draft_id)
                return
            raise GmailClientError(
                f"Gmail API error deleting draft {draft_id}: {exc}"
            ) from exc

    def send_draft(self, draft_id: str) -> str:
        """Send an existing draft by id. Returns the sent message id."""
        if not draft_id:
            raise GmailClientError("Cannot send draft: empty draft_id.")
        try:
            sent = (
                self._service.users()
                .drafts()
                .send(userId="me", body={"id": draft_id})
                .execute()
            )
        except HttpError as exc:
            raise GmailClientError(
                f"Gmail API error sending draft {draft_id}: {exc}"
            ) from exc

        message_id = sent.get("id", "")
        log.debug("Sent draft %s -> message %s", draft_id, message_id)
        return message_id
