@echo off
REM ============================================================================
REM Jira Tray Monitor - team distribution launcher (OAuth mode)
REM ============================================================================
REM This file lets teammates run the app WITHOUT entering a Client ID/Secret
REM themselves - they only click "Sign in with Atlassian" in their browser.
REM
REM SECURITY NOTE: filling in JIRA_TRAY_OAUTH_CLIENT_SECRET below means that
REM value is distributed, in plain text, to every machine that receives this
REM file. Only do this if you (the app owner) have made an informed decision
REM that this is acceptable for this app's audience and sharing scope (see
REM PRIVACY_POLICY_DRAFT.md for the full discussion of what this secret does
REM and does not expose).
REM
REM IMPORTANT: Fill in the real values ONLY on your own local machine, in
REM your own downloaded/extracted copy of this project - never inside a
REM shared editor/workspace/session, and never commit a filled-in copy to
REM any shared or version-controlled location.
REM ============================================================================

REM 1) Download/extract this project on YOUR OWN machine first.
REM 2) There, rename this file to "launcher.bat" (remove the ".example").
REM 3) Fill in your actual Client ID and Client Secret below.
REM 4) Keep it in the same folder as this project's "app" folder.
REM 5) Distribute the whole folder (or a zip of it) to your teammates.
REM 6) Teammates just double-click launcher.bat - no setup dialog needed.

set JIRA_TRAY_APPROVAL_RECORDED=true
set JIRA_TRAY_AUTH_MODE=oauth
set "JIRA_TRAY_SITE_URL=https://jira.idoc.intel.com"
set "JIRA_TRAY_OAUTH_CLIENT_ID=YOUR_CLIENT_ID_HERE"
set "JIRA_TRAY_OAUTH_CLIENT_SECRET=YOUR_CLIENT_SECRET_HERE"
set "JIRA_TRAY_CHANNEL_JQL=project = WLWG"

cd /d "%~dp0"
REM NOTE: Do NOT set JIRA_TRAY_CA_BUNDLE here. Confirmed this deployment is
REM real Jira Cloud: with OAuth, the app talks to api.atlassian.com (a
REM public Atlassian endpoint with a publicly-trusted certificate), not
REM directly to jira.idoc.intel.com. Pointing verification at Intel's
REM internal CA bundle breaks that connection with CERTIFICATE_VERIFY_FAILED.

REM Your machine has multiple Python installations, and plain "python" may
REM resolve to one that doesn't have the packages installed. Pin explicitly
REM to the version where `pip install -r requirements.txt` succeeded.
py -3.14 -m app.main
if errorlevel 1 (
    echo.
    echo The app exited with an error - see the message above.
)
pause
