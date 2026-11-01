"""Tests for api_token_auth: GUI-agnostic credential collection + /myself validation."""
from unittest.mock import Mock, patch

import pytest

from app.auth import api_token_auth
from app.auth.credential_store import TokenBundle


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr("app.config.JIRA_SITE_URL", "https://example.atlassian.net")
    monkeypatch.setattr("app.config.API_BASE", "https://example.atlassian.net/rest/api/3")
    yield


def _resp(status_code=200, json_data=None):
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = Mock()
    return resp


def test_successful_setup_validates_via_myself_with_basic_auth():
    resp = _resp(json_data={"accountId": "acc-1", "displayName": "Tester"})
    with patch("app.auth.api_token_auth.session.get", return_value=resp) as mock_get:
        bundle = api_token_auth.run_setup_flow(lambda: ("user@example.com", "tok-123"))
    assert bundle == TokenBundle(email="user@example.com", api_token="tok-123", account_id="acc-1", display_name="Tester")
    _, kwargs = mock_get.call_args
    assert kwargs["auth"] == ("user@example.com", "tok-123")
    assert mock_get.call_args[0][0] == "https://example.atlassian.net/rest/api/3/myself"


def test_empty_credentials_raise_without_calling_jira():
    with patch("app.auth.api_token_auth.session.get") as mock_get:
        with pytest.raises(api_token_auth.AuthError):
            api_token_auth.run_setup_flow(lambda: ("", ""))
    mock_get.assert_not_called()


def test_401_raises_auth_error():
    with patch("app.auth.api_token_auth.session.get", return_value=_resp(status_code=401)):
        with pytest.raises(api_token_auth.AuthError):
            api_token_auth.run_setup_flow(lambda: ("user@example.com", "bad-token"))


def test_missing_site_url_raises_actionable_error(monkeypatch):
    monkeypatch.setattr("app.config.API_BASE", "")
    with pytest.raises(api_token_auth.AuthError):
        api_token_auth.run_setup_flow(lambda: ("user@example.com", "tok"))


def test_verify_token_refreshes_profile():
    bundle = TokenBundle(email="user@example.com", api_token="tok-123", account_id="old", display_name="Old Name")
    resp = _resp(json_data={"accountId": "old", "displayName": "New Name"})
    with patch("app.auth.api_token_auth.session.get", return_value=resp):
        updated = api_token_auth.verify_token(bundle)
    assert updated.display_name == "New Name"


def test_datacenter_mode_uses_bearer_auth_without_requiring_email(monkeypatch):
    monkeypatch.setattr("app.config.IS_DATACENTER", True)
    monkeypatch.setattr("app.config.API_BASE", "https://jira.example.com/rest/api/2")
    resp = _resp(json_data={"displayName": "Tester", "name": "tester", "emailAddress": "tester@example.com"})
    with patch("app.auth.api_token_auth.session.get", return_value=resp) as mock_get:
        bundle = api_token_auth.run_setup_flow(lambda: ("", "pat-456"))
    assert bundle.api_token == "pat-456"
    assert bundle.email == "tester@example.com"
    assert bundle.account_id == "tester"
    _, kwargs = mock_get.call_args
    assert "auth" not in kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer pat-456"
    assert mock_get.call_args[0][0] == "https://jira.example.com/rest/api/2/myself"


def test_datacenter_mode_rejects_empty_token(monkeypatch):
    monkeypatch.setattr("app.config.IS_DATACENTER", True)
    with patch("app.auth.api_token_auth.session.get") as mock_get:
        with pytest.raises(api_token_auth.AuthError):
            api_token_auth.run_setup_flow(lambda: ("", ""))
    mock_get.assert_not_called()
