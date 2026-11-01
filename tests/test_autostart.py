"""Tests for autostart: opt-in, reversible, per-OS launch-at-login.

Only the Linux (.desktop) path is exercised directly since that's what this
test environment runs; Windows/macOS branches are not unit-testable without
those OSes, per the manual OS-matrix test strategy in SPECIFICATION.md 9.
"""
import os

import pytest

from app import autostart


@pytest.fixture(autouse=True)
def isolated_autostart_dir(tmp_path, monkeypatch):
    desktop_path = tmp_path / f"{autostart.APP_NAME}.desktop"
    monkeypatch.setattr(autostart, "_LINUX_AUTOSTART_DIR", str(tmp_path))
    monkeypatch.setattr(autostart, "_LINUX_DESKTOP_PATH", str(desktop_path))
    yield


@pytest.mark.skipif(os.name == "nt" or __import__("sys").platform == "darwin", reason="Linux-only path")
def test_enable_creates_desktop_entry_and_is_reported_enabled():
    assert autostart.is_enabled() is False
    autostart.enable()
    assert autostart.is_enabled() is True
    assert os.path.isfile(autostart._LINUX_DESKTOP_PATH)


@pytest.mark.skipif(os.name == "nt" or __import__("sys").platform == "darwin", reason="Linux-only path")
def test_disable_removes_desktop_entry():
    autostart.enable()
    autostart.disable()
    assert autostart.is_enabled() is False


@pytest.mark.skipif(os.name == "nt" or __import__("sys").platform == "darwin", reason="Linux-only path")
def test_toggle_flips_state_and_is_reversible():
    assert autostart.toggle() is True
    assert autostart.is_enabled() is True
    assert autostart.toggle() is False
    assert autostart.is_enabled() is False
