"""Durable storage for the user-controlled personal-use confirmation switch
(see `main._ensure_approval_recorded`), so each user confirms this once for
themselves instead of needing an environment variable set every session.
"""
import json
import os

from app import config


def load_approval_recorded() -> bool:
    try:
        with open(config.SETTINGS_FILE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return bool(data.get("approval_recorded", False))
    except (FileNotFoundError, ValueError, OSError):
        return False


def save_approval_recorded(value: bool) -> None:
    os.makedirs(config.USER_DATA_DIR, exist_ok=True)
    tmp_path = config.SETTINGS_FILE_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump({"approval_recorded": value}, fh)
    os.replace(tmp_path, config.SETTINGS_FILE_PATH)
