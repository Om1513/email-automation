"""
Logging setup for the outreach tool.

Provides a single configured logger that writes to both the console and
``logs/outreach.log`` with timestamps and severity levels. A small helper
(``redact``) is included so callers can scrub anything sensitive before it is
ever handed to the logger.

Hard rules (enforced by convention + this module never logging them):
  * Never log OAuth tokens or credential contents.
  * Never log the full personalized email body (except explicit dry-run
    previews, which the caller opts into).
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from . import config

_CONFIGURED = False

# Substrings that should never appear in logs. If a message looks like it
# contains one of these, redact() blanks the whole value.
_SENSITIVE_HINTS = ("token", "client_secret", "refresh_token", "access_token")


def get_logger(name: str = "outreach") -> logging.Logger:
    """Return the shared, fully-configured application logger."""
    global _CONFIGURED
    logger = logging.getLogger("outreach")

    if not _CONFIGURED:
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        os.makedirs(config.LOG_DIR, exist_ok=True)

        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Console: INFO and above (keep it readable for interactive use).
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(fmt)

        # File: DEBUG and above, rotated so the log never grows unbounded.
        file_handler = RotatingFileHandler(
            config.LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)

        logger.addHandler(console)
        logger.addHandler(file_handler)

        # Quiet the noisy Google client libraries unless something breaks.
        logging.getLogger("googleapiclient").setLevel(logging.WARNING)
        logging.getLogger("google").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

        _CONFIGURED = True

    return logging.getLogger(name if name.startswith("outreach") else f"outreach.{name}")


def redact(value: str) -> str:
    """Return a log-safe version of ``value``.

    If the value appears to contain a secret, it is replaced wholesale; this is
    intentionally aggressive because logs are cheap and leaked tokens are not.
    """
    if value is None:
        return ""
    lowered = str(value).lower()
    if any(hint in lowered for hint in _SENSITIVE_HINTS):
        return "[REDACTED]"
    return str(value)
