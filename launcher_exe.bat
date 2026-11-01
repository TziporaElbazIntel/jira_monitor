@echo off
REM ============================================================================
REM Jira Tray Monitor - OPTIONAL override launcher for the standalone .exe
REM ============================================================================
REM This file is NOT required anymore. If you filled in app/team_defaults.py
REM and rebuilt the .exe (see README.md's "Recommended: distribute a single
REM standalone .exe" section), the .exe already has your team's Site URL,
REM Channel JQL, auth mode, and OAuth Client ID/Secret baked in - teammates
REM can just double-click JiraTrayMonitor.exe directly, with no .bat file at
REM all.
REM
REM Use this .bat ONLY if you need to override some of those baked-in
REM defaults for a specific variant/team without rebuilding the exe (e.g. a
REM different Channel JQL for a different sub-team sharing the same build).
REM Any JIRA_TRAY_... variable set below always wins over the exe's baked-in
REM default; leave a line commented out to just use the baked-in value.
REM
REM SECURITY NOTE: if you do fill in JIRA_TRAY_OAUTH_CLIENT_SECRET below,
REM that value is distributed, in plain text, to every machine that
REM receives this file - same trade-off as baking it into the exe. Only do
REM this if you've made an informed decision this is acceptable (see
REM README.md's "Distributing to a team" section).
REM
REM IMPORTANT: Fill in real values ONLY on your own local machine, in your
REM own downloaded/extracted copy of this project - never inside a shared
REM editor/workspace/session, and never commit a filled-in copy to any
REM shared or version-controlled location.
REM ============================================================================

REM --- Uncomment and edit only the lines you need to override ---------------
REM set JIRA_TRAY_APPROVAL_RECORDED=true
REM set JIRA_TRAY_AUTH_MODE=oauth
REM set "JIRA_TRAY_SITE_URL=https://jira.idoc.intel.com"
REM set "JIRA_TRAY_OAUTH_CLIENT_ID=YOUR_CLIENT_ID_HERE"
REM set "JIRA_TRAY_OAUTH_CLIENT_SECRET=YOUR_CLIENT_SECRET_HERE"
REM set "JIRA_TRAY_CHANNEL_JQL=project = WLWG"

cd /d "%~dp0"
REM NOTE: Do NOT set JIRA_TRAY_CA_BUNDLE here. Confirmed this deployment is
REM real Jira Cloud: with OAuth, the app talks to api.atlassian.com (a
REM public Atlassian endpoint with a publicly-trusted certificate), not
REM directly to jira.idoc.intel.com. Pointing verification at Intel's
REM internal CA bundle breaks that connection with CERTIFICATE_VERIFY_FAILED.

JiraTrayMonitor.exe
if errorlevel 1 (
    echo.
    echo The app exited with an error.
    echo If this keeps happening, rebuild the exe with "console=True" in
    echo pyinstaller.spec temporarily, so error details are visible here.
    pause
)
