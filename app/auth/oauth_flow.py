"""Atlassian OAuth 2.0 (3LO) sign-in for Jira Cloud orgs that block Basic
Auth/API tokens (`Www-Authenticate: OAuth` on token requests).

The user signs in via their normal browser (same SSO they already use for
Jira), exactly like the "Authorization Code Grant" flow documented at
https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/.
This requires a one-time app registration by the user at
`config.OAUTH_APPS_CONSOLE_URL` to obtain a Client ID and Secret (see
README). No scopes beyond read-only Jira access are requested.
"""
import http.server
import secrets
import threading
import urllib.parse
import webbrowser

import requests

from app import config
from app.auth.credential_store import TokenBundle
from app.http_session import session


class AuthError(Exception):
    """OAuth sign-in failed, was denied, or Atlassian could not be reached."""


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self.server.result = {
            "code": (params.get("code") or [None])[0],
            "state": (params.get("state") or [None])[0],
            "error": (params.get("error") or [None])[0],
        }
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body>Signed in - you can close this window and return "
            b"to Jira Tray Monitor.</body></html>"
        )

    def log_message(self, *_args):  # don't spam stderr with HTTP access logs
        pass


def _wait_for_redirect(port: int, expected_state: str, timeout: int) -> str:
    server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.result = None
    server.timeout = timeout
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(timeout + 5)
    server.server_close()
    result = server.result
    if not result:
        raise AuthError("Sign-in timed out waiting for the browser.")
    if result["error"]:
        raise AuthError(f"Sign-in was denied or failed: {result['error']}")
    if not result["code"] or result["state"] != expected_state:
        raise AuthError("Sign-in response was invalid (state mismatch).")
    return result["code"]


def _post_token(payload: dict) -> dict:
    try:
        resp = session.post(
            config.OAUTH_TOKEN_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=config.HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise AuthError(f"Could not reach Atlassian: {exc}") from exc
    if resp.status_code != 200:
        raise AuthError(f"Atlassian rejected the sign-in (HTTP {resp.status_code}).")
    return resp.json()


def _resolve_cloud_site(access_token: str) -> dict:
    try:
        resp = session.get(
            config.OAUTH_ACCESSIBLE_RESOURCES_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=config.HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise AuthError(f"Could not reach Atlassian: {exc}") from exc
    if resp.status_code != 200:
        raise AuthError("Could not look up your accessible Jira sites.")
    sites = resp.json()
    if not sites:
        raise AuthError("Your Atlassian account granted no accessible Jira site.")
    site = sites[0]
    return {"cloud_id": site["id"], "site_url": site["url"], "name": site.get("name", "")}


def run_setup_flow(client_id: str, client_secret: str) -> TokenBundle:
    """Opens the user's browser for Atlassian sign-in/consent, exchanges the
    resulting code for tokens, and resolves the Jira Cloud site."""
    client_id = (client_id or "").strip()
    client_secret = (client_secret or "").strip()
    if not client_id or not client_secret:
        raise AuthError("Client ID and Client Secret are both required.")

    redirect_uri = f"http://localhost:{config.OAUTH_CALLBACK_PORT}/callback"
    state = secrets.token_urlsafe(24)
    authorize_url = config.OAUTH_AUTHORIZE_URL + "?" + urllib.parse.urlencode(
        {
            "audience": "api.atlassian.com",
            "client_id": client_id,
            "scope": config.OAUTH_SCOPES,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
    )
    webbrowser.open(authorize_url)
    code = _wait_for_redirect(config.OAUTH_CALLBACK_PORT, state, timeout=180)
    tokens = _post_token(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
    )
    site = _resolve_cloud_site(tokens["access_token"])
    return TokenBundle(
        email="",
        api_token="",
        auth_mode="oauth",
        client_id=client_id,
        client_secret=client_secret,
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token", ""),
        cloud_id=site["cloud_id"],
        site_url=site["site_url"],
        display_name=site.get("name") or site["site_url"],
    )


def refresh_access_token(bundle: TokenBundle) -> TokenBundle:
    """Exchanges the stored (rotating) refresh token for a new access token.
    Mutates and returns `bundle`; the caller must persist it afterwards."""
    tokens = _post_token(
        {
            "grant_type": "refresh_token",
            "client_id": bundle.client_id,
            "client_secret": bundle.client_secret,
            "refresh_token": bundle.refresh_token,
        }
    )
    bundle.access_token = tokens["access_token"]
    bundle.refresh_token = tokens.get("refresh_token", bundle.refresh_token)
    return bundle


def verify_token(bundle: TokenBundle) -> TokenBundle:
    """Re-checks a stored OAuth session is still valid by refreshing it;
    raises AuthError if the refresh token has expired or was revoked."""
    return refresh_access_token(bundle)
