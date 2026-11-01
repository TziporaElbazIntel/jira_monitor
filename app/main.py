"""Entry point: approval gate, GUI-based first-run setup, then the tray app.

No step in this module depends on a console/terminal - all user-facing
interaction goes through `app/gui/setup_dialog.py` (SPECIFICATION.md 4.1).
"""
import sys

from app import config, settings_store, single_instance, state_store
from app.auth import api_token_auth, credential_store, oauth_flow
from app.auth.credential_store import CredentialStoreUnavailable
from app.gui import setup_dialog
from app.jira_client import JiraClient
from app.notifier import Notifier
from app.poller import Poller


def _ensure_approval_recorded() -> None:
    """A personal switch the user controls: confirmed once via a GUI dialog
    and then persisted locally, instead of requiring an environment variable
    to be re-set every session."""
    if config.APPROVAL_RECORDED or settings_store.load_approval_recorded():
        return
    confirmed = setup_dialog.confirm(
        config.APP_NAME,
        "This app stores your personal Jira API token in your OS credential "
        "manager and polls Jira on your behalf.\n\nDo you want to continue?",
    )
    if not confirmed:
        print("Startup cancelled: personal-use confirmation was declined.", file=sys.stderr)
        sys.exit(1)
    settings_store.save_approval_recorded(True)


def _check_release_gate() -> None:
    """Fails closed until the required policy/config inputs exist
    (SPECIFICATION.md 2, "Required before release")."""
    _ensure_approval_recorded()
    if not config.JIRA_SITE_URL:
        print(
            "Startup blocked: JIRA_TRAY_SITE_URL is not set. Configure the "
            "approved Jira site URL before running this app.",
            file=sys.stderr,
        )
        sys.exit(1)


def _collect_credentials_gui(prefill_email: str = "", error_message: str = ""):
    try:
        return setup_dialog.collect_credentials(prefill_email, error_message)
    except setup_dialog.SetupCancelled:
        print("Setup was cancelled by the user.", file=sys.stderr)
        sys.exit(1)


def _collect_oauth_client_gui(prefill_client_id: str = "", error_message: str = ""):
    try:
        return setup_dialog.collect_oauth_client(prefill_client_id, error_message)
    except setup_dialog.SetupCancelled:
        print("Setup was cancelled by the user.", file=sys.stderr)
        sys.exit(1)


def _known_oauth_client():
    if config.OAUTH_CLIENT_ID and config.OAUTH_CLIENT_SECRET:
        return config.OAUTH_CLIENT_ID, config.OAUTH_CLIENT_SECRET
    return credential_store.load_oauth_client()


def _run_setup_with_retries():
    error_message = ""
    prefill_email = ""
    prefill_client_id = ""
    while True:
        try:
            if config.IS_OAUTH:
                # After a failure, fall back to the dialog in case the known client is wrong.
                known = None if error_message else _known_oauth_client()
                if known:
                    client_id, client_secret = known
                else:
                    client_id, client_secret = _collect_oauth_client_gui(prefill_client_id, error_message)
                prefill_client_id = client_id
                bundle = oauth_flow.run_setup_flow(client_id, client_secret)
                credential_store.save_oauth_client(client_id, client_secret)
                return bundle
            return api_token_auth.run_setup_flow(
                lambda: _collect_credentials_gui(prefill_email, error_message)
            )
        except (api_token_auth.AuthError, oauth_flow.AuthError) as exc:
            error_message = str(exc)


def _verify_token(bundle):
    return oauth_flow.verify_token(bundle) if bundle.auth_mode == "oauth" else api_token_auth.verify_token(bundle)


def _load_or_authorize():
    bundle = credential_store.load()
    if bundle is None:
        bundle = _run_setup_with_retries()
        credential_store.save(bundle)
        return bundle, True

    try:
        bundle = _verify_token(bundle)
    except (api_token_auth.AuthError, oauth_flow.AuthError):
        setup_dialog.show_message(
            config.APP_NAME,
            "Your saved Jira credentials were rejected. Please reauthenticate.",
        )
        bundle = _run_setup_with_retries()
        credential_store.save(bundle)
        return bundle, True
    credential_store.save(bundle)  # persist any refreshed OAuth access/refresh tokens
    return bundle, False


def _sign_out():
    """Clears the saved token and local dedup state; next launch re-runs
    setup (SPECIFICATION.md 4.1). The OAuth client ID/secret are kept."""
    bundle = credential_store.load()
    if bundle and bundle.client_id and bundle.client_secret:
        credential_store.save_oauth_client(bundle.client_id, bundle.client_secret)
    credential_store.clear()
    state_store.clear()


def main():
    _check_release_gate()

    # Imported lazily so this module (and its release-gate/auth logic) stays
    # importable and testable on systems/CI without a display backend.
    from app.tray_app import TrayApp

    if not single_instance.acquire():
        print(f"{config.APP_NAME} is already running.", file=sys.stderr)
        sys.exit(0)

    try:
        bundle, is_new_signin = _load_or_authorize()
    except CredentialStoreUnavailable as exc:
        setup_dialog.show_message("Secure storage unavailable", str(exc))
        sys.exit(1)

    if is_new_signin:
        setup_dialog.show_message(
            config.APP_NAME, f"Signed in as {bundle.display_name or bundle.email}."
        )

    jira_client = JiraClient(bundle, on_token_refreshed=credential_store.save)
    notifier = Notifier()

    def on_show_account():
        identity = bundle.display_name or bundle.email or bundle.account_id
        if bundle.auth_mode == "oauth":
            revoke_hint = (
                "Revoke access from your Atlassian account's \"Connected apps\" "
                "security settings."
            )
        elif config.IS_DATACENTER:
            revoke_hint = (
                "Revoke this token from your Jira profile's Personal Access "
                "Tokens settings."
            )
        else:
            revoke_hint = f"Revoke this token at: {config.API_TOKEN_SETTINGS_URL}"
        setup_dialog.show_message(
            "Account",
            f"Signed in as {identity}.\n\n{revoke_hint}",
        )

    tray = TrayApp(
        on_refresh=lambda: poller.poll_now(),
        on_mute_toggle=lambda: notifier.toggle_mute(),
        on_sign_out=_sign_out,
        on_show_account=on_show_account,
    )

    def on_issues(issues):
        tray.set_issues(
            [
                {
                    "key": i["key"],
                    "summary": i.get("fields", {}).get("summary", ""),
                    "url": jira_client.issue_url(i["key"]),
                }
                for i in issues
            ]
        )

    def on_new_ticket(issue_key: str, summary: str, url: str):
        notifier.notify_new_ticket(issue_key, summary, url)

    def on_status(status: str, detail: str):
        tray.set_status(status, detail)
        if detail:
            print(f"[{status}] {detail}", file=sys.stderr)

    poller = Poller(jira_client, on_issues=on_issues, on_new_ticket=on_new_ticket, on_status=on_status)
    poller.start()

    try:
        tray.run()
    finally:
        poller.stop()


if __name__ == "__main__":
    main()
