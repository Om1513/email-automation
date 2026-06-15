@echo off
REM Convenience wrapper for the Gmail Outreach Automation tool (Windows).
REM
REM - Runs from the script's own folder, so it works under Task Scheduler.
REM - Creates the virtualenv and installs dependencies on first run.
REM - Forwards every argument straight to `python -m src.main`.
REM
REM Examples:
REM   run.bat dry-run     --contacts contacts.csv --campaign-id "quant-risk-june-2026" --linkedin-url "https://linkedin.com/in/yuktasethi"
REM   run.bat create-drafts --contacts contacts.csv --campaign-id "quant-risk-june-2026" --linkedin-url "https://linkedin.com/in/yuktasethi"
REM   run.bat send-due    --campaign-id "quant-risk-june-2026"

setlocal
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

set "VENV_DIR=%PROJECT_ROOT%.venv"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo [run.bat] Creating virtual environment in .venv ...
  python -m venv "%VENV_DIR%"
  "%VENV_DIR%\Scripts\python.exe" -m pip install --quiet --upgrade pip
  "%VENV_DIR%\Scripts\python.exe" -m pip install --quiet -r "%PROJECT_ROOT%requirements.txt"
  echo [run.bat] Dependencies installed.
)

"%PYTHON%" -m src.main %*
endlocal
