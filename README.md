# Jira Tray Monitor

Lightweight system-tray app that shows your active **Jira Cloud** issues from
an approved source-channel filter, marks the tray icon with a small red
corner badge (like Microsoft Teams' notification dot) when there are open
issues, lists each matching issue directly in the
menu, and sends desktop notifications when a new issue arrives. There is no shared backend, webhook receiver, or
server-side database - the app polls Jira Cloud directly using each user's
own Atlassian account email and personal API token. See
[SPECIFICATION.md](SPECIFICATION.md) for the full product spec.

## Before you run this

This app collects individual users' Jira API tokens, which Atlassian
currently warns against for distributed apps. Per the spec's release gate,
the app **fails closed** and refuses to start until:

1. You confirm you want to continue (a one-time personal-use confirmation
   dialog, under your own control - no setup step or environment variable
   needed; your answer is remembered for next time).
2. The approved Jira Cloud site URL is configured (`JIRA_TRAY_SITE_URL`).

By default, every user simply sees their own assigned active issues
(`assignee = currentUser()`). If you want to further restrict that to a
specific project/label/channel, optionally set `JIRA_TRAY_CHANNEL_JQL`:

```bash
export JIRA_TRAY_SITE_URL="https://your-team.atlassian.net"
# Optional - narrows which of your issues show up:
export JIRA_TRAY_CHANNEL_JQL='project = ABC AND labels = "team-queue"'
```

## Optional: on-prem Jira Data Center testing mode

[SPECIFICATION.md](SPECIFICATION.md) scopes this app to **Jira Cloud only**.
As a deliberate, opt-in escape hatch for locally testing against an on-prem
Jira Data Center/Server instance (which does not speak Cloud's REST API v3
or email+API-token Basic auth), set:

```bash
export JIRA_TRAY_DEPLOYMENT=datacenter
export JIRA_TRAY_SITE_URL="https://jira.your-company.example"
# Optional - narrows which of your issues show up:
export JIRA_TRAY_CHANNEL_JQL='project = YOURPROJECT'
# Optional, only if the instance uses an internal/corporate CA:
export JIRA_TRAY_CA_BUNDLE=/path/to/internal-ca-bundle.pem
```

In this mode the app uses REST API **v2** and a Bearer **Personal Access
Token** (generated from your Jira profile's Personal Access Tokens
settings) instead of email+API-token Basic auth; the setup dialog's email
field becomes optional. Leave `JIRA_TRAY_DEPLOYMENT` unset (or `cloud`) for
normal, spec-compliant Cloud use - this mode exists purely to validate the
app against a real on-prem instance during development and is not part of
the approved product spec.

## If your organization blocks API tokens (OAuth sign-in)

Some Atlassian orgs' authentication policies reject email+API-token Basic
auth entirely (Jira responds with `401` and a `Www-Authenticate: OAuth`
header even for a freshly generated, valid token). If that's your org, this
app can sign you in with real Atlassian OAuth 2.0 ("3LO") instead - the
same kind of sign-in your browser already uses, going through your org's
SSO.

This requires a one-time setup step **you** need to do yourself (it needs
your own Atlassian login and can't be done on your behalf):

1. Go to `https://developer.atlassian.com/console/myapps/` and create a new
   app (choose "OAuth 2.0 integration").
2. Under **Authorization**, enable OAuth 2.0 (3LO) and set the callback URL
   to exactly:
   ```
   http://localhost:8765/callback
   ```
3. Under **Permissions**, add the "Jira API" and grant these scopes:
   - `read:jira-work`
   - `read:jira-user`
   - `offline_access`
4. Under **Settings**, copy the app's **Client ID** and **Secret**.
5. Set the auth mode env var before running the app:

```bash
export JIRA_TRAY_AUTH_MODE=oauth
export JIRA_TRAY_SITE_URL="https://your-team.atlassian.net"
```

On first launch, a GUI window asks for the Client ID and Secret you copied
above, then opens your browser to sign in with Atlassian and grant access.
The app stores the resulting access/refresh tokens in your OS keyring (like
the API-token mode) and automatically refreshes the access token as needed -
you won't need to sign in again unless you revoke access or stay fully
inactive for 90+ days. `JIRA_TRAY_AUTH_MODE=oauth` is Cloud-only; it cannot
be combined with `JIRA_TRAY_DEPLOYMENT=datacenter`.

### Distributing to a team without each person entering Client ID/Secret

If `JIRA_TRAY_OAUTH_CLIENT_ID` and `JIRA_TRAY_OAUTH_CLIENT_SECRET` are both
already set in the environment before launch, the app **skips the Client
ID/Secret dialog entirely** and teammates only see the "Sign in with
Atlassian" browser step.

`launcher.bat.example` in the project root is a template for this: copy it
to `launcher.bat`, fill in your team's actual Client ID/Secret and Jira site
URL, then distribute the whole project folder (including your filled-in
`launcher.bat`) - teammates just double-click it.

**Important security trade-off:** doing this means the Client Secret is
distributed, in plain text, to every machine that receives `launcher.bat`.
This is the app's **Client Secret** (its identity credential with
Atlassian), not an individual user's password or token - anyone holding it
could register an app that impersonates yours to Atlassian, but it does not
by itself grant access to any Jira data; an attacker would still need a real
user to complete Atlassian's own sign-in/consent screen. Only distribute it
this way if you've made an informed decision that this is acceptable given
this app's scope and sharing settings (e.g. "Sharing within organization",
not "Sharing with anyone", on the app's Atlassian Distribution page). Never
commit a filled-in `launcher.bat` to a shared or public repository - only
hand it directly to your intended users.

For a stronger guarantee that the Client Secret never reaches any user's
machine at all, the app would need a small backend component that performs
the OAuth code exchange on your behalf; that is not implemented here.

#### Recommended: distribute a single standalone .exe (no companion files)

Sending the Python source + `launcher.bat` means every teammate's machine
needs a compatible Python install with all of `requirements.txt` already
`pip install`-ed - in practice this is fragile (wrong/missing Python
version, missing packages). Instead, build one standalone Windows `.exe`
with your team's configuration baked in, and send *just that one file*:

1. Open [app/team_defaults.py](app/team_defaults.py) in your own local copy
   of this project and fill in `TEAM_OAUTH_CLIENT_ID` /
   `TEAM_OAUTH_CLIENT_SECRET` with your real values (the site URL and
   channel JQL are already filled in). Never do this in a shared editor or
   commit the filled-in file anywhere shared/public.
2. Build the exe:

   ```bash
   pip install pyinstaller
   pyinstaller pyinstaller.spec
   # produces dist/JiraTrayMonitor.exe
   ```
3. Send teammates just `dist/JiraTrayMonitor.exe` - nothing else. No
   `launcher.bat`, no environment variables, no Python install. They
   double-click it, click "Yes/Continue" on the one-time approval dialog,
   and sign in with Atlassian.

The same security trade-off described above still applies: the Client
Secret is now baked into the `.exe` binary instead of a `.bat` file, so
anyone holding the `.exe` holds the Client Secret too. Only do this if
you've already made that informed decision (see above).

If different teams need different site URLs/JQL from the same build, you
can still override any baked-in value at launch time by setting the
matching `JIRA_TRAY_...` environment variable before running the exe - for
example via `launcher_exe.bat` (fill in just the values you want to
override; leave the rest blank to use the baked-in defaults). This is
optional and only needed for that per-team-variant scenario.

Note: `pyinstaller.spec` builds with `console=False` (no visible console
window), which also means startup errors are not displayed anywhere. If a
teammate reports the tray icon never appears, temporarily set
`console=True` in `pyinstaller.spec`, rebuild, and have them run the `.exe`
to see the actual error.

## Architecture

```
app/
  config.py            non-secret settings: tenant, approved JQL, poll interval,
                        approval gate, per-OS user-data paths
  team_defaults.py      optional baked-in team defaults for single-.exe distribution
  main.py               entry point: release gate, GUI setup, worker wiring, shutdown
  jira_client.py        Jira Cloud REST v3 client (Basic auth, paginated search)
  state_store.py        persists the issue-id de-dup snapshot across restarts
  poller.py              background thread: serialized polling, backoff, status
  notifier.py             plyer desktop notification wrapper + mute flag
  tray_app.py             pystray icon/alert corner badge + dynamic menu (issues, status, controls)
  autostart.py           opt-in, reversible launch-at-login (Windows/macOS/Linux)
  single_instance.py     best-effort duplicate-instance guard
  auth/
    api_token_auth.py     GUI-agnostic token validation via /rest/api/3/myself
    oauth_flow.py          Atlassian OAuth 2.0 (3LO) sign-in, token refresh, verify
    credential_store.py   keyring-backed storage for email+API token or OAuth tokens
  gui/
    setup_dialog.py        tkinter dialogs for onboarding/reauth/account info/OAuth client
tests/                    pytest suite with mocked Jira HTTP, keyring, and autostart
```

The API token is stored only in the OS credential manager via `keyring` -
never written to disk in plaintext, never logged.

## 1. Generate a Jira Cloud API token

On first launch, a GUI window (no console) explains how to create a
personal API token at:

```
https://id.atlassian.com/manage-profile/security/api-tokens
```

Enter your Atlassian account **email** and paste the generated **token**
(masked as you type). The app verifies both via
`GET /rest/api/3/myself` using HTTP Basic auth and stores them in your OS
keyring - your Atlassian password is never entered into the app.

## 2. Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Linux only: tkinter is not pip-installable, install the OS package:
#   sudo apt-get install python3-tk
python -m app.main
```

## 3. Run tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/
```

All tests mock the Jira HTTP layer, keyring, and autostart filesystem paths
(no network/display dependency) and cover: Basic-auth headers, Cloud v3
pagination, HTTP 401/403/429 handling, id-based notification de-duplication
across restarts, serialized polling, the approval/config release gate,
opt-in launch-at-login, and the opt-in on-prem Data Center (Bearer auth +
v2) testing mode.

## 4. Behavior notes

- **Pagination:** the search client follows `startAt`/`total` until every
  matching issue is retrieved.
- **De-duplication by immutable id:** the app tracks issue IDs (not keys,
  which can change) and persists them to a per-OS user-data directory so
  restarts don't replay notifications for issues already seen. Only IDs and
  a timestamp are stored - never summaries, descriptions, or credentials.
- **Serialized polling:** manual "Refresh Now" and the scheduled background
  poll share a lock and never run concurrently.
- **Jitter and backoff:** poll timing has randomized jitter so many clients
  don't request in lockstep; repeated failures back off exponentially
  (capped), and HTTP 429 responses honor `Retry-After`.
- **Status:** HTTP 401 stops polling and surfaces "reauthentication
  required"; the app then opens a GUI reauth dialog. 403/5xx/network errors
  mark the last known results as stale rather than clearing them.
- **Tray menu:** lists each active issue (opens its canonical Jira URL),
  the exact count and connection status, Refresh Now, Mute/Unmute, Launch
  at Login (where supported), Account info, Sign Out, and Quit.
- **Sign out:** clears both the stored token (keyring) and the local
  de-dup state file, then exits; the next launch re-runs setup.
- **Launch at login:** opt-in and reversible via the tray menu; implemented
  natively per OS (Windows Run key, macOS LaunchAgent, Linux
  `~/.config/autostart`). Never registered automatically.
- **Single instance:** a best-effort local-socket guard prevents duplicate
  tray instances from the same user session.
- **Known limitation (documented per spec):** a client-only poller cannot
  detect issues that enter and leave the query while the app is closed.
  After downtime, issues present now but not in the last persisted snapshot
  are treated as new arrivals and will notify once; this interpretation of
  the "notification window after restart" open decision should be
  confirmed with the product owner before wider rollout.

## 5. Package as a single executable

```bash
pip install pyinstaller
pyinstaller pyinstaller.spec
```

The binary is produced at `dist/JiraTrayMonitor` (or `.exe` on Windows).
`--noconsole` is applied via `console=False` in the spec so no terminal
window appears; `--onefile` bundling is applied via `onefile=True`. All
onboarding, reauth, and informational dialogs use `tkinter` (bundled with
standard Python installers on Windows/macOS; on Linux, build machines need
the `python3-tk` OS package installed before running PyInstaller).

Notes for packaged builds:
- Each teammate generates their own API token the first time they run the
  executable; credentials are scoped per OS user account via keyring.
- TLS certificate verification is always enabled (Jira Cloud uses publicly
  trusted certificates, so no custom CA bundle is needed). The opt-in
  on-prem testing mode never disables verification either - it optionally
  points it at an internal CA bundle (`JIRA_TRAY_CA_BUNDLE`) instead of
  turning it off.

## Security notes

- The API token is treated like a password: stored only in the OS
  credential manager (`keyring`), never in plaintext files, environment
  dumps, or logs. If no secure OS credential store is available, the app
  refuses to save the token rather than falling back to plaintext.
- All HTTP calls use `requests` with default TLS certificate verification
  (never disabled).
- The app is read-only against Jira: it only issues `GET` requests and
  never creates, updates, or deletes Jira data.
- No telemetry.
- Revoke access any time at
  `https://id.atlassian.com/manage-profile/security/api-tokens` (also
  shown in the tray's "Account" menu item) - deleting the token there
  immediately invalidates the app's access. Use "Sign Out" in the tray
  menu to also remove it from local storage.
