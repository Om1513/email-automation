"""
Campaign state persistence using local JSON files (no database).

State lives at ``state/{campaign_id}.json``. A timestamped backup is written to
``state/backups/`` before the file is mutated, so a bad run is always
recoverable. Recipients are keyed by lowercase email within a campaign.

State document shape::

    {
      "campaign_id": "quant-risk-june-2026",
      "created_at": "...",
      "updated_at": "...",
      "recipients": {
        "jane@example.com": {
          "name": ..., "email": ..., "company": ..., "first_name": ...,
          "subject": ..., "gmail_draft_id": ..., "gmail_message_id": ...,
          "scheduled_send_time": ..., "status": ...,
          "created_at": ..., "updated_at": ..., "error_message": ...
        },
        ...
      }
    }
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

from . import config
from .logger import get_logger
from .scheduler import now_local, to_iso
from .validators import ValidationError

log = get_logger("state")

_CAMPAIGN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _campaign_path(campaign_id: str) -> str:
    return os.path.join(config.STATE_DIR, f"{campaign_id}.json")


def _timestamp_slug() -> str:
    """Filesystem-safe timestamp for backup filenames."""
    return now_local().strftime("%Y%m%d-%H%M%S")


def validate_campaign_id(campaign_id: str) -> str:
    """Ensure the campaign id is safe to use as a filename."""
    if not campaign_id or not _CAMPAIGN_ID_RE.match(campaign_id):
        raise ValidationError(
            "Invalid --campaign-id. Use only letters, numbers, '.', '_' and '-' "
            f"(got: {campaign_id!r})."
        )
    return campaign_id


class CampaignState:
    """In-memory view of a campaign's state with explicit persistence."""

    def __init__(self, campaign_id: str, data: Dict):
        self.campaign_id = campaign_id
        self.data = data

    # ---- construction ----------------------------------------------------
    @classmethod
    def load_or_create(cls, campaign_id: str) -> "CampaignState":
        validate_campaign_id(campaign_id)
        os.makedirs(config.STATE_DIR, exist_ok=True)
        path = _campaign_path(campaign_id)

        if os.path.exists(path):
            if not os.access(path, os.R_OK):
                raise ValidationError(f"Campaign state file is not readable: {path}")
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                raise ValidationError(
                    f"Campaign state file is corrupt or unreadable: {path} ({exc})"
                ) from exc
            log.debug("Loaded existing campaign state: %s", path)
        else:
            ts = to_iso(now_local())
            data = {
                "campaign_id": campaign_id,
                "created_at": ts,
                "updated_at": ts,
                "recipients": {},
            }
            log.debug("Initialized new campaign state for %s", campaign_id)

        data.setdefault("recipients", {})
        return cls(campaign_id, data)

    @classmethod
    def load(cls, campaign_id: str) -> "CampaignState":
        """Load an existing campaign; error if it does not exist."""
        validate_campaign_id(campaign_id)
        path = _campaign_path(campaign_id)
        if not os.path.exists(path):
            raise ValidationError(
                f"No campaign state found for {campaign_id!r} at {path}. "
                "Run create-drafts (or dry-run) first."
            )
        return cls.load_or_create(campaign_id)

    # ---- accessors -------------------------------------------------------
    @property
    def recipients(self) -> Dict[str, Dict]:
        return self.data["recipients"]

    def get(self, email: str) -> Optional[Dict]:
        return self.recipients.get(email.lower())

    def records(self) -> List[Dict]:
        return list(self.recipients.values())

    def is_blocking_duplicate(self, email: str) -> bool:
        """True if this email already has a draft_created/sent record."""
        rec = self.get(email)
        return bool(rec and rec.get("status") in config.DUPLICATE_BLOCKING_STATUSES)

    # ---- mutation --------------------------------------------------------
    def upsert(self, email: str, fields: Dict) -> Dict:
        """Insert or update a recipient record, stamping timestamps.

        Returns the resulting record. Does NOT persist; call save().
        """
        key = email.lower()
        ts = to_iso(now_local())
        existing = self.recipients.get(key)

        if existing is None:
            record = {
                "name": "",
                "email": email,
                "company": "",
                "first_name": "",
                "subject": "",
                "gmail_draft_id": None,
                "gmail_message_id": None,
                "scheduled_send_time": None,
                "status": None,
                "created_at": ts,
                "updated_at": ts,
                "error_message": None,
            }
        else:
            record = existing

        record.update(fields)
        record["email"] = email  # keep canonical casing from input
        record["updated_at"] = ts
        if existing is None:
            record["created_at"] = ts

        self.recipients[key] = record
        return record

    # ---- persistence -----------------------------------------------------
    def backup(self) -> Optional[str]:
        """Write a timestamped backup of the current on-disk state, if any.

        Returns the backup path, or None if there was nothing to back up.
        """
        path = _campaign_path(self.campaign_id)
        if not os.path.exists(path):
            return None
        os.makedirs(config.BACKUP_DIR, exist_ok=True)
        backup_path = os.path.join(
            config.BACKUP_DIR, f"{self.campaign_id}_{_timestamp_slug()}.json"
        )
        with open(path, encoding="utf-8") as src, open(
            backup_path, "w", encoding="utf-8"
        ) as dst:
            dst.write(src.read())
        log.info("Backed up campaign state -> %s", backup_path)
        return backup_path

    def save(self) -> str:
        """Persist state atomically (write to temp then replace)."""
        os.makedirs(config.STATE_DIR, exist_ok=True)
        path = _campaign_path(self.campaign_id)
        self.data["updated_at"] = to_iso(now_local())

        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        log.debug("Saved campaign state -> %s", path)
        return path
