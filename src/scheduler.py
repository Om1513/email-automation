"""
Timezone-aware scheduling helpers.

All timestamps produced here are timezone-aware and serialized to ISO-8601 with
an explicit UTC offset, so state files remain unambiguous across machines and
DST changes. "Local time" means the local timezone of the machine running the
tool, per the spec.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from . import config
from .validators import ValidationError


def local_tz():
    """Return the local timezone as a tzinfo object."""
    # astimezone() with no argument attaches the system local timezone.
    return datetime.now().astimezone().tzinfo


def now_local() -> datetime:
    """Current time as a timezone-aware datetime in local time."""
    return datetime.now(local_tz())


def default_send_time(reference: datetime | None = None) -> datetime:
    """Tomorrow at 8:00 AM local time, as a tz-aware datetime."""
    ref = reference or now_local()
    tomorrow = (ref + timedelta(days=1)).date()
    return datetime(
        tomorrow.year,
        tomorrow.month,
        tomorrow.day,
        config.DEFAULT_SEND_HOUR,
        config.DEFAULT_SEND_MINUTE,
        tzinfo=local_tz(),
    )


def parse_schedule_at(value: str) -> datetime:
    """Parse a ``--schedule-at`` argument like ``"2026-06-15 08:00"``.

    The value is interpreted in local time and returned tz-aware.
    """
    value = (value or "").strip()
    fmts = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M")
    for fmt in fmts:
        try:
            naive = datetime.strptime(value, fmt)
            return naive.replace(tzinfo=local_tz())
        except ValueError:
            continue
    raise ValidationError(
        f"Could not parse --schedule-at {value!r}. "
        'Expected format: "YYYY-MM-DD HH:MM" (e.g. "2026-06-15 08:00").'
    )


def resolve_send_time(schedule_at: str | None) -> datetime:
    """Resolve the effective send time from the optional override."""
    if schedule_at:
        return parse_schedule_at(schedule_at)
    return default_send_time()


def to_iso(dt: datetime) -> str:
    """Serialize a tz-aware datetime to ISO-8601 with offset."""
    return dt.isoformat()


def from_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp back into a tz-aware datetime.

    Falls back to attaching local tz if the stored value somehow lacks offset.
    """
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=local_tz())
    return dt


def is_due(scheduled_iso: str, reference: datetime | None = None) -> bool:
    """True if ``scheduled_iso`` is at or before now."""
    ref = reference or now_local()
    return from_iso(scheduled_iso) <= ref
