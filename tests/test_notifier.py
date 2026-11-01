"""Tests for Notifier: mute toggle, Windows toast vs Linux notify-send fallback."""
from unittest.mock import Mock, patch

from app.notifier import Notifier


def test_muted_skips_notification():
    with patch("app.notifier._ToastNotification", Mock()) as mock_toast_cls, patch(
        "app.notifier._NOTIFY_SEND_PATH", "/usr/bin/notify-send"
    ), patch("app.notifier.subprocess.run") as mock_run:
        notifier = Notifier()
        notifier.toggle_mute()
        notifier.notify_new_ticket("ABC-1", "Summary", "https://example.atlassian.net/browse/ABC-1")
    mock_toast_cls.assert_not_called()
    mock_run.assert_not_called()


def test_uses_windows_toast_when_available():
    mock_toast_instance = Mock()
    mock_toast_cls = Mock(return_value=mock_toast_instance)
    with patch("app.notifier._ToastNotification", mock_toast_cls), patch(
        "app.notifier._NOTIFY_SEND_PATH", "/usr/bin/notify-send"
    ), patch("app.notifier.subprocess.run") as mock_run:
        notifier = Notifier()
        notifier.notify_new_ticket("ABC-1", "Summary", "https://example.atlassian.net/browse/ABC-1")
    mock_toast_cls.assert_called_once()
    mock_toast_instance.show.assert_called_once()
    mock_run.assert_not_called()


def test_falls_back_to_notify_send_on_linux():
    with patch("app.notifier._ToastNotification", None), patch(
        "app.notifier._NOTIFY_SEND_PATH", "/usr/bin/notify-send"
    ), patch("app.notifier.subprocess.run") as mock_run:
        notifier = Notifier()
        notifier.notify_new_ticket("ABC-1", "Summary")
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == "/usr/bin/notify-send"
    assert "New Jira issue: ABC-1" in args
    assert "Summary" in args


def test_no_backend_available_does_not_raise():
    with patch("app.notifier._ToastNotification", None), patch("app.notifier._NOTIFY_SEND_PATH", None), patch(
        "app.notifier.subprocess.run"
    ) as mock_run:
        notifier = Notifier()
        notifier.notify_new_ticket("ABC-1", "Summary")
    mock_run.assert_not_called()


def test_notify_send_failure_is_swallowed():
    with patch("app.notifier._ToastNotification", None), patch(
        "app.notifier._NOTIFY_SEND_PATH", "/usr/bin/notify-send"
    ), patch("app.notifier.subprocess.run", side_effect=OSError("not found")):
        notifier = Notifier()
        notifier.notify_new_ticket("ABC-1", "Summary")  # must not raise
