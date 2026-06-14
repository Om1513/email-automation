"""
Email construction and personalization.

Responsibilities:
  * Extract a first name from a full name.
  * Substitute personalization tokens into the subject/body.
  * Build a MIME message with the resume PDF attached.
  * Encode the message into the base64url form the Gmail API expects.

This module performs no network I/O, which keeps it trivially unit-testable.
"""

from __future__ import annotations

import base64
import os
from email.message import EmailMessage
from typing import Dict

from . import config


def extract_first_name(full_name: str) -> str:
    """Return the first token of a full name.

    "Jane Smith" -> "Jane", "Rahul Mehta" -> "Rahul". Falls back to the whole
    (trimmed) string if there is no whitespace.
    """
    if not full_name:
        return ""
    return full_name.strip().split()[0]


def personalize(text: str, first_name: str, company: str, linkedin_url: str) -> str:
    """Replace all personalization placeholders in ``text``.

    Uses str.replace (not str.format) so unexpected braces in data are safe.
    """
    return (
        text.replace(config.PLACEHOLDER_FIRST_NAME, first_name)
        .replace(config.PLACEHOLDER_COMPANY, company)
        .replace(config.PLACEHOLDER_LINKEDIN, linkedin_url)
    )


def build_personalized_content(
    contact: Dict[str, str], linkedin_url: str
) -> Dict[str, str]:
    """Return ``{first_name, subject, body}`` for a single contact."""
    first_name = extract_first_name(contact["name"])
    subject = personalize(config.SUBJECT, first_name, contact["company"], linkedin_url)
    body = personalize(
        config.BODY_TEMPLATE, first_name, contact["company"], linkedin_url
    )
    return {"first_name": first_name, "subject": subject, "body": body}


def build_mime_message(
    *,
    sender: str,
    to: str,
    subject: str,
    body: str,
    resume_path: str,
) -> EmailMessage:
    """Build a MIME message with the resume PDF attached."""
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with open(resume_path, "rb") as fh:
        data = fh.read()

    filename = os.path.basename(resume_path)
    msg.add_attachment(
        data,
        maintype="application",
        subtype="pdf",
        filename=filename,
    )
    return msg


def encode_message(msg: EmailMessage) -> Dict[str, str]:
    """Encode a MIME message into the Gmail API draft/message body shape.

    Returns ``{"raw": "<base64url>"}``.
    """
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    return {"raw": raw}
