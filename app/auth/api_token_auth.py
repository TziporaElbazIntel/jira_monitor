"""Jira API-token onboarding and validation (SPECIFICATION.md 4.1).

Flow:
  1. A GUI (see `app/gui/setup_dialog.py`) explains how to create a personal
     API token at Atlassian's token settings page and collects the user's
     Atlassian account email plus the (masked) token.
  2. This module validates the pair via `GET /myself` using HTTP Basic
     authentication (email, token) - the standard Jira Cloud API-token auth
     scheme.
  3. On success, a `TokenBundle` is returned for the caller to persist via
     `credential_store.save()`.

This module takes an injected `collect_credentials` callable rather than
importing a GUI toolkit directly, so it stays testable without a display.

`config.DEPLOYMENT_TYPE == "datacenter"` is an opt-in, non-spec local-testing
mode for on-prem Jira Data Center/Server: it swaps Basic auth (email+token)
for a Bearer Personal Access Token against the same `/myself` endpoint, and
does not require an email address up front.
"""
import requests

from app import config
from app.auth.credential_store import TokenBundle
from app.http_session import session


class AuthError(Exception):
    """Credentials were missing, rejected, or Jira could not be reached."""


def _fetch_myself(email: str, api_token: str) -> dict:
    if not config.API_BASE:
        raise AuthError(
            "Jira site URL is not configured (set JIRA_TRAY_SITE_URL to your "
            "Jira site, e.g. https://your-team.atlassian.net)."
        )
    headers = {"Accept": "application/json"}
    kwargs = {"headers": headers, "timeout": config.HTTP_TIMEOUT_SECONDS, "verify": config.REQUESTS_VERIFY}
    if config.IS_DATACENTER:
        headers["Authorization"] = f"Bearer {api_token}"
    else:
        kwargs["auth"] = (email, api_token)
    try:
        resp = session.get(f"{config.API_BASE}/myself", **kwargs)
    except requests.RequestException as exc:
        raise AuthError(f"Could not reach Jira: {exc}") from exc

    if resp.status_code == 401:
        raise AuthError("Jira rejected this credential (invalid, expired, or revoked).")
    if resp.status_code == 403:
        raise AuthError("Jira denied access for this account (insufficient permissions).")
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise AuthError(f"Jira returned an error: {exc}") from exc
    return resp.json()


def run_setup_flow(collect_credentials) -> TokenBundle:
    """`collect_credentials` is a zero-arg callable returning (email,
    api_token), typically backed by a GUI dialog. In datacenter mode, email
    is optional (the PAT alone authenticates); Cloud still requires both."""
    email, api_token = collect_credentials()
    email = (email or "").strip()
    api_token = (api_token or "").strip()
    if config.IS_DATACENTER:
        if not api_token:
            raise AuthError("A Personal Access Token is required.")
    elif not email or not api_token:
        raise AuthError("Email and API token are both required.")

    profile = _fetch_myself(email, api_token)
    return TokenBundle(
        email=email or profile.get("emailAddress", ""),
        api_token=api_token,
        account_id=profile.get("accountId") or profile.get("key") or profile.get("name", ""),
        display_name=profile.get("displayName", ""),
    )


def verify_token(bundle: TokenBundle) -> TokenBundle:
    """Re-checks a stored token is still valid; raises AuthError if not."""
    profile = _fetch_myself(bundle.email, bundle.api_token)
    bundle.display_name = profile.get("displayName", bundle.display_name)
    bundle.account_id = profile.get("accountId", bundle.account_id)
    return bundle
