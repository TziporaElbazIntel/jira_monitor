"""Tests for main.py's release/approval gate (SPECIFICATION.md 2 and 11)."""
import pytest

from app import main as app_main


def test_asks_for_confirmation_when_approval_not_recorded(monkeypatch):
    monkeypatch.setattr("app.config.APPROVAL_RECORDED", False)
    monkeypatch.setattr("app.config.JIRA_SITE_URL", "https://example.atlassian.net")
    monkeypatch.setattr("app.settings_store.load_approval_recorded", lambda: False)
    saved = {}
    monkeypatch.setattr("app.settings_store.save_approval_recorded", lambda v: saved.update(value=v))
    monkeypatch.setattr("app.gui.setup_dialog.confirm", lambda title, message: True)
    app_main._check_release_gate()  # must not raise
    assert saved["value"] is True


def test_blocks_when_confirmation_declined(monkeypatch):
    monkeypatch.setattr("app.config.APPROVAL_RECORDED", False)
    monkeypatch.setattr("app.config.JIRA_SITE_URL", "https://example.atlassian.net")
    monkeypatch.setattr("app.settings_store.load_approval_recorded", lambda: False)
    monkeypatch.setattr("app.gui.setup_dialog.confirm", lambda title, message: False)
    with pytest.raises(SystemExit) as exc_info:
        app_main._check_release_gate()
    assert exc_info.value.code == 1


def test_skips_confirmation_when_previously_recorded_locally(monkeypatch):
    monkeypatch.setattr("app.config.APPROVAL_RECORDED", False)
    monkeypatch.setattr("app.config.JIRA_SITE_URL", "https://example.atlassian.net")
    monkeypatch.setattr("app.settings_store.load_approval_recorded", lambda: True)
    app_main._check_release_gate()  # must not raise, no dialog needed


def test_blocks_when_site_url_missing(monkeypatch):
    monkeypatch.setattr("app.config.APPROVAL_RECORDED", True)
    monkeypatch.setattr("app.config.JIRA_SITE_URL", "")
    with pytest.raises(SystemExit):
        app_main._check_release_gate()


def test_passes_when_fully_configured(monkeypatch):
    monkeypatch.setattr("app.config.APPROVAL_RECORDED", True)
    monkeypatch.setattr("app.config.JIRA_SITE_URL", "https://example.atlassian.net")
    app_main._check_release_gate()  # must not raise


def _oauth_setup(monkeypatch, env_client=("", ""), stored_client=None):
    monkeypatch.setattr("app.config.IS_OAUTH", True)
    monkeypatch.setattr("app.config.OAUTH_CLIENT_ID", env_client[0])
    monkeypatch.setattr("app.config.OAUTH_CLIENT_SECRET", env_client[1])
    monkeypatch.setattr("app.auth.credential_store.load_oauth_client", lambda: stored_client)
    saved = {}
    monkeypatch.setattr(
        "app.auth.credential_store.save_oauth_client", lambda cid, secret: saved.update(client=(cid, secret))
    )
    used = {}

    def fake_flow(cid, secret):
        used["client"] = (cid, secret)
        return "bundle"

    monkeypatch.setattr("app.auth.oauth_flow.run_setup_flow", fake_flow)
    return saved, used


def _no_dialog(*args, **kwargs):
    raise AssertionError("Client ID/Secret dialog should not be shown")


def test_oauth_setup_uses_env_client_without_dialog(monkeypatch):
    saved, used = _oauth_setup(monkeypatch, env_client=("env-id", "env-secret"))
    monkeypatch.setattr(app_main, "_collect_oauth_client_gui", _no_dialog)
    assert app_main._run_setup_with_retries() == "bundle"
    assert used["client"] == ("env-id", "env-secret")
    assert saved["client"] == ("env-id", "env-secret")


def test_oauth_setup_reuses_stored_client_without_dialog(monkeypatch):
    _, used = _oauth_setup(monkeypatch, stored_client=("stored-id", "stored-secret"))
    monkeypatch.setattr(app_main, "_collect_oauth_client_gui", _no_dialog)
    app_main._run_setup_with_retries()
    assert used["client"] == ("stored-id", "stored-secret")


def test_oauth_setup_shows_dialog_when_no_known_client(monkeypatch):
    saved, used = _oauth_setup(monkeypatch)
    monkeypatch.setattr(app_main, "_collect_oauth_client_gui", lambda *a: ("typed-id", "typed-secret"))
    app_main._run_setup_with_retries()
    assert used["client"] == ("typed-id", "typed-secret")
    assert saved["client"] == ("typed-id", "typed-secret")


def test_sign_out_keeps_oauth_client(monkeypatch):
    from app.auth.credential_store import TokenBundle

    bundle = TokenBundle(email="", api_token="", auth_mode="oauth", client_id="cid", client_secret="sec")
    monkeypatch.setattr("app.auth.credential_store.load", lambda: bundle)
    saved = {}
    monkeypatch.setattr(
        "app.auth.credential_store.save_oauth_client", lambda cid, secret: saved.update(client=(cid, secret))
    )
    cleared = []
    monkeypatch.setattr("app.auth.credential_store.clear", lambda: cleared.append("creds"))
    monkeypatch.setattr("app.state_store.clear", lambda: cleared.append("state"))

    app_main._sign_out()

    assert saved["client"] == ("cid", "sec")
    assert cleared == ["creds", "state"]
