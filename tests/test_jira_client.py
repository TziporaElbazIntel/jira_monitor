"""Tests for JiraClient: Basic auth, Cloud v3 pagination, and HTTP status handling."""
from unittest.mock import Mock, patch

import pytest

from app.auth.credential_store import TokenBundle
from app.jira_client import (
    AuthRequiredError,
    JiraClient,
    PermissionDeniedError,
    RateLimitedError,
)


def _bundle():
    return TokenBundle(email="user@example.com", api_token="tok-123", account_id="acc", display_name="Tester")


def _resp(status_code=200, json_data=None, headers=None):
    resp = Mock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = json_data or {}
    resp.raise_for_status = Mock()
    return resp


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr("app.config.JIRA_SITE_URL", "https://example.atlassian.net")
    monkeypatch.setattr("app.config.API_BASE", "https://example.atlassian.net/rest/api/3")
    monkeypatch.setattr("app.config.CHANNEL_JQL", 'project = ABC')
    yield


def test_uses_basic_auth_with_email_and_token():
    client = JiraClient(_bundle())
    page = _resp(json_data={"issues": []})
    with patch("app.jira_client.session.post", return_value=page) as mock_post:
        client.get_active_issues()
    _, kwargs = mock_post.call_args
    assert kwargs["auth"] == ("user@example.com", "tok-123")


def test_hits_cloud_v3_search_jql_endpoint():
    client = JiraClient(_bundle())
    page = _resp(json_data={"issues": []})
    with patch("app.jira_client.session.post", return_value=page) as mock_post:
        client.get_active_issues()
    url = mock_post.call_args[0][0]
    assert url == "https://example.atlassian.net/rest/api/3/search/jql"


def test_pagination_follows_all_pages():
    client = JiraClient(_bundle())
    page1 = _resp(json_data={"issues": [{"id": "1", "key": "A-1"}, {"id": "2", "key": "A-2"}], "nextPageToken": "tok2"})
    page2 = _resp(json_data={"issues": [{"id": "3", "key": "A-3"}]})
    with patch("app.jira_client.session.post", side_effect=[page1, page2]) as mock_post:
        issues = client.get_active_issues()
    assert [i["key"] for i in issues] == ["A-1", "A-2", "A-3"]
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[1].kwargs["json"]["nextPageToken"] == "tok2"


def test_pagination_stops_when_no_next_page_token():
    client = JiraClient(_bundle())
    page = _resp(json_data={"issues": [{"id": "1", "key": "A-1"}]})
    with patch("app.jira_client.session.post", return_value=page) as mock_post:
        issues = client.get_active_issues()
    assert len(issues) == 1
    assert mock_post.call_count == 1


def test_401_raises_auth_required():
    client = JiraClient(_bundle())
    with patch("app.jira_client.session.post", return_value=_resp(status_code=401)):
        with pytest.raises(AuthRequiredError):
            client.get_active_issues()


def test_403_raises_permission_denied():
    client = JiraClient(_bundle())
    with patch("app.jira_client.session.post", return_value=_resp(status_code=403)):
        with pytest.raises(PermissionDeniedError):
            client.get_active_issues()


def test_429_raises_rate_limited_with_retry_after():
    client = JiraClient(_bundle())
    resp = _resp(status_code=429, headers={"Retry-After": "7"})
    with patch("app.jira_client.session.post", return_value=resp):
        with pytest.raises(RateLimitedError) as exc_info:
            client.get_active_issues()
    assert exc_info.value.retry_after == 7.0


def test_issue_url_points_at_configured_site():
    client = JiraClient(_bundle())
    assert client.issue_url("ABC-1") == "https://example.atlassian.net/browse/ABC-1"


def test_verify_param_defaults_to_true_without_ca_bundle(monkeypatch):
    monkeypatch.setattr("app.config.REQUESTS_VERIFY", True)
    client = JiraClient(_bundle())
    page = _resp(json_data={"issues": []})
    with patch("app.jira_client.session.post", return_value=page) as mock_post:
        client.get_active_issues()
    assert mock_post.call_args[1]["verify"] is True


def test_datacenter_mode_uses_bearer_auth_and_v2_endpoint(monkeypatch):
    monkeypatch.setattr("app.config.IS_DATACENTER", True)
    monkeypatch.setattr("app.config.API_BASE", "https://jira.example.com/rest/api/2")
    monkeypatch.setattr("app.config.REQUESTS_VERIFY", "/etc/ssl/internal-ca.pem")
    client = JiraClient(_bundle())
    page = _resp(json_data={"issues": [], "total": 0})
    with patch("app.jira_client.session.get", return_value=page) as mock_get:
        client.get_active_issues()
    args, kwargs = mock_get.call_args
    assert args[0] == "https://jira.example.com/rest/api/2/search"
    assert "auth" not in kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer tok-123"
    assert kwargs["verify"] == "/etc/ssl/internal-ca.pem"


def _oauth_bundle(access_token="atok", refresh_token="rtok"):
    return TokenBundle(
        email="",
        api_token="",
        auth_mode="oauth",
        client_id="client-id",
        client_secret="client-secret",
        access_token=access_token,
        refresh_token=refresh_token,
        cloud_id="cloud-123",
        site_url="https://example.atlassian.net",
        display_name="Example",
    )


def test_oauth_mode_uses_bearer_token_and_cloud_scoped_endpoint():
    client = JiraClient(_oauth_bundle())
    page = _resp(json_data={"issues": []})
    with patch("app.jira_client.session.post", return_value=page) as mock_post:
        client.get_active_issues()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.atlassian.com/ex/jira/cloud-123/rest/api/3/search/jql"
    assert "auth" not in kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer atok"


def test_oauth_mode_issue_url_uses_resolved_site_url():
    client = JiraClient(_oauth_bundle())
    assert client.issue_url("ABC-1") == "https://example.atlassian.net/browse/ABC-1"


def test_oauth_mode_refreshes_and_retries_once_on_401():
    bundle = _oauth_bundle()
    client = JiraClient(bundle)
    unauthorized = _resp(status_code=401)
    success = _resp(json_data={"issues": []})
    refreshed = _oauth_bundle(access_token="new-atok", refresh_token="new-rtok")
    with patch("app.jira_client.session.post", side_effect=[unauthorized, success]) as mock_post, patch(
        "app.jira_client.oauth_flow.refresh_access_token", return_value=refreshed
    ) as mock_refresh:
        client.get_active_issues()
    mock_refresh.assert_called_once_with(bundle)
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer new-atok"


def test_oauth_mode_raises_auth_required_if_still_401_after_refresh():
    bundle = _oauth_bundle()
    client = JiraClient(bundle)
    unauthorized = _resp(status_code=401)
    with patch("app.jira_client.session.post", return_value=unauthorized), patch(
        "app.jira_client.oauth_flow.refresh_access_token", return_value=_oauth_bundle()
    ):
        with pytest.raises(AuthRequiredError):
            client.get_active_issues()


def test_oauth_mode_calls_on_token_refreshed_callback():
    bundle = _oauth_bundle()
    refreshed = _oauth_bundle(access_token="new-atok")
    on_refreshed = Mock()
    client = JiraClient(bundle, on_token_refreshed=on_refreshed)
    unauthorized = _resp(status_code=401)
    success = _resp(json_data={"issues": []})
    with patch("app.jira_client.session.post", side_effect=[unauthorized, success]), patch(
        "app.jira_client.oauth_flow.refresh_access_token", return_value=refreshed
    ):
        client.get_active_issues()
    on_refreshed.assert_called_once_with(refreshed)
