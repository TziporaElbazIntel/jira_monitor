"""Durable storage for notification de-duplication state.

Only the minimum needed to avoid re-notifying across restarts is kept here:
the set of immutable issue IDs seen on the last successful poll, and when
that poll happened. No issue summaries, descriptions, or credentials are
stored (SPECIFICATION.md 4.3 and 5).
"""
import json
import os
from typing import Optional, Set

from app import config


def load_known_ids() -> Optional[Set[str]]:
    """Returns the last-known issue-id snapshot, or None if there isn't one
    (e.g. first run) so the caller can treat it as "no baseline yet"."""
    try:
        with open(config.STATE_FILE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return set(data.get("known_ids", []))
    except (FileNotFoundError, ValueError, OSError):
        return None


def save_known_ids(ids: Set[str], last_poll_epoch: float) -> None:
    os.makedirs(config.USER_DATA_DIR, exist_ok=True)
    tmp_path = config.STATE_FILE_PATH + ".tmp"
    payload = {"known_ids": sorted(ids), "last_poll_epoch": last_poll_epoch}
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    os.replace(tmp_path, config.STATE_FILE_PATH)


def clear() -> None:
    try:
        os.remove(config.STATE_FILE_PATH)
    except OSError:
        pass
