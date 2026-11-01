# Jira Cloud Tray Monitor Specification

## 1. Purpose

A lightweight desktop tray application for Windows, macOS, and Linux. It shows a user's active Jira Cloud issues from a configured source channel and notifies them when a new issue matches that filter.

The app connects directly to Jira using each user's own credentials. It has no shared backend, webhook receiver, push service, or server-side database.

## 2. Decisions and Release Gate

- Jira deployment: Atlassian Jira Cloud.
- Audience: internal team only; no public distribution is planned.
- Authentication direction: each user provides their own Atlassian account email and API token. Do not use a shared or service-account token.
- Credential storage: use the operating system's credential manager only. Never store tokens in app files, settings, environment variables, logs, or crash reports.
- Backend: none. The desktop client polls Jira directly.
- Poll interval: default 60 seconds, with random jitter to spread requests across clients. Any user-configurable interval must have a safe minimum.
- Approval gate: Atlassian currently warns against distributed apps that collect users' API tokens. Obtain internal security/policy approval before collecting tokens or rolling out the app. If this approach is not approved, stop and choose an approved Atlassian integration model.
- Required before release: approved Jira site URL, exact source-channel JQL, supported OS versions, and behavior for tickets that arrive while the app is closed.

## 3. Users and User Stories

- End user: installs/runs the app, connects their own Jira account, views matching issues, controls notifications, and can sign out.
- Maintainer: configures the approved tenant and channel filter, builds and signs platform-specific releases, and provides upgrade and removal instructions. The maintainer must not receive user tokens or issue contents.

Users must be able to:

1. Connect a Jira account once and have the app remember the token securely on that OS account.
2. See the active issue count and matching issue list from the tray.
3. Receive one desktop notification when an issue newly enters the configured results, without backlog spam on initial setup.
4. Open an issue in Jira, refresh immediately, mute/unmute notifications, and exit.
5. See whether Jira is reachable and whether displayed results are current or stale.
6. Remove saved credentials and find instructions for revoking the token in Atlassian.

## 4. Functional Requirements

### 4.1 Onboarding and authentication

- First launch uses a GUI; packaged no-console builds must not depend on terminal input.
- Explain that the user must create an individual Jira Cloud API token and provide the Atlassian account email associated with it.
- Mask token input. Validate credentials with Jira Cloud `/rest/api/3/myself` before saving.
- On success, show the authenticated account identity and begin monitoring.
- Invalid credentials, insufficient permissions, unavailable secure storage, network errors, and tenant errors must produce actionable messages without exposing secrets.
- Provide a reauthentication flow after token rejection/revocation.
- Sign-out deletes the token from the OS credential manager and clears local issue/deduplication state.

### 4.2 Jira Cloud queries and issue list

- Use HTTPS Basic authentication with the user's Atlassian email and API token, and Jira Cloud REST API v3.
- Search for the current user's active issues using an approved JQL query that includes the confirmed source-channel filter and excludes completed issues.
- The exact channel clause is configuration supplied by the product owner; do not invent it.
- Request only fields needed by the UI and notification flow, such as issue ID, key, summary, status, and updated timestamp.
- Follow pagination until all matching results are retrieved. Deduplicate by immutable issue ID; display the Jira issue key.
- Selecting an issue opens its canonical URL on the configured Jira Cloud site.
- Jira permissions remain authoritative: the app can only show issues the authenticated user can access.

### 4.3 Polling and notifications

- Poll immediately after successful setup, then at the configured interval (default 60 seconds).
- Add random startup and interval jitter so clients do not synchronize their requests.
- The first successful search creates a silent baseline and does not notify for existing issues.
- Notify once when an issue transitions from absent in the previous successful result to present in the current result. An edit to an issue already in the results is not a new arrival.
- Persist only the minimum issue IDs and timestamps needed to deduplicate alerts across application restarts. Do not persist issue descriptions or comments.
- After restart, compare against saved state. The product owner must choose whether to notify for currently matching issues first observed since the last successful poll and define a maximum notification age/window.
- A client-only poller cannot detect issues that enter and leave the query while the app is closed. The app must document this limitation.
- Muting suppresses alerts only; polling and the issue list continue.
- Manual and scheduled refreshes must be serialized and must not overlap.
- Notification failures must not stop polling. Notification text should minimize sensitive content; default to issue key and short summary subject to company policy.

### 4.4 Resilience and status

- Expose clear states: setup required, connecting, connected, stale/offline, authentication required, and error.
- On network loss or VPN disconnect, keep the last successful issue list visible and mark it stale. Do not retry rapidly.
- On HTTP 401, stop normal polling and request reauthentication. On HTTP 403, display a permissions-related message.
- On HTTP 429, honor `Retry-After`. Use bounded exponential backoff with jitter for other retryable network and 5xx errors.
- After sleep/wake or network restoration, run one refresh rather than replaying all missed polling intervals.
- Use request timeouts. Keep TLS certificate validation enabled; never disable it.
- Stop worker threads cleanly on exit and prevent duplicate app instances where practical.

### 4.5 Tray controls and preferences

