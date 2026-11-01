"""Static, non-secret configuration for Jira Cloud Tray Monitor.

Per SPECIFICATION.md section 2: Jira Cloud only, per-user API tokens (never
a shared/service-account token), no backend/webhook/push service. All
secrets (the API token) live only in the OS credential manager via
`auth/credential_store.py` - never here, never on disk, never logged.

Values that are policy decisions for the product owner (tenant URL, the
approved source-channel JQL, and recorded security approval) are read from
the environment rather than hardcoded/invented, per section 11 ("Open
Decisions Before Implementation").
"""
import os

from app import team_defaults

APP_NAME = "JiraTrayMonitor"
KEYRING_SERVICE = "jira_tray_monitor"
KEYRING_USER = "default"

# --- Release/approval gate (section 2 and 5) ---------------------------
# Atlassian currently warns against distributing apps that collect users'
# API tokens. This app must not run until that internal security/policy
# approval has actually been recorded. Only set this to true after that
# approval exists; do not flip it to unblock development shortcuts.
APPROVAL_RECORDED = os.environ.get("JIRA_TRAY_APPROVAL_RECORDED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)

# --- Tenant and query (section 4.2 and 11) ------------------------------
# Jira Cloud site, e.g. "https://your-team.atlassian.net". Must be supplied
# by the product owner; this app does not guess or default it.
JIRA_SITE_URL = os.environ.get("JIRA_TRAY_SITE_URL", team_defaults.TEAM_SITE_URL).rstrip("/")

# Approved JQL clause identifying the source channel (e.g. a project/label
# filter). This is policy, not something this app may invent (section 4.2:
# "do not invent it").
CHANNEL_JQL = os.environ.get("JIRA_TRAY_CHANNEL_JQL", team_defaults.TEAM_CHANNEL_JQL).strip()

# --- Deployment type (NOT part of SPECIFICATION.md, which scopes this app
# to Jira Cloud only) -----------------------------------------------------
# SPECIFICATION.md section 2 scopes this app to Jira Cloud. "datacenter" is
# an explicit, opt-in local-testing escape hatch (requested outside the
# spec) for trying the app against an on-prem Jira Data Center/Server
# instance, which uses REST API v2 and Bearer Personal Access Tokens
# instead of Cloud's email+API-token Basic auth. Defaults to "cloud" so
# normal/packaged runs stay spec-compliant unless someone deliberately
# opts in.
DEPLOYMENT_TYPE = os.environ.get("JIRA_TRAY_DEPLOYMENT", "cloud").strip().lower()
if DEPLOYMENT_TYPE not in ("cloud", "datacenter"):
    raise RuntimeError(
        f"Invalid JIRA_TRAY_DEPLOYMENT={DEPLOYMENT_TYPE!r}; must be 'cloud' "
        "(default, per SPECIFICATION.md) or 'datacenter' (opt-in on-prem "
        "testing mode)."
    )
IS_DATACENTER = DEPLOYMENT_TYPE == "datacenter"

# Jira Cloud uses REST API v3; on-prem Data Center/Server only exposes v2.
API_BASE = (
    f"{JIRA_SITE_URL}/rest/api/{'2' if IS_DATACENTER else '3'}" if JIRA_SITE_URL else ""
)

# Where users create their own Jira Cloud API token (never a password).
API_TOKEN_SETTINGS_URL = "https://id.atlassian.com/manage-profile/security/api-tokens"

# --- Auth mode ------------------------------------------------------------
# Some Atlassian orgs' authentication policy blocks Basic Auth/API tokens
# entirely (returns 401 with `Www-Authenticate: OAuth`), requiring real
# Atlassian OAuth 2.0 (3LO) sign-in instead. Defaults to "token" (the
# simpler, spec-described flow); set JIRA_TRAY_AUTH_MODE=oauth to opt in.
AUTH_MODE = os.environ.get(
    "JIRA_TRAY_AUTH_MODE", "token" if IS_DATACENTER else team_defaults.TEAM_AUTH_MODE
).strip().lower()
if AUTH_MODE not in ("token", "oauth"):
    raise RuntimeError(f"Invalid JIRA_TRAY_AUTH_MODE={AUTH_MODE!r}; must be 'token' or 'oauth'.")
IS_OAUTH = AUTH_MODE == "oauth"
if IS_OAUTH and IS_DATACENTER:
    raise RuntimeError("JIRA_TRAY_AUTH_MODE=oauth is only supported in Cloud mode.")

# Developer console app registration page (one-time, per-user setup step).
OAUTH_APPS_CONSOLE_URL = "https://developer.atlassian.com/console/myapps/"
# Optional team-wide OAuth app; when both are set, users skip the Client ID/Secret dialog.
OAUTH_CLIENT_ID = os.environ.get("JIRA_TRAY_OAUTH_CLIENT_ID", team_defaults.TEAM_OAUTH_CLIENT_ID).strip()
OAUTH_CLIENT_SECRET = os.environ.get("JIRA_TRAY_OAUTH_CLIENT_SECRET", team_defaults.TEAM_OAUTH_CLIENT_SECRET).strip()
OAUTH_CALLBACK_PORT = 8765
OAUTH_SCOPES = "read:jira-work read:jira-user offline_access"
OAUTH_AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
OAUTH_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
OAUTH_ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

# Optional path to a PEM CA bundle for verifying an on-prem instance's TLS
# certificate (e.g. an internal corporate CA). Ignored for Cloud, which
# uses publicly trusted certificates. Never disables verification outright:
# if unset, the system trust store is used (`requests`' default `verify=True`).
CA_BUNDLE_PATH = os.environ.get("JIRA_TRAY_CA_BUNDLE", "").strip()
REQUESTS_VERIFY = CA_BUNDLE_PATH or True


def build_search_jql() -> str:
    """Combines the optional approved channel filter with the user's own
    active-issue scope. Without a channel filter, every user simply gets
    their own assigned active issues."""
    base = "assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC"
    if not CHANNEL_JQL:
        return base
    return f"assignee = currentUser() AND ({CHANNEL_JQL}) AND statusCategory != Done ORDER BY updated DESC"


# --- Polling (section 4.3) ----------------------------------------------
MIN_POLL_INTERVAL_SECONDS = 30  # Safe minimum for any user-configurable interval.
POLL_INTERVAL_SECONDS = max(
    MIN_POLL_INTERVAL_SECONDS, int(os.environ.get("JIRA_TRAY_POLL_INTERVAL", "60"))
)
# Spread out client requests so many machines don't poll in lockstep.
POLL_JITTER_FRACTION = 0.15
# Bounded exponential backoff after consecutive poll failures (network/5xx).
# HTTP 429 instead honors the server's Retry-After header.
BACKOFF_BASE_SECONDS = 5
BACKOFF_MAX_SECONDS = 300

HTTP_TIMEOUT_SECONDS = 15

# Cap how many individual issues are listed directly in the tray menu;
# the exact count is always shown in the tooltip/status entry regardless.
MAX_MENU_ISSUES = 15


def _user_data_dir() -> str:
    """Per-OS, per-user directory for non-secret local app data (preferences
    and the minimal issue-id/timestamp de-duplication snapshot)."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME)
    if os.uname().sysname == "Darwin":  # type: ignore[attr-defined]
        return os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "jira_tray_monitor")


USER_DATA_DIR = _user_data_dir()
STATE_FILE_PATH = os.path.join(USER_DATA_DIR, "poll_state.json")
SETTINGS_FILE_PATH = os.path.join(USER_DATA_DIR, "settings.json")
