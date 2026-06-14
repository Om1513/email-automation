"""
Central configuration for the Gmail Outreach Automation tool.

Everything that is "policy" rather than "logic" lives here so it can be
reviewed and tweaked in one place: paths, OAuth scopes, the expected sender
account, scheduling defaults, and the email template itself.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Paths (resolved relative to the project root, i.e. the parent of src/)
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, "credentials.json")
TOKEN_FILE = os.path.join(PROJECT_ROOT, "token.json")

STATE_DIR = os.path.join(PROJECT_ROOT, "state")
BACKUP_DIR = os.path.join(STATE_DIR, "backups")

# Default resume attached to every email when --resume is not supplied.
# Falls back to the copy in files/ if the root copy is absent.
_ROOT_RESUME = os.path.join(PROJECT_ROOT, "YUKTA_SETHI_RESUME.pdf")
_FILES_RESUME = os.path.join(PROJECT_ROOT, "files", "Yukta_Sethi_Resume.pdf")
DEFAULT_RESUME = _ROOT_RESUME if os.path.exists(_ROOT_RESUME) else _FILES_RESUME

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "outreach.log")

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
# The account that MUST be authenticated. If OAuth returns any other address
# the run is aborted. This is a guard against sending from the wrong account.
EXPECTED_SENDER = "yuktasethi@gmail.com"

# gmail.compose is sufficient for everything we do:
#   - users.drafts.create   (create drafts)
#   - users.drafts.send     (send drafts)
#   - users.getProfile      (verify the authenticated address)
# It does NOT grant read access to the mailbox, keeping the footprint minimal.
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]

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
SUBJECT = "Quant, Risk, and a real love of the numbers!"

# Placeholders are replaced with str.replace (not str.format) so that any
# stray braces in real-world data cannot break templating.
PLACEHOLDER_FIRST_NAME = "{First Name}"
PLACEHOLDER_COMPANY = "{Company Name}"
PLACEHOLDER_LINKEDIN = "{LinkedIn URL}"

BODY_TEMPLATE = """Hi {First Name},

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