- Tray icon conveys the active issue count. The rendered badge may cap at a stable display value for large counts, while the menu shows the exact count.
- Menu includes active issue entries, connection/stale status, Refresh Now, Mute/Unmute Notifications, Account/Settings, and Exit.
- Preferences may include poll interval, mute state, and optional launch-at-login. JQL editing is restricted to the approved configuration policy.
- Launch-at-login is opt-in, reversible, and implemented separately for each supported OS. Do not register silently during first launch.

## 5. Security and Privacy

- Use per-user Jira permissions and read-only API access. The app must not create, update, or delete Jira data.
- Store the token only in Windows Credential Manager, macOS Keychain, or Linux Secret Service through the platform keyring integration.
- If secure credential storage is unavailable, fail closed with a clear message. Never fall back to plaintext token storage.
- Keep TLS verification enabled. Do not embed secrets in the binary or source, and never log tokens.
- Local app data may contain non-secret preferences and minimal issue IDs/timestamps for notification deduplication. Protect data with normal per-user OS permissions and offer a clear-data/sign-out action.
- No telemetry by default. Any future telemetry must be opt-in and exclude credentials, issue keys, summaries, and descriptions.
- Document token revocation and the effect of uninstalling the app on stored credentials.
- Record internal approval for the API-token approach before implementation or release.

## 6. Non-Functional Requirements

- Lightweight idle resource use; no visible console window in packaged builds.
- UI remains responsive while API calls run in a background worker.
- A failed API request must not terminate the tray process.
- Validate separately on Windows, macOS, and Linux. Build PyInstaller artifacts on their target OS.
- Normal operation requires network access to Jira Cloud and an available platform credential service; there is no server dependency.
- Optimize API usage with narrow JQL, minimal fields, pagination, jitter, and rate-limit handling.

## 7. Proposed Component Boundaries

- `app/config.py`: tenant, approved JQL/channel filter, timeouts, poll interval, and non-secret preferences.
- `app/auth/pat_auth.py` or renamed API-token auth module: GUI token collection and `/myself` validation.
- `app/auth/credential_store.py`: platform keyring get/set/delete; no plaintext fallback.
- `app/jira_client.py`: authenticated Cloud REST v3 requests, JQL search, pagination, response normalization, and rate-limit handling.
- `app/poller.py`: serialized scheduling, durable snapshot/delta state, retry/backoff, and status events.
- `app/tray_app.py` and `app/notifier.py`: tray display, issue actions, user controls, and desktop notifications.
- `app/main.py`: GUI setup, component wiring, worker lifecycle, and clean shutdown.
- New platform helpers: opt-in startup integration and platform-specific user-data paths, if needed.
- New `tests/` directory: deterministic tests using mocked Jira HTTP, keyring, and tray dependencies.

## 8. Acceptance Criteria

1. A clean-profile packaged build launches without a console and provides GUI-based setup.
2. Credentials are validated before saving and never appear in plaintext files, settings, or logs.
3. The app refuses to save credentials if secure OS storage is unavailable.
4. The configured JQL returns the intended active source-channel issues; pagination retrieves all matches; issue links open on the correct tenant.
5. Initial setup establishes a silent baseline. A newly matching issue notifies once. Repeated polls and restarts do not duplicate the alert.
6. Manual and scheduled polls cannot overlap. Offline/VPN loss leaves results visible as stale and recovers after connectivity returns.
7. HTTP 401 requests reauthentication; 403 reports a permission problem; 429 honors `Retry-After`; transient failures back off without busy loops.
8. Mute suppresses notifications without stopping polling. Refresh triggers a serialized immediate poll. Exit stops workers cleanly.
9. Optional startup registration can be enabled and removed by the user.
10. Unit tests use fake data only. Packaged builds pass manual verification on each supported OS before pilot.
11. Internal approval is recorded and a small-team pilot signs off before wider internal rollout.

## 9. Test Strategy

- Unit tests: credential storage success/failure/clear; API authentication and `/myself`; JQL construction; pagination; response normalization; baseline/delta persistence; poll serialization; 401/403/429/5xx/network behavior; mute; graceful shutdown.
- Integration test: opt-in live check against an approved Jira Cloud tenant using a disposable test user/token. Never run load or rate-limit tests against production.
- Manual OS matrix: first-run setup, keyring, notifications, tray actions, sleep/wake, VPN/network disconnect and recovery, optional startup, upgrade/uninstall, and no-console packaging on every supported OS.
- Pilot: small internal cohort validates JQL, notification behavior, token policy, and support/revocation steps.

## 10. Out of Scope for First Release

- Central webhook receiver, push service, shared backend, or server-side database.
- Guaranteed delivery of events while the app is closed.
- Jira issue writes, comments, transitions, or attachment access.
- Public distribution or Atlassian Marketplace publication.
- Multiple Jira tenants unless separately required and designed.
- Jenkins/GHE Jira migration or unrelated DevOps changes.

## 11. Open Decisions Before Implementation

1. What is the approved Jira Cloud tenant URL?
2. What exact JQL identifies the source channel, and who approves it?
3. Has internal security/policy approved collecting individual API tokens in this internal utility?
4. After downtime, should the app notify about current matches newer than the last saved snapshot, show a count-only summary, or remain silent?
5. What minimum versions of Windows, macOS, and Linux are supported? Are tray and desktop notifications required on all three?
6. Are poll interval and channel JQL fixed by release configuration or user-configurable?
