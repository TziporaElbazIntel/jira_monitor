"""Headless smoke test: verifies Jira auth and the search query without
keyring/pystray/tkinter.

Usage (Jira Cloud, the spec-compliant default):
    JIRA_TRAY_SITE_URL=https://your-team.atlassian.net \
    JIRA_TRAY_CHANNEL_JQL='project = ABC' \
    python3 scripts/smoke_test.py

Usage (opt-in on-prem Jira Data Center testing mode - see README.md):
    JIRA_TRAY_DEPLOYMENT=datacenter \
    JIRA_TRAY_SITE_URL=https://jira.your-company.example \
    JIRA_TRAY_CHANNEL_JQL='project = ABC' \
    JIRA_TRAY_CA_BUNDLE=/path/to/internal-ca.pem \
    python3 scripts/smoke_test.py

Paste your Atlassian email + API token (Cloud) or Personal Access Token
(datacenter mode) when prompted. Nothing is persisted to keyring or disk -
this only prints results to stdout for a quick sanity check before running
the full tray app.
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.auth import api_token_auth


def main():
    if not config.JIRA_SITE_URL:
        print("JIRA_TRAY_SITE_URL is not set.", file=sys.stderr)
        sys.exit(1)
    if not config.CHANNEL_JQL:
        print("JIRA_TRAY_CHANNEL_JQL is not set.", file=sys.stderr)
        sys.exit(1)

    print(f"Jira site ({config.DEPLOYMENT_TYPE}): {config.JIRA_SITE_URL}")
    if config.IS_DATACENTER:
        email = input("Atlassian account email (optional, press Enter to skip): ").strip()
        token = getpass.getpass("Paste a Personal Access Token (input hidden): ").strip()
    else:
        email = input("Atlassian account email: ").strip()
        token = getpass.getpass("Paste a Jira Cloud API token (input hidden): ").strip()
    if not token or (not config.IS_DATACENTER and not email):
        print("Email and token are both required for Cloud mode; token is required "
              "for datacenter mode. Aborting.", file=sys.stderr)
        sys.exit(1)

    try:
        profile = api_token_auth._fetch_myself(email, token)
    except api_token_auth.AuthError as exc:
        print(f"Auth failed: {exc}", file=sys.stderr)
        sys.exit(1)

    identity = profile.get("accountId") or profile.get("key") or profile.get("name", "")
    print(f"Signed in as: {profile.get('displayName')} ({identity})")

    from app.auth.credential_store import TokenBundle
    from app.jira_client import JiraClient

    bundle = TokenBundle(
        email=email or profile.get("emailAddress", ""),
        api_token=token,
        account_id=identity,
        display_name=profile.get("displayName", ""),
    )
    client = JiraClient(bundle)
    issues = client.get_active_issues()
    print(f"Active matching issues: {len(issues)}")
    for issue in issues[:10]:
        print(f"  {issue['key']}: {issue['fields'].get('summary', '')}")


if __name__ == "__main__":
    main()
