#!/usr/bin/env bash
#
# Convenience wrapper for the Gmail Outreach Automation tool (macOS / Linux).
#
# - Resolves its own location, so it works no matter what directory you call it
#   from (important for cron).
# - Creates the virtualenv and installs dependencies on first run.
# - Forwards every argument straight to `python -m src.main`.
#
# Examples:
#   ./run.sh dry-run     --contacts contacts.csv --campaign-id "quant-risk-june-2026" --linkedin-url "https://linkedin.com/in/yuktasethi"
#   ./run.sh create-drafts --contacts contacts.csv --campaign-id "quant-risk-june-2026" --linkedin-url "https://linkedin.com/in/yuktasethi"
#   ./run.sh send-due    --campaign-id "quant-risk-june-2026"

set -euo pipefail

# Absolute path to this script's directory (the project root).
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON="$VENV_DIR/bin/python"

# First-run bootstrap: create venv + install requirements.
if [[ ! -x "$PYTHON" ]]; then
  echo "[run.sh] Creating virtual environment in .venv ..."
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --quiet --upgrade pip
  "$VENV_DIR/bin/pip" install --quiet -r "$PROJECT_ROOT/requirements.txt"
  echo "[run.sh] Dependencies installed."
fi

exec "$PYTHON" -m src.main "$@"
