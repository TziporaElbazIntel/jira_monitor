"""Tests for oauth_flow: Atlassian OAuth 2.0 (3LO) sign-in, refresh, and verify."""
from unittest.mock import Mock, patch

import pytest

from app.auth import oauth_flow
from app.auth.credential_store import TokenBundle


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr("app.config.OAUTH_CALLBACK_PORT", 8765)
    monkeypatch.setattr("app.config.OAUTH_SCOPES", "read:jira-work read:jira-user offline_access")
    monkeypatch.setattr("app.config.OAUTH_AUTHORIZE_URL", "https://auth.atlassian.com/authorize")
    monkeypatch.setattr("app.config.OAUTH_TOKEN_URL", "https://auth.atlassian.com/oauth/token")
    monkeypatch.setattr(
        "app.config.OAUTH_ACCESSIBLE_RESOURCES_URL",
        "https://api.atlassian.com/oauth/token/accessible-resources",
    )
    yield


def _resp(status_code=200, json_data=None):
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


def test_empty_client_credentials_raise_without_opening_browser():
    with patch("app.auth.oauth_flow.webbrowser.open") as mock_open:
        with pytest.raises(oauth_flow.AuthError):
            oauth_flow.run_setup_flow("", "")
    mock_open.assert_not_called()


def test_successful_setup_flow_returns_oauth_bundle():
    token_resp = _resp(json_data={"access_token": "atok", "refresh_token": "rtok", "expires_in": 3600})
    sites_resp = _resp(
        json_data=[{"id": "cloud-123", "url": "https://example.atlassian.net", "name": "Example"}]
    )
    with patch("app.auth.oauth_flow.webbrowser.open") as mock_open, patch(
        "app.auth.oauth_flow._wait_for_redirect", return_value="auth-code"
    ), patch("app.auth.oauth_flow.session.post", return_value=token_resp) as mock_post, patch(
        "app.auth.oauth_flow.session.get", return_value=sites_resp
    ) as mock_get:
        bundle = oauth_flow.run_setup_flow("client-id", "client-secret")

    mock_open.assert_called_once()
    assert bundle.auth_mode == "oauth"
    assert bundle.access_token == "atok"
    assert bundle.refresh_token == "rtok"
    assert bundle.cloud_id == "cloud-123"
    assert bundle.site_url == "https://example.atlassian.net"
    assert bundle.display_name == "Example"
    assert bundle.client_id == "client-id"
    assert bundle.client_secret == "client-secret"

    post_kwargs = mock_post.call_args.kwargs
    assert post_kwargs["json"]["grant_type"] == "authorization_code"
    assert post_kwargs["json"]["code"] == "auth-code"
    get_kwargs = mock_get.call_args.kwargs
    assert get_kwargs["headers"]["Authorization"] == "Bearer atok"


def test_setup_flow_raises_when_no_accessible_site():
    token_resp = _resp(json_data={"access_token": "atok"})
    sites_resp = _resp(json_data=[])
    with patch("app.auth.oauth_flow.webbrowser.open"), patch(
        "app.auth.oauth_flow._wait_for_redirect", return_value="auth-code"
    ), patch("app.auth.oauth_flow.session.post", return_value=token_resp), patch(
        "app.auth.oauth_flow.session.get", return_value=sites_resp
    ):
        with pytest.raises(oauth_flow.AuthError):
            oauth_flow.run_setup_flow("client-id", "client-secret")


def test_setup_flow_raises_on_denied_or_failed_redirect():
    with patch("app.auth.oauth_flow.webbrowser.open"), patch(
        "app.auth.oauth_flow._wait_for_redirect", side_effect=oauth_flow.AuthError("denied")
    ):
        with pytest.raises(oauth_flow.AuthError):
            oauth_flow.run_setup_flow("client-id", "client-secret")


def test_token_exchange_failure_raises_auth_error():
    with patch("app.auth.oauth_flow.webbrowser.open"), patch(
        "app.auth.oauth_flow._wait_for_redirect", return_value="auth-code"
    ), patch("app.auth.oauth_flow.session.post", return_value=_resp(status_code=400)):
        with pytest.raises(oauth_flow.AuthError):
            oauth_flow.run_setup_flow("client-id", "client-secret")


def test_refresh_access_token_mutates_and_returns_bundle():
    bundle = TokenBundle(
        email="",
        api_token="",
        auth_mode="oauth",
        client_id="client-id",
        client_secret="client-secret",
        access_token="old-access",
        refresh_token="old-refresh",
        cloud_id="cloud-123",
        site_url="https://example.atlassian.net",
    )
    token_resp = _resp(json_data={"access_token": "new-access", "refresh_token": "new-refresh"})
    with patch("app.auth.oauth_flow.session.post", return_value=token_resp) as mock_post:
        result = oauth_flow.refresh_access_token(bundle)

    assert result is bundle
    assert bundle.access_token == "new-access"
    assert bundle.refresh_token == "new-refresh"
    post_kwargs = mock_post.call_args.kwargs
    assert post_kwargs["json"]["grant_type"] == "refresh_token"
    assert post_kwargs["json"]["refresh_token"] == "old-refresh"


def test_refresh_access_token_keeps_old_refresh_token_if_not_rotated():
    bundle = TokenBundle(
        email="",
        api_token="",
        auth_mode="oauth",
        client_id="client-id",
        client_secret="client-secret",
        access_token="old-access",
        refresh_token="old-refresh",
    )
    token_resp = _resp(json_data={"access_token": "new-access"})
    with patch("app.auth.oauth_flow.session.post", return_value=token_resp):
        oauth_flow.refresh_access_token(bundle)
    assert bundle.refresh_token == "old-refresh"


def test_verify_token_delegates_to_refresh():
    bundle = TokenBundle(email="", api_token="", auth_mode="oauth", refresh_token="rtok")
    with patch("app.auth.oauth_flow.refresh_access_token", return_value=bundle) as mock_refresh:
        result = oauth_flow.verify_token(bundle)
    mock_refresh.assert_called_once_with(bundle)
    assert result is bundle


def test_refresh_raises_when_revoked():
    bundle = TokenBundle(email="", api_token="", auth_mode="oauth", refresh_token="revoked")
    with patch("app.auth.oauth_flow.session.post", return_value=_resp(status_code=400)):
        with pytest.raises(oauth_flow.AuthError):
            oauth_flow.refresh_access_token(bundle)
