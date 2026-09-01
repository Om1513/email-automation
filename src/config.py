"""
Central configuration for the Gmail Outreach Automation tool.

Everything that is "policy" rather than "logic" lives here so it can be
reviewed and tweaked in one place: paths, OAuth scopes, the expected sender
account, scheduling defaults, and the email template itself.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Paths (resolved relative to the project root, i.e. the parent of src/)
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, "credentials.json")
TOKEN_FILE = os.path.join(PROJECT_ROOT, "token.json")

STATE_DIR = os.path.join(PROJECT_ROOT, "state")
BACKUP_DIR = os.path.join(STATE_DIR, "backups")

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "outreach.log")


def _resolve_resume(root_name: str, files_name: str) -> str:
    """Return the project-root copy of a resume, falling back to files/."""
    root_copy = os.path.join(PROJECT_ROOT, root_name)
    if os.path.exists(root_copy):
        return root_copy
    return os.path.join(PROJECT_ROOT, "files", files_name)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
# gmail.compose is sufficient for everything we do:
#   - users.drafts.create   (create drafts)
#   - users.drafts.send     (send drafts)
#   - users.getProfile      (verify the authenticated address)
# It does NOT grant read access to the mailbox, keeping the footprint minimal.
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


def token_file_for(sender: str) -> str:
    """Return the token file path for a given sender account.

    The default sender keeps the original ``token.json`` (back-compat); any
    other account gets its own ``token_<account>.json`` so switching senders
    never clobbers another account's credentials.
    """
    import re

    if sender.lower() == EXPECTED_SENDER.lower():
        return TOKEN_FILE
    safe = re.sub(r"[^A-Za-z0-9]+", "_", sender.lower()).strip("_")
    return os.path.join(PROJECT_ROOT, f"token_{safe}.json")

# ---------------------------------------------------------------------------
# Scheduling defaults
# ---------------------------------------------------------------------------
DEFAULT_SEND_HOUR = 8        # 8:00 AM
DEFAULT_SEND_MINUTE = 0
DEFAULT_SEND_DELAY_SECONDS = 5

# ---------------------------------------------------------------------------
# CSV / validation
# ---------------------------------------------------------------------------
REQUIRED_CSV_COLUMNS = ("name", "email", "company")

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
STATUS_PREVIEWED = "previewed"
STATUS_DRAFT_CREATED = "draft_created"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

VALID_STATUSES = (
    STATUS_PREVIEWED,
    STATUS_DRAFT_CREATED,
    STATUS_SENT,
    STATUS_FAILED,
    STATUS_SKIPPED,
)

# Statuses that mean "we already committed an outbound action for this person".
# Re-running create-drafts will skip these unless --force is supplied.
DUPLICATE_BLOCKING_STATUSES = (STATUS_DRAFT_CREATED, STATUS_SENT)

# ---------------------------------------------------------------------------
# Email content
# ---------------------------------------------------------------------------
# Placeholders are replaced with str.replace (not str.format) so that any
# stray braces in real-world data cannot break templating.
PLACEHOLDER_FIRST_NAME = "{First Name}"
PLACEHOLDER_COMPANY = "{Company Name}"
PLACEHOLDER_LINKEDIN = "{LinkedIn URL}"

_YUKTA_SUBJECT = "Quant, Risk, and a real love of the numbers!"

_YUKTA_BODY = """Hi {First Name},

I've always loved numbers, the way they carry a kind of honesty, where everything has to reconcile in the end. That love grew into a fascination with how systems behave under pressure, how small changes ripple through a structure and reveal the true shape of risk. It's what pulled me toward quantitative modeling, and it's the same instinct that shapes how I approach markets and engineering today.

Most recently, I was a market risk analyst at StoneX, where I worked across global futures, rates, and fixed-income portfolios. My work centered on building quantitative risk infrastructure: Python-based exposure and SA-CCR/PFE analytics, sensitivity and curve-risk models on the MSCI RiskMetrics platform, and SQL pipelines feeding real-time risk and P&L attribution. Much of what I built was used directly by trading desks and risk leadership, which pushed me to make complex outputs intuitive, transparent, and something people could actually act on.

Before StoneX, I developed event-driven signals and sentiment factors at MAK Capital, a billion-dollar hedge fund, and modeled fixed-income sensitivities, hedging frameworks, and portfolio risk at Numeraxial using QuantLib and scenario analysis. Across all of it, I've gravitated toward work that mixes quantitative depth with real engineering and clear communication: building the tools that help a team understand how risk behaves and how to manage it.

I really like how {Company Name} pairs serious trading technology with disciplined risk management. Work like this sits exactly where I do my best thinking, at the meeting point of modeling, software, and high-visibility risk and P&L work. The chance to build and improve risk analytics platforms and to dig into model performance, backtesting, and P&L attribution is the kind of problem I'd happily lose a weekend to.

I've attached my resume, and if my background looks like a fit for anything you're working on, I'd truly welcome the chance to connect. Even a brief conversation would mean a lot.

Warm regards,

Yukta Sethi
(347) 728-8849
yuktasethi@gmail.com
{LinkedIn URL}
"""

_OM_SUBJECT = "Building is what I do best — would love to contribute at {Company Name}"

# Om sends from more than one account. The body copy is identical across them;
# only the signature address changes, so it is templated here rather than
# duplicated -- edit the copy once and both variants stay in sync.
_OM_SIGNATURE_EMAIL_TOKEN = "__SENDER_EMAIL__"

_OM_BODY_TEMPLATE = """Hi {First Name},

