"""Thin wrapper around the Jira REST API for the signed-in user.

Uses HTTPS Basic auth with the user's Atlassian email + personal API token
for Jira Cloud (SPECIFICATION.md 4.2). Read-only: this client only ever
issues GETs.

`config.DEPLOYMENT_TYPE == "datacenter"` is an opt-in, non-spec local-testing
mode for on-prem Jira Data Center/Server: it uses Bearer Personal Access
Token auth against REST API v2 instead (`config.API_BASE` is already
versioned accordingly) and honors an optional custom CA bundle
(`config.REQUESTS_VERIFY`) for internally-signed TLS certificates.

`bundle.auth_mode == "oauth"` (see `app/auth/oauth_flow.py`) is for orgs
whose authentication policy blocks Basic Auth/API tokens entirely: it uses
a Bearer access token against `https://api.atlassian.com/ex/jira/{cloud_id}`
instead, and transparently refreshes that access token once on a 401.
"""
from typing import Callable, List, Optional

from app import config
from app.auth import oauth_flow
from app.auth.credential_store import TokenBundle
from app.http_session import session


class JiraApiError(Exception):
    """Generic/unexpected Jira API failure."""


class AuthRequiredError(JiraApiError):
    """HTTP 401: the credential was rejected, expired, or revoked."""


class PermissionDeniedError(JiraApiError):
    """HTTP 403: the authenticated user lacks permission for this request."""


class RateLimitedError(JiraApiError):
    """HTTP 429: caller should wait `retry_after` seconds before retrying."""

    def __init__(self, retry_after: Optional[float]):
        super().__init__(f"Rate limited; retry after {retry_after}s")
        self.retry_after = retry_after


class JiraClient:
    def __init__(self, bundle: TokenBundle, on_token_refreshed: Optional[Callable[[TokenBundle], None]] = None):
        self._bundle = bundle
        self._on_token_refreshed = on_token_refreshed
        self._api_base = (
            f"https://api.atlassian.com/ex/jira/{bundle.cloud_id}/rest/api/3"
            if bundle.auth_mode == "oauth"
            else config.API_BASE
        )

    def _request_kwargs(self, params: dict = None) -> dict:
        headers = {"Accept": "application/json"}
        kwargs = {
            "headers": headers,
            "params": params,
            "timeout": config.HTTP_TIMEOUT_SECONDS,
            "verify": config.REQUESTS_VERIFY,
        }
        if self._bundle.auth_mode == "oauth":
            headers["Authorization"] = f"Bearer {self._bundle.access_token}"
        elif config.IS_DATACENTER:
            headers["Authorization"] = f"Bearer {self._bundle.api_token}"
        else:
            kwargs["auth"] = (self._bundle.email, self._bundle.api_token)
        return kwargs

    def _handle_response(self, resp, retry: Callable[[], dict], _retried: bool) -> dict:
        if resp.status_code == 401:
            if self._bundle.auth_mode == "oauth" and not _retried:
                self._bundle = oauth_flow.refresh_access_token(self._bundle)
                if self._on_token_refreshed:
                    self._on_token_refreshed(self._bundle)
                return retry()
            raise AuthRequiredError("Jira rejected the saved credential (invalid, expired, or revoked).")
        if resp.status_code == 403:
            raise PermissionDeniedError("Jira denied access; the account lacks permission for this request.")
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise RateLimitedError(float(retry_after) if retry_after else None)
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str, params: dict = None, _retried: bool = False) -> dict:
        resp = session.get(f"{self._api_base}{path}", **self._request_kwargs(params))
        return self._handle_response(resp, lambda: self._get(path, params, _retried=True), _retried)

    def _post(self, path: str, json_body: dict, _retried: bool = False) -> dict:
        kwargs = self._request_kwargs()
        kwargs.pop("params", None)
        resp = session.post(f"{self._api_base}{path}", json=json_body, **kwargs)
        return self._handle_response(resp, lambda: self._post(path, json_body, _retried=True), _retried)

    def get_active_issues(self) -> List[dict]:
        """Fetch all matching issues for the approved source-channel JQL,
        following pagination until every match is retrieved. Fields are
        narrowed to what the UI/notification flow needs.

        Cloud uses the enhanced JQL search endpoint (`/search/jql`, cursor
        pagination via `nextPageToken`) - the older `/search` endpoint
        (offset pagination via `startAt`/`total`) was removed by Atlassian
        (returns 410 Gone). Data Center/Server (REST API v2) has no
        `/search/jql` equivalent, so it keeps using the classic endpoint.
        """
        jql = config.build_search_jql()
        issues: List[dict] = []
        page_size = 100
        if config.IS_DATACENTER:
            start_at = 0
            while True:
                data = self._get(
                    "/search",
                    params={
                        "jql": jql,
                        "fields": "summary,status,updated",
                        "startAt": start_at,
                        "maxResults": page_size,
                    },
                )
                page = data.get("issues", [])
                issues.extend(page)
                total = data.get("total", len(issues))
                start_at += len(page)
                if not page or start_at >= total:
                    break
        else:
            next_page_token = None
            while True:
                body = {"jql": jql, "fields": ["summary", "status", "updated"], "maxResults": page_size}
                if next_page_token:
                    body["nextPageToken"] = next_page_token
                data = self._post("/search/jql", body)
                page = data.get("issues", [])
                issues.extend(page)
                next_page_token = data.get("nextPageToken")
                if not page or not next_page_token:
                    break
        return issues

    def issue_url(self, issue_key: str) -> str:
        site_url = self._bundle.site_url if self._bundle.auth_mode == "oauth" else config.JIRA_SITE_URL
        return f"{site_url}/browse/{issue_key}"
