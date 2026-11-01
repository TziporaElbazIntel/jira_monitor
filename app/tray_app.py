"""System tray icon: draws a badge with the active-issue count, lists the
matching issues directly in the menu, and hosts connection/status and user
controls (SPECIFICATION.md 4.5).
"""
import webbrowser
from functools import lru_cache
from pathlib import Path
from typing import Callable, List

import pystray
from PIL import Image, ImageDraw

from app import autostart
from app.config import APP_NAME, MAX_MENU_ISSUES

# Rendered large and downscaled by the OS tray, so the Jira icon stays
# crisp instead of looking blurry (as a 64px source did).
_BASE_SIZE = 128
_BASE_COLOR = (38, 132, 255, 255)   # Jira-ish blue
# Open issues are signalled Teams-presence-badge style: a large solid red
# dot (~60% of the icon width) flush with the bottom-right corner,
# separated from the logo by a transparent cut-out gap so the taskbar
# background shows through on both light and dark themes.
_BADGE_COLOR = (222, 53, 11, 255)   # Jira's red accent (#DE350B)
_BADGE_DIAMETER_FRACTION = 0.56
_BADGE_GAP_FRACTION = 0.06

_STATUS_LABELS = {
    "connecting": "Connecting...",
    "connected": "Connected",
    "stale": "Stale - offline",
    "auth_required": "Reauthentication required",
    "error": "Error",
}

# Optional real Jira logo, user-supplied (not bundled: Atlassian's logo is
# trademarked). Falls back to a generic placeholder if absent.
_JIRA_ICON_PATH = Path(__file__).parent / "assets" / "jira_icon.png"


@lru_cache(maxsize=1)
def _load_base_icon() -> Image.Image:
    if _JIRA_ICON_PATH.exists():
        base = Image.open(_JIRA_ICON_PATH).convert("RGBA")
        if base.size != (_BASE_SIZE, _BASE_SIZE):
            base = base.resize((_BASE_SIZE, _BASE_SIZE), Image.LANCZOS)
        return base

    img = Image.new("RGBA", (_BASE_SIZE, _BASE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, _BASE_SIZE - 1, _BASE_SIZE - 1), radius=24, fill=_BASE_COLOR)
    draw.polygon([(40, 64), (64, 40), (88, 64), (64, 88)], fill=(255, 255, 255, 255))
    return img


def _render_icon(count: int) -> Image.Image:
    img = _load_base_icon().copy()

    if count == 0:
        # No issues: just the plain icon, no dot.
        return img

    # Drawn supersampled then downscaled so the edges stay smooth.
    scale = 4
    size = _BASE_SIZE * scale
    dot_radius = _BASE_SIZE * _BADGE_DIAMETER_FRACTION / 2 * scale
    gap_radius = dot_radius + _BASE_SIZE * _BADGE_GAP_FRACTION * scale
    center = size - dot_radius  # flush with the bottom-right corner

    def _circle(radius: float, mode: str, fill) -> Image.Image:
        layer = Image.new(mode, (size, size), 0)
        ImageDraw.Draw(layer).ellipse(
            (center - radius, center - radius, center + radius, center + radius), fill=fill
        )
        return layer.resize((_BASE_SIZE, _BASE_SIZE), Image.LANCZOS)

    # Cut a transparent ring out of the logo around the dot.
    gap_mask = _circle(gap_radius, "L", 255)
    alpha = Image.composite(Image.new("L", img.size, 0), img.getchannel("A"), gap_mask)
    img.putalpha(alpha)

    img.alpha_composite(_circle(dot_radius, "RGBA", _BADGE_COLOR))
    return img


class TrayApp:
    def __init__(
        self,
        on_refresh: Callable[[], None],
        on_mute_toggle: Callable[[], None],
        on_sign_out: Callable[[], None],
        on_show_account: Callable[[], None],
    ):
        self._on_refresh = on_refresh
        self._on_mute_toggle = on_mute_toggle
        self._on_sign_out = on_sign_out
        self._on_show_account = on_show_account
        self._muted = False
        self._issues: List[dict] = []  # [{key, summary, url}, ...]
        self._status = "connecting"
        self._status_detail = ""
        self._autostart_supported = autostart.is_supported()

        self.icon = pystray.Icon(
            APP_NAME,
            _render_icon(0),
            f"{APP_NAME} - connecting...",
            menu=pystray.Menu(self._generate_menu),
        )

    def _generate_menu(self):
        count = len(self._issues)
        status_label = _STATUS_LABELS.get(self._status, self._status)
        count_label = "no active issues" if count == 0 else f"{count} active issue(s)"
        yield pystray.MenuItem(f"{count_label} - {status_label}", None, enabled=False)
        yield pystray.Menu.SEPARATOR

        if self._issues:
            for issue in self._issues[:MAX_MENU_ISSUES]:
                label = f"{issue['key']}: {issue['summary']}"
                if len(label) > 70:
                    label = label[:67] + "..."
                yield pystray.MenuItem(label, self._make_opener(issue["url"]))
            if count > MAX_MENU_ISSUES:
                yield pystray.MenuItem(f"... and {count - MAX_MENU_ISSUES} more", None, enabled=False)
        else:
            yield pystray.MenuItem("No active issues", None, enabled=False)

        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Refresh Now", lambda icon, item: self._on_refresh())
        yield pystray.MenuItem("Mute Notifications", self._toggle_mute, checked=lambda item: self._muted)
        if self._autostart_supported:
            yield pystray.MenuItem(
                "Launch at Login", self._toggle_autostart, checked=lambda item: autostart.is_enabled()
            )
        yield pystray.MenuItem("Account", lambda icon, item: self._on_show_account())
        yield pystray.MenuItem("Sign Out", self._sign_out)
        yield pystray.MenuItem("Quit", self._quit)

    @staticmethod
    def _make_opener(url: str):
        return lambda icon, item: webbrowser.open(url)

    def _toggle_mute(self, icon=None, item=None):
        self._muted = not self._muted
        self._on_mute_toggle()
        self.icon.update_menu()

    def _toggle_autostart(self, icon=None, item=None):
        try:
            autostart.toggle()
        except Exception:
            pass  # Best-effort; never crash the tray over this.
        self.icon.update_menu()

    def _sign_out(self, icon=None, item=None):
        self._on_sign_out()
        self.icon.stop()

    def _quit(self, icon=None, item=None):
        self.icon.stop()

    def set_issues(self, issues: List[dict]):
        self._issues = issues
        self.icon.icon = _render_icon(len(issues))
        self._refresh_title()
        self.icon.update_menu()

    def set_status(self, status: str, detail: str = ""):
        """status: connecting | connected | stale | auth_required | error"""
        self._status = status
        self._status_detail = detail
        self._refresh_title()
        self.icon.update_menu()

    def _refresh_title(self):
        count = len(self._issues)
        label = "no active issues" if count == 0 else f"{count} active issue(s)"
        status_label = _STATUS_LABELS.get(self._status, self._status)
        self.icon.title = f"{APP_NAME} - {label} ({status_label})"

    def run(self):
        self.icon.run()