I've spent time learning about what you're building at {Company Name}, and I'm genuinely impressed by it. Building is the one thing I am good at. If building is what you're looking for, I would love to chat.

I'm Om, a passionate coder with 2+ yrs of software development experience and a hunger to learn, eager to grow under your guidance, and help build systems from 0 -> 100 or 1 -> 100.

Over the last two years, I've helped MAK Capital generate consistent five-figure weekly profits using AI-based prediction models and LLM-powered analytics pipelines. I contributed to a National Science Foundation project by developing and deploying a real-time AI simulation of a power grid. Last summer, I joined Aroris Health as a Founding Engineer, building backend and frontend features and helping scale and onboard clients onto their web platform. I'm currently working with SewerAI, helping the startup scale its infrastructure and accelerate growth as a Software Development Engineer.

I've built full-stack systems with React/TypeScript front ends, Python/Node.js/Go backends (GraphQL + gRPC), and deployed on AWS/GCP and Docker, designed and trained AI/ML models, developed agentic workflows, worked with GANs, and built RAG systems using vector databases and optimized search pipelines.

If there's room to talk, I'd love to hear how you think about growing the team. Even a quick call would mean a lot.

Best,

Om Singhan
(917) 328-0100
__SENDER_EMAIL__
{LinkedIn URL}
"""


def _om_body_for(sender_email: str) -> str:
    """Render Om's body with the signature address matching the sending account."""
    return _OM_BODY_TEMPLATE.replace(_OM_SIGNATURE_EMAIL_TOKEN, sender_email)


_OM_GMAIL_SENDER = "omsinghan25@gmail.com"
_OM_NYU_SENDER = "oss9762@nyu.edu"


# ---------------------------------------------------------------------------
# Sender profiles
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Profile:
    """One outreach identity: who sends, which resume, and which template.

    Keeping these bundled means a run can never mix (say) Om's body copy with
    Yukta's resume attachment — picking a profile picks all three together.
    """

    key: str
    display_name: str
    sender: str
    resume: str
    subject: str
    body_template: str
    # Where this profile's contact CSVs live. A bare --contacts filename is
    # resolved against this directory, so each identity's lists stay separate.
    contacts_dir: str


PROFILES = {
    "yukta": Profile(
        key="yukta",
        display_name="Yukta Sethi",
        sender="yuktasethi@gmail.com",
        resume=_resolve_resume("YUKTA_SETHI_RESUME.pdf", "Yukta_Sethi_Resume.pdf"),
        subject=_YUKTA_SUBJECT,
        body_template=_YUKTA_BODY,
        # Yukta's lists predate the contacts/ layout and stay in the root.
        contacts_dir=PROJECT_ROOT,
    ),
    # Yukta's second sending channel. Unlike om/om-nyu, the signature keeps her
    # gmail address: that is the contact address on her resume and the one her
    # earlier gmail/nyu split campaigns have always used.
    "yukta-nyu": Profile(
        key="yukta-nyu",
        display_name="Yukta Sethi (NYU)",
        sender="yns2318@nyu.edu",
        resume=_resolve_resume("YUKTA_SETHI_RESUME.pdf", "Yukta_Sethi_Resume.pdf"),
        subject=_YUKTA_SUBJECT,
        body_template=_YUKTA_BODY,
        contacts_dir=PROJECT_ROOT,
    ),
    "om": Profile(
        key="om",
        display_name="Om Singhan",
        sender=_OM_GMAIL_SENDER,
        resume=_resolve_resume(
            "OM_SANJAY_SINGHAN_RESUME.pdf", "Om_Sanjay_Singhan_Resume.pdf"
        ),
        subject=_OM_SUBJECT,
        body_template=_om_body_for(_OM_GMAIL_SENDER),
        contacts_dir=os.path.join(PROJECT_ROOT, "contacts", "om"),
    ),
    # Same person, same copy, same resume -- only the sending account and the
    # signature address differ. Drafts live in whichever mailbox created them,
    # so a split send needs one campaign per profile.
    "om-nyu": Profile(
        key="om-nyu",
        display_name="Om Singhan (NYU)",
        sender=_OM_NYU_SENDER,
        resume=_resolve_resume(
            "OM_SANJAY_SINGHAN_RESUME.pdf", "Om_Sanjay_Singhan_Resume.pdf"
        ),
        subject=_OM_SUBJECT,
        body_template=_om_body_for(_OM_NYU_SENDER),
        contacts_dir=os.path.join(PROJECT_ROOT, "contacts", "om"),
    ),
}

# Existing campaigns and cron entries were written before profiles existed, so
# the default stays on the original identity. Pass --profile to switch.
DEFAULT_PROFILE = "yukta"


def get_profile(key: str) -> Profile:
    """Look up a profile by key, raising a helpful error on a typo."""
    try:
        return PROFILES[key]
    except KeyError:
        known = ", ".join(sorted(PROFILES))
        raise KeyError(f"Unknown profile {key!r}. Available profiles: {known}.") from None


# Back-compat aliases for the default profile. Existing code and docs refer to
# these names directly; new code should read them off a Profile instead.
_DEFAULT = PROFILES[DEFAULT_PROFILE]

# The account that MUST be authenticated. If OAuth returns any other address
# the run is aborted. This is a guard against sending from the wrong account.
EXPECTED_SENDER = _DEFAULT.sender
DEFAULT_RESUME = _DEFAULT.resume
SUBJECT = _DEFAULT.subject
BODY_TEMPLATE = _DEFAULT.body_template
