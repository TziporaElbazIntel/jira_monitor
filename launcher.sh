#!/usr/bin/env bash
# ==============================================================================
# Jira Tray Monitor - team distribution launcher (OAuth mode) - Linux/macOS
# ==============================================================================
# This file lets teammates run the app WITHOUT entering a Client ID/Secret
# themselves - they only click "Sign in with Atlassian" in their browser.
#
# SECURITY NOTE: filling in JIRA_TRAY_OAUTH_CLIENT_SECRET below means that
# value is distributed, in plain text, to every machine that receives this
# file. Only do this if you (the app owner) have made an informed decision
# that this is acceptable for this app's audience and sharing scope. Do not
# commit a filled-in copy of this file to any shared/version-controlled
# location - only distribute the final launcher.sh directly to users (e.g.
# inside the zipped app folder).
# ==============================================================================

# 1) Rename this file to "launcher.sh" (remove the ".example" suffix).
# 2) Fill in your actual Client ID and Client Secret below.
# 3) Place it in the same folder as this project's "app" folder.
# 4) Make it executable:  chmod +x launcher.sh
# 5) Distribute the whole folder (or a zip/tarball of it) to your teammates.
# 6) Teammates run:  ./launcher.sh   (or double-click it, if their file
#    manager is set up to run .sh files) - no setup dialog needed.

export JIRA_TRAY_APPROVAL_RECORDED=true
export JIRA_TRAY_AUTH_MODE=oauth
export JIRA_TRAY_SITE_URL="https://jira.idoc.intel.com"
export JIRA_TRAY_OAUTH_CLIENT_ID="YOUR_CLIENT_ID_HERE"
export JIRA_TRAY_OAUTH_CLIENT_SECRET="YOUR_CLIENT_SECRET_HERE"
export JIRA_TRAY_CHANNEL_JQL="project = WLWG"

cd "$(dirname "$0")"
# NOTE: Do NOT set JIRA_TRAY_CA_BUNDLE here. Confirmed this deployment is
# real Jira Cloud: with OAuth, the app talks to api.atlassian.com (a
# public Atlassian endpoint with a publicly-trusted certificate), not
# directly to jira.idoc.intel.com. Pointing verification at Intel's
# internal CA bundle breaks that connection with CERTIFICATE_VERIFY_FAILED.

python3 -m app.main
