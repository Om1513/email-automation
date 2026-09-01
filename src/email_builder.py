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
import html
import os
import re
from email.message import EmailMessage
from typing import Dict

from . import config

# Matches bare http(s) URLs so we can make them clickable in the HTML part.
_URL_RE = re.compile(r"(https?://[^\s<]+)")


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
    contact: Dict[str, str],
    linkedin_url: str,
    profile: "config.Profile | None" = None,
) -> Dict[str, str]:
    """Return ``{first_name, subject, body}`` for a single contact.

    ``profile`` selects whose subject/body template to use; it defaults to the
    profile named by ``config.DEFAULT_PROFILE``.
    """
    profile = profile or config.get_profile(config.DEFAULT_PROFILE)
    first_name = extract_first_name(contact["name"])
    subject = personalize(profile.subject, first_name, contact["company"], linkedin_url)
    body = personalize(
        profile.body_template, first_name, contact["company"], linkedin_url
    )
    return {"first_name": first_name, "subject": subject, "body": body}


def body_to_html(body: str) -> str:
    """Render the plain-text body as simple, well-formed HTML.

    Blank-line-separated blocks become ``<p>`` paragraphs (so the email client
    wraps them responsively instead of showing hard mid-sentence breaks), single
    newlines within a block become ``<br>`` (keeps the signature lines together),
    and bare URLs are made clickable.
    """
    blocks = body.strip().split("\n\n")
    html_blocks = []
    for block in blocks:
        lines = [html.escape(line) for line in block.split("\n")]
        joined = "<br>".join(lines)
        joined = _URL_RE.sub(r'<a href="\1">\1</a>', joined)
        html_blocks.append(f"<p>{joined}</p>")
    inner = "\n".join(html_blocks)
    return (
        '<!DOCTYPE html><html><body style="font-family:Arial,Helvetica,sans-serif;'
        'font-size:14px;line-height:1.5;color:#222222;">'
        f"{inner}</body></html>"
    )


def build_mime_message(
    *,
    sender: str,
    to: str,
    subject: str,
    body: str,
    resume_path: str,
) -> EmailMessage:
    """Build a multipart MIME message (plain text + HTML) with the resume PDF
    attached. Sending both alternatives means text-only clients still work while
    HTML clients render clean, flowing paragraphs."""
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)  # text/plain alternative
    msg.add_alternative(body_to_html(body), subtype="html")  # text/html alternative

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
