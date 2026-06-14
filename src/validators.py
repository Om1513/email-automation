"""
Input validation.

Every public function raises ``ValidationError`` with a human-readable message
on failure. Callers (main.py) catch this and exit cleanly instead of dumping a
traceback at the user.
"""

from __future__ import annotations

import csv
import os
import re
from typing import Dict, List

from . import config

# A pragmatic email regex. Not RFC 5322-complete (nothing sane is) but rejects
# the obvious garbage while accepting normal addresses.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationError(Exception):
    """Raised when user-supplied input fails a validation check."""


def is_valid_email(email: str) -> bool:
    """True if ``email`` looks like a valid address."""
    return bool(_EMAIL_RE.match((email or "").strip()))


def validate_resume(path: str) -> str:
    """Validate the resume PDF path.

    Checks existence, that it is a file, the ``.pdf`` extension, and
    readability. Returns the absolute path on success.
    """
    if not path:
        raise ValidationError("No resume path provided (use --resume).")

    abs_path = os.path.abspath(os.path.expanduser(path))

    if not os.path.exists(abs_path):
        raise ValidationError(f"Resume file does not exist: {abs_path}")
    if not os.path.isfile(abs_path):
        raise ValidationError(f"Resume path is not a file: {abs_path}")
    if os.path.splitext(abs_path)[1].lower() != ".pdf":
        raise ValidationError(f"Resume must be a .pdf file: {abs_path}")
    if not os.access(abs_path, os.R_OK):
        raise ValidationError(f"Resume file is not readable: {abs_path}")

    return abs_path


def validate_linkedin_url(url: str) -> str:
    """Validate the LinkedIn URL argument (basic shape check)."""
    if not url:
        raise ValidationError("No LinkedIn URL provided (use --linkedin-url).")
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValidationError(
            f"LinkedIn URL must start with http:// or https:// (got: {url})"
        )
    return url


def load_and_validate_contacts(path: str) -> List[Dict[str, str]]:
    """Load contacts from a CSV file and validate the whole file.

    Validates: file exists/readable, required columns present, each row has a
    valid email and non-empty name, and no duplicate emails within the file.

    Returns a list of normalized contact dicts: ``{name, email, company}``.
    """
    if not path:
        raise ValidationError("No contacts path provided (use --contacts).")

    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(abs_path):
        raise ValidationError(f"Contacts file does not exist: {abs_path}")
    if not os.path.isfile(abs_path):
        raise ValidationError(f"Contacts path is not a file: {abs_path}")
    if not os.access(abs_path, os.R_OK):
        raise ValidationError(f"Contacts file is not readable: {abs_path}")

    try:
        with open(abs_path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]

            missing = [c for c in config.REQUIRED_CSV_COLUMNS if c not in fieldnames]
            if missing:
                raise ValidationError(
                    "Contacts CSV is missing required column(s): "
                    f"{', '.join(missing)}. Required columns: "
                    f"{', '.join(config.REQUIRED_CSV_COLUMNS)}."
                )

            contacts: List[Dict[str, str]] = []
            seen_emails: Dict[str, int] = {}
            duplicates: List[str] = []

            for line_no, raw in enumerate(reader, start=2):  # header is line 1
                # Normalize keys to lowercase so header casing doesn't matter.
                row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}

                name = row.get("name", "")
                email = row.get("email", "")
                company = row.get("company", "")

                if not name:
                    raise ValidationError(f"Row {line_no}: missing 'name'.")
                if not email:
                    raise ValidationError(f"Row {line_no}: missing 'email'.")
                if not company:
                    raise ValidationError(f"Row {line_no}: missing 'company'.")
                if not is_valid_email(email):
                    raise ValidationError(
                        f"Row {line_no}: invalid email address: {email!r}"
                    )

                key = email.lower()
                if key in seen_emails:
                    duplicates.append(
                        f"{email} (rows {seen_emails[key]} and {line_no})"
                    )
                else:
                    seen_emails[key] = line_no

                contacts.append({"name": name, "email": email, "company": company})

    except UnicodeDecodeError as exc:
        raise ValidationError(f"Contacts CSV is not valid UTF-8: {exc}") from exc

    if duplicates:
        raise ValidationError(
            "Duplicate email addresses detected in contacts CSV:\n  - "
            + "\n  - ".join(duplicates)
        )

    if not contacts:
        raise ValidationError("Contacts CSV contains no data rows.")

    return contacts
