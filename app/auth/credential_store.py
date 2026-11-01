"""Secure storage of the Jira Cloud API token and account profile.

Uses `keyring`, which delegates to Windows Credential Manager, macOS
Keychain, or Linux Secret Service - the token is never written to plaintext
files or logs (SPECIFICATION.md section 5). If secure storage is
unavailable, callers must fail closed rather than falling back to disk.
"""
import json
from dataclasses import asdict, dataclass
from typing import Optional, Tuple

import keyring
import keyring.errors

from app.config import KEYRING_SERVICE, KEYRING_USER


@dataclass
class TokenBundle:
    email: str
    api_token: str
    account_id: str = ""
    display_name: str = ""
    auth_mode: str = "token"
    # Only populated when auth_mode == "oauth" (see app/auth/oauth_flow.py).
    client_id: str = ""
    client_secret: str = ""
    access_token: str = ""
    refresh_token: str = ""
    cloud_id: str = ""
    site_url: str = ""


class CredentialStoreUnavailable(Exception):
    """Raised when the OS secure credential store cannot be used at all."""


# Windows Credential Manager rejects a single credential's secret above ~2560
# bytes ("CredWrite ... The stub received bad data."); OAuth bundles (JWT
# access/refresh tokens) regularly exceed that, unlike the short token-mode
# bundles this store originally held. Bundles that fit stay a single plain
# JSON entry (unchanged, backward compatible); larger ones are split across
# numbered chunk entries, with the main entry holding a chunk-count marker.
# Windows stores the blob as UTF-16 (2 bytes/char), so the character budget
# per chunk is roughly half the 2560-byte limit; keep well under that.
_CHUNK_SIZE = 1000
_CHUNK_MARKER_PREFIX = "__CHUNKED__:"


def _chunk_key(index: int) -> str:
    return f"{KEYRING_USER}__chunk{index}"


# Kept separately from the sign-in bundle so it survives sign-out.
_OAUTH_CLIENT_USER = f"{KEYRING_USER}__oauth_client"


def save_oauth_client(client_id: str, client_secret: str) -> None:
    raw = json.dumps({"client_id": client_id, "client_secret": client_secret})
    try:
        keyring.set_password(KEYRING_SERVICE, _OAUTH_CLIENT_USER, raw)
    except keyring.errors.NoKeyringError as exc:
        raise CredentialStoreUnavailable(
            "No OS credential store is available; refusing to save the OAuth "
            "client secret in plaintext."
        ) from exc


def load_oauth_client() -> Optional[Tuple[str, str]]:
    try:
        raw = keyring.get_password(KEYRING_SERVICE, _OAUTH_CLIENT_USER)
    except keyring.errors.NoKeyringError:
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
        client_id, client_secret = data["client_id"], data["client_secret"]
    except (ValueError, TypeError, KeyError):
        return None
    if not client_id or not client_secret:
        return None
    return client_id, client_secret


def save(bundle: TokenBundle) -> None:
    raw = json.dumps(asdict(bundle))
    try:
        if len(raw) <= _CHUNK_SIZE:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USER, raw)
            _delete_chunks()
        else:
            chunks = [raw[i : i + _CHUNK_SIZE] for i in range(0, len(raw), _CHUNK_SIZE)]
            for index, chunk in enumerate(chunks):
                keyring.set_password(KEYRING_SERVICE, _chunk_key(index), chunk)
            keyring.set_password(KEYRING_SERVICE, KEYRING_USER, f"{_CHUNK_MARKER_PREFIX}{len(chunks)}")
    except keyring.errors.NoKeyringError as exc:
        raise CredentialStoreUnavailable(
            "No OS credential store is available; refusing to save the token "
            "in plaintext."
        ) from exc


def load() -> Optional[TokenBundle]:
    try:
        raw = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except keyring.errors.NoKeyringError:
        return None
    if not raw:
        return None
    if raw.startswith(_CHUNK_MARKER_PREFIX):
        try:
            count = int(raw[len(_CHUNK_MARKER_PREFIX) :])
        except ValueError:
            return None
        parts = []
        for index in range(count):
            part = keyring.get_password(KEYRING_SERVICE, _chunk_key(index))
            if part is None:
                return None
            parts.append(part)
        raw = "".join(parts)
    try:
        data = json.loads(raw)
        return TokenBundle(**data)
    except (ValueError, TypeError):
        return None


def _delete_chunks() -> None:
    for index in range(_max_plausible_chunks()):
        try:
            if keyring.get_password(KEYRING_SERVICE, _chunk_key(index)) is None:
                break
        except keyring.errors.NoKeyringError:
            return
        try:
            keyring.delete_password(KEYRING_SERVICE, _chunk_key(index))
        except (keyring.errors.PasswordDeleteError, keyring.errors.NoKeyringError):
            break


def _max_plausible_chunks() -> int:
    # A generous ceiling (bundles are at most a few KB) just to bound the
    # stale-chunk cleanup loop; not a hard protocol limit.
    return 50


def clear() -> None:
    try:
        raw = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except keyring.errors.NoKeyringError:
        raw = None
    if raw and raw.startswith(_CHUNK_MARKER_PREFIX):
        try:
            count = int(raw[len(_CHUNK_MARKER_PREFIX) :])
        except ValueError:
            count = 0
        for index in range(count):
            try:
                keyring.delete_password(KEYRING_SERVICE, _chunk_key(index))
            except (keyring.errors.PasswordDeleteError, keyring.errors.NoKeyringError):
                pass
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
    except keyring.errors.PasswordDeleteError:
        pass
    except keyring.errors.NoKeyringError:
        pass
