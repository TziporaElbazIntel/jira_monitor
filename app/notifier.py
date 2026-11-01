"""Desktop notification helper, respecting the user's mute toggle.

Uses Windows' native toast notifications (via winotify) so popups match the
modern Action Center style, show the Jira icon, and can be clicked to open
the issue directly in the browser. On Linux, falls back to the standard
`notify-send` tool (libnotify) - this can't click-to-open like winotify, so
the tray menu's issue list remains the way to open the issue there.

Notification text is limited to the issue key and a short summary, per
SPECIFICATION.md 4.3 ("minimize sensitive content"). Failures here must
never stop polling.
"""
import shutil
import subprocess
import sys
from pathlib import Path

try:
    # winotify shells out to PowerShell and imports winreg, so it's only
    # importable on Windows; keep this optional so non-Windows dev/test
    # environments can still import this module.
    from winotify import Notification as _ToastNotification
except ImportError:  # pragma: no cover - exercised only on non-Windows
    _ToastNotification = None

from app.config import APP_NAME

_ICON_PATH = Path(__file__).parent / "assets" / "jira_icon.png"
_NOTIFY_SEND_PATH = shutil.which("notify-send") if sys.platform.startswith("linux") else None


class Notifier:
    def __init__(self):
        self.muted = False

    def toggle_mute(self):
        self.muted = not self.muted

    def notify_new_ticket(self, issue_key: str, summary: str, url: str = ""):
        if self.muted:
            return
        try:
            if _ToastNotification is not None:
                toast = _ToastNotification(
                    app_id=APP_NAME,
                    title=f"New Jira issue: {issue_key}",
                    msg=summary[:200],
                    icon=str(_ICON_PATH) if _ICON_PATH.is_file() else "",
                    launch=url,
                )
                toast.show()
            elif _NOTIFY_SEND_PATH:
                args = [_NOTIFY_SEND_PATH, f"--app-name={APP_NAME}", f"New Jira issue: {issue_key}", summary[:200]]
                if _ICON_PATH.is_file():
                    args.append(f"--icon={_ICON_PATH}")
                subprocess.run(args, check=False, timeout=5)
        except Exception:
            # Notifications are best-effort; never crash the app over them.
            pass
