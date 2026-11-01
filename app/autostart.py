"""Opt-in, reversible launch-at-login integration (SPECIFICATION.md 4.5).

Implemented separately per OS, and never registered silently - callers must
explicitly invoke `enable()`. Each platform uses the mechanism native to it:

- Windows: a value under HKCU\\...\\Run (no admin rights needed).
- macOS: a per-user LaunchAgent plist in ~/Library/LaunchAgents.
- Linux: a desktop-autostart entry in ~/.config/autostart (XDG spec).
"""
import os
import sys

from app.config import APP_NAME

_LINUX_AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
_LINUX_DESKTOP_PATH = os.path.join(_LINUX_AUTOSTART_DIR, f"{APP_NAME}.desktop")

_MACOS_AGENT_DIR = os.path.expanduser("~/Library/LaunchAgents")
_MACOS_AGENT_LABEL = "com.jiratraymonitor.launcher"
_MACOS_AGENT_PATH = os.path.join(_MACOS_AGENT_DIR, f"{_MACOS_AGENT_LABEL}.plist")

_WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WINDOWS_VALUE_NAME = APP_NAME


def _launch_command() -> str:
    """Prefers the frozen (PyInstaller) executable path; falls back to
    `python -m app.main` for source/dev runs."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return f'"{sys.executable}" -m app.main'


def is_supported() -> bool:
    return os.name == "nt" or sys.platform == "darwin" or sys.platform.startswith("linux")


def is_enabled() -> bool:
    if os.name == "nt":
        return _windows_is_enabled()
    if sys.platform == "darwin":
        return os.path.isfile(_MACOS_AGENT_PATH)
    if sys.platform.startswith("linux"):
        return os.path.isfile(_LINUX_DESKTOP_PATH)
    return False


def enable() -> None:
    if os.name == "nt":
        _windows_enable()
    elif sys.platform == "darwin":
        _macos_enable()
    elif sys.platform.startswith("linux"):
        _linux_enable()
    else:
        raise RuntimeError("Launch-at-login is not supported on this platform.")


def disable() -> None:
    if os.name == "nt":
        _windows_disable()
    elif sys.platform == "darwin":
        _macos_disable()
    elif sys.platform.startswith("linux"):
        _linux_disable()


def toggle() -> bool:
    """Flips the current state and returns the new enabled state."""
    if is_enabled():
        disable()
        return False
    enable()
    return True


# --- Linux ---------------------------------------------------------------
def _linux_enable() -> None:
    os.makedirs(_LINUX_AUTOSTART_DIR, exist_ok=True)
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f"Exec={_launch_command()}\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    with open(_LINUX_DESKTOP_PATH, "w", encoding="utf-8") as fh:
        fh.write(content)


def _linux_disable() -> None:
    try:
        os.remove(_LINUX_DESKTOP_PATH)
    except OSError:
        pass


# --- macOS -----------------------------------------------------------------
def _macos_enable() -> None:
    os.makedirs(_MACOS_AGENT_DIR, exist_ok=True)
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_MACOS_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
    with open(_MACOS_AGENT_PATH, "w", encoding="utf-8") as fh:
        fh.write(plist)


def _macos_disable() -> None:
    try:
        os.remove(_MACOS_AGENT_PATH)
    except OSError:
        pass


# --- Windows -----------------------------------------------------------------
def _windows_enable() -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, _WINDOWS_VALUE_NAME, 0, winreg.REG_SZ, _launch_command())


def _windows_disable() -> None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _WINDOWS_VALUE_NAME)
    except FileNotFoundError:
        pass


def _windows_is_enabled() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WINDOWS_RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, _WINDOWS_VALUE_NAME)
        return True
    except FileNotFoundError:
        return False
