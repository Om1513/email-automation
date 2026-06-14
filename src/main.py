"""
Command-line entry point for the Gmail Outreach Automation tool.

Subcommands:
  dry-run        Preview personalized emails + scheduling. No drafts, no sends.
  create-drafts  Create Gmail drafts and record scheduling metadata.
  send-due       Send drafts whose scheduled time has arrived.

Run ``python -m src.main <command> --help`` for per-command options.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import List

from . import config
from .auth import AuthError, get_gmail_service
from .email_builder import build_personalized_content
from .gmail_client import GmailClient, GmailClientError
from .logger import get_logger
from .scheduler import (
    from_iso,
    is_due,
    now_local,
    resolve_send_time,
    to_iso,
)
from .state_store import CampaignState, validate_campaign_id
from .validators import (
    ValidationError,
    load_and_validate_contacts,
    validate_linkedin_url,
    validate_resume,
)

log = get_logger("main")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Automate personalized Gmail outreach (drafts + scheduled send).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common_build_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--contacts", required=True, help="Path to contacts CSV.")
        p.add_argument(
            "--resume",
            default=config.DEFAULT_RESUME,
            help="Path to resume PDF attached to every email "
            f"(default: {config.DEFAULT_RESUME}).",
        )
        p.add_argument("--campaign-id", required=True, help="Unique campaign id.")
        p.add_argument(
            "--linkedin-url", required=True, help="LinkedIn URL to embed in the email."
        )
        p.add_argument(
            "--schedule-at",
            default=None,
            help='Override send time, local tz, e.g. "2026-06-15 08:00". '
            "Defaults to tomorrow 08:00 local.",
        )
        p.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Only process the first N recipients (useful for testing).",
        )

    # dry-run
    p_dry = sub.add_parser("dry-run", help="Preview emails; create nothing.")
    add_common_build_args(p_dry)

    # create-drafts
    p_create = sub.add_parser("create-drafts", help="Create Gmail drafts.")
    add_common_build_args(p_create)
    p_create.add_argument(
        "--force",
        action="store_true",
        help="Recreate drafts even if a draft/sent record already exists.",
    )

    # send-due
    p_send = sub.add_parser("send-due", help="Send drafts whose time has arrived.")
    p_send.add_argument("--campaign-id", required=True, help="Campaign id to send.")
    p_send.add_argument(
        "--send-delay-seconds",
        type=float,
        default=config.DEFAULT_SEND_DELAY_SECONDS,
        help=f"Delay between sends (default {config.DEFAULT_SEND_DELAY_SECONDS}s).",
    )
    p_send.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only send the first N due drafts (useful for testing).",
    )

    return parser


def _apply_limit(items: List, limit) -> List:
    if limit is not None and limit >= 0:
        return items[:limit]
    return items


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_dry_run(args) -> int:
    """Validate inputs and preview every personalized email. No side effects
    on Gmail; records are persisted with status 'previewed' for reference."""
    resume_path = validate_resume(args.resume)
    linkedin_url = validate_linkedin_url(args.linkedin_url)
    validate_campaign_id(args.campaign_id)
    contacts = load_and_validate_contacts(args.contacts)
    contacts = _apply_limit(contacts, args.limit)

    send_time = resolve_send_time(args.schedule_at)
    log.info("DRY RUN — campaign %s", args.campaign_id)
    log.info("Resume: %s", resume_path)
    log.info("Scheduled send time (local): %s", send_time.isoformat())
    log.info("Recipients to preview: %d", len(contacts))

    state = CampaignState.load_or_create(args.campaign_id)

    for i, contact in enumerate(contacts, start=1):
        content = build_personalized_content(contact, linkedin_url)
        log.info("-" * 72)
        log.info("[%d/%d] To: %s <%s>", i, len(contacts), contact["name"], contact["email"])
        log.info("Company: %s | First name: %s", contact["company"], content["first_name"])
        log.info("Subject: %s", content["subject"])
        # Dry-run is the one place full body preview is allowed.
        log.info("Body preview:\n%s", content["body"])

        state.upsert(
            contact["email"],
            {
                "name": contact["name"],
                "company": contact["company"],
                "first_name": content["first_name"],
                "subject": content["subject"],
                "scheduled_send_time": to_iso(send_time),
                "status": config.STATUS_PREVIEWED,
                "error_message": None,
            },
        )

    state.backup()
    state.save()
    log.info("-" * 72)
    log.info("Dry run complete. No drafts created, no emails sent.")
    return 0


def cmd_create_drafts(args) -> int:
    """Create Gmail drafts for each contact and record scheduling metadata."""
    resume_path = validate_resume(args.resume)
    linkedin_url = validate_linkedin_url(args.linkedin_url)
    validate_campaign_id(args.campaign_id)
    contacts = load_and_validate_contacts(args.contacts)
    contacts = _apply_limit(contacts, args.limit)

    send_time = resolve_send_time(args.schedule_at)

    service = get_gmail_service()
    client = GmailClient(service, config.EXPECTED_SENDER)

    state = CampaignState.load_or_create(args.campaign_id)
    state.backup()  # one backup before this run mutates anything

    log.info("CREATE DRAFTS — campaign %s", args.campaign_id)
    log.info("Scheduled send time (local): %s", send_time.isoformat())
    log.info("Recipients: %d (force=%s)", len(contacts), args.force)

    created = skipped = failed = 0

    for i, contact in enumerate(contacts, start=1):
        email = contact["email"]

        if not args.force and state.is_blocking_duplicate(email):
            log.info("[%d/%d] SKIP %s (already draft_created/sent).", i, len(contacts), email)
            state.upsert(email, {"status": config.STATUS_SKIPPED, "error_message": None})
            state.save()
            skipped += 1
            continue

        content = build_personalized_content(contact, linkedin_url)
        try:
            result = client.create_draft(
                to=email,
                subject=content["subject"],
                body=content["body"],
                resume_path=resume_path,
            )
            state.upsert(
                email,
                {
                    "name": contact["name"],
                    "company": contact["company"],
                    "first_name": content["first_name"],
                    "subject": content["subject"],
                    "gmail_draft_id": result["draft_id"],
                    "gmail_message_id": result["message_id"],
                    "scheduled_send_time": to_iso(send_time),
                    "status": config.STATUS_DRAFT_CREATED,
                    "error_message": None,
                },
            )
            state.save()  # persist immediately for resilience
            created += 1
            log.info("[%d/%d] DRAFT created for %s (draft %s)", i, len(contacts), email, result["draft_id"])
        except (GmailClientError, OSError) as exc:
            state.upsert(
                email,
                {
                    "name": contact["name"],
                    "company": contact["company"],
                    "first_name": content["first_name"],
                    "subject": content["subject"],
                    "status": config.STATUS_FAILED,
                    "error_message": str(exc),
                },
            )
            state.save()
            failed += 1
            log.error("[%d/%d] FAILED to create draft for %s: %s", i, len(contacts), email, exc)

    log.info("-" * 72)
    log.info("Done. created=%d skipped=%d failed=%d", created, skipped, failed)
    log.info("Review the drafts in Gmail, then schedule send-due for %s.", send_time.isoformat())
    return 0 if failed == 0 else 1


def cmd_send_due(args) -> int:
    """Send all drafts whose scheduled_send_time has arrived."""
    validate_campaign_id(args.campaign_id)
    state = CampaignState.load(args.campaign_id)

    service = get_gmail_service()
    client = GmailClient(service, config.EXPECTED_SENDER)

    state.backup()
    now = now_local()
    log.info("SEND DUE — campaign %s (now=%s)", args.campaign_id, now.isoformat())

    due = []
    for rec in state.records():
        if rec.get("status") != config.STATUS_DRAFT_CREATED:
            continue
        scheduled = rec.get("scheduled_send_time")
        if scheduled and is_due(scheduled, now):
            due.append(rec)

    due = _apply_limit(due, args.limit)
    log.info("Drafts due to send: %d", len(due))

    sent = failed = 0
    for i, rec in enumerate(due, start=1):
        email = rec["email"]
        draft_id = rec.get("gmail_draft_id")
        try:
            message_id = client.send_draft(draft_id)
            state.upsert(
                email,
                {
                    "gmail_message_id": message_id,
                    "status": config.STATUS_SENT,
                    "error_message": None,
                },
            )
            state.save()  # save immediately after each send
            sent += 1
            log.info(
                "[%d/%d] SENT to %s (scheduled %s, message %s)",
                i, len(due), email, rec.get("scheduled_send_time"), message_id,
            )
        except (GmailClientError, OSError) as exc:
            state.upsert(
                email, {"status": config.STATUS_FAILED, "error_message": str(exc)}
            )
            state.save()
            failed += 1
            log.error("[%d/%d] FAILED to send to %s: %s", i, len(due), email, exc)

        # Rate limit between sends (skip the wait after the final one).
        if i < len(due) and args.send_delay_seconds > 0:
            time.sleep(args.send_delay_seconds)

    log.info("-" * 72)
    log.info("Send complete. sent=%d failed=%d", sent, failed)
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
_COMMANDS = {
    "dry-run": cmd_dry_run,
    "create-drafts": cmd_create_drafts,
    "send-due": cmd_send_due,
}


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = _COMMANDS[args.command]
    try:
        return handler(args)
    except ValidationError as exc:
        log.error("Validation error: %s", exc)
        return 2
    except AuthError as exc:
        log.error("Authentication error: %s", exc)
        return 3
    except KeyboardInterrupt:
        log.warning("Interrupted by user.")
        return 130
    except Exception as exc:  # last-resort safety net
        log.exception("Unexpected error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
