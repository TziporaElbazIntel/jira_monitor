"""Tests for credential_store: keyring-backed save/load/clear, no plaintext fallback."""
import keyring.errors
import pytest

from app.auth import credential_store
from app.auth.credential_store import CredentialStoreUnavailable, TokenBundle


def test_save_then_load_round_trips(monkeypatch):
    backing = {}

    def fake_set(service, user, value):
        backing[(service, user)] = value

    def fake_get(service, user):
        return backing.get((service, user))

    monkeypatch.setattr(credential_store.keyring, "set_password", fake_set)
    monkeypatch.setattr(credential_store.keyring, "get_password", fake_get)

    bundle = TokenBundle(email="user@example.com", api_token="tok-123", account_id="acc", display_name="Tester")
    credential_store.save(bundle)
    loaded = credential_store.load()
    assert loaded == bundle


def test_load_returns_none_when_nothing_saved(monkeypatch):
    monkeypatch.setattr(credential_store.keyring, "get_password", lambda service, user: None)
    assert credential_store.load() is None


def test_load_returns_none_on_corrupt_data(monkeypatch):
    monkeypatch.setattr(credential_store.keyring, "get_password", lambda service, user: "not-json")
    assert credential_store.load() is None


def test_save_fails_closed_when_no_keyring_backend(monkeypatch):
    def raise_no_keyring(*args, **kwargs):
        raise keyring.errors.NoKeyringError("no backend")

    monkeypatch.setattr(credential_store.keyring, "set_password", raise_no_keyring)
    bundle = TokenBundle(email="user@example.com", api_token="tok-123")
    with pytest.raises(CredentialStoreUnavailable):
        credential_store.save(bundle)


def test_clear_is_idempotent_when_nothing_to_delete(monkeypatch):
    def raise_not_found(*args, **kwargs):
        raise keyring.errors.PasswordDeleteError("not found")

    monkeypatch.setattr(credential_store.keyring, "get_password", lambda service, user: None)
    monkeypatch.setattr(credential_store.keyring, "delete_password", raise_not_found)
    credential_store.clear()  # must not raise


def _fake_backend(monkeypatch):
    backing = {}

    def fake_set(service, user, value):
        backing[(service, user)] = value

    def fake_get(service, user):
        return backing.get((service, user))

    def fake_delete(service, user):
        if (service, user) not in backing:
            raise keyring.errors.PasswordDeleteError("not found")
        del backing[(service, user)]

    monkeypatch.setattr(credential_store.keyring, "set_password", fake_set)
    monkeypatch.setattr(credential_store.keyring, "get_password", fake_get)
    monkeypatch.setattr(credential_store.keyring, "delete_password", fake_delete)
    return backing


def test_large_oauth_bundle_is_chunked_and_round_trips(monkeypatch):
    backing = _fake_backend(monkeypatch)
    bundle = TokenBundle(
        email="",
        api_token="",
        auth_mode="oauth",
        client_id="client-id",
        client_secret="client-secret",
        access_token="a" * 4000,  # larger than a single Windows Credential Manager entry allows
        refresh_token="r" * 1000,
        cloud_id="cloud-123",
        site_url="https://example.atlassian.net",
    )
    credential_store.save(bundle)

    # Stored as multiple chunk entries, not one oversized entry.
    main_entry = backing[(credential_store.KEYRING_SERVICE, credential_store.KEYRING_USER)]
    assert main_entry.startswith("__CHUNKED__:")
    assert len(main_entry) < 100
    assert any(key[1].startswith("default__chunk") for key in backing)

    loaded = credential_store.load()
    assert loaded == bundle


def test_resaving_small_bundle_clears_stale_chunks(monkeypatch):
    backing = _fake_backend(monkeypatch)
    large_bundle = TokenBundle(
        email="", api_token="", auth_mode="oauth", access_token="a" * 4000
    )
    credential_store.save(large_bundle)
    assert any(key[1].startswith("default__chunk") for key in backing)

    small_bundle = TokenBundle(email="user@example.com", api_token="tok-123")
    credential_store.save(small_bundle)
    assert not any(key[1].startswith("default__chunk") for key in backing)
    assert credential_store.load() == small_bundle


def test_clear_removes_chunks_too(monkeypatch):
    backing = _fake_backend(monkeypatch)
    bundle = TokenBundle(email="", api_token="", auth_mode="oauth", access_token="a" * 4000)
    credential_store.save(bundle)
    assert any(key[1].startswith("default__chunk") for key in backing)

    credential_store.clear()
    assert backing == {}


def test_oauth_client_round_trips_and_survives_clear(monkeypatch):
    _fake_backend(monkeypatch)
    credential_store.save(TokenBundle(email="", api_token="", auth_mode="oauth", access_token="a" * 4000))
    credential_store.save_oauth_client("cid", "secret")

    credential_store.clear()

    assert credential_store.load() is None
    assert credential_store.load_oauth_client() == ("cid", "secret")


def test_load_oauth_client_returns_none_when_missing(monkeypatch):
    _fake_backend(monkeypatch)
    assert credential_store.load_oauth_client() is None
