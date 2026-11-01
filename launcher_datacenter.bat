@echo off
REM ============================================================================
REM NOTE: Confirmed NOT applicable to jira.idoc.intel.com - that site's
REM profile menu redirects to id.atlassian.com for token creation, which
REM only happens on real Jira Cloud (Data Center/Server manages Personal
REM Access Tokens locally and never redirects there). Use launcher.bat
REM (OAuth/Cloud mode) instead. Kept here only in case a genuinely
REM on-prem Data Center instance is needed later.
REM ============================================================================
REM Jira Tray Monitor - launcher for an on-prem Jira Data Center / PAT instance
REM ============================================================================
REM This pre-fills the connection settings so each user only has to do ONE
REM thing the first time they run it: paste their own Personal Access Token
REM into the setup window that appears. There is no shared secret here -
REM every user's PAT is personal to their own Jira account.
REM ============================================================================

set JIRA_TRAY_APPROVAL_RECORDED=true
set JIRA_TRAY_DEPLOYMENT=datacenter
set "JIRA_TRAY_SITE_URL=https://jira.idoc.intel.com"
set "JIRA_TRAY_CHANNEL_JQL=project = WLWG"

cd /d "%~dp0"
set "JIRA_TRAY_CA_BUNDLE=%cd%\certs\intel_ca_chain.pem"

python -m app.main
