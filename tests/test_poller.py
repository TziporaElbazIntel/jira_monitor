"""Tests for Poller: baseline/dedup persistence (by immutable id), serialization,
jitter/backoff status handling, and auth-required stop behavior."""
import threading
import time
from unittest.mock import Mock

import pytest

from app.poller import Poller


class FakeClient:
    def __init__(self, issues):
        self._issues = issues
        self.calls = 0

    def get_active_issues(self):
        self.calls += 1
        return self._issues

    def issue_url(self, issue_key):
        return f"https://example.test/browse/{issue_key}"


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.STATE_FILE_PATH", str(tmp_path / "poll_state.json"))
    monkeypatch.setattr("app.config.USER_DATA_DIR", str(tmp_path))
    yield


def _issue(issue_id, key, summary):
    return {"id": issue_id, "key": key, "fields": {"summary": summary}}


def test_first_poll_is_silent_baseline():
    client = FakeClient([_issue("1", "A-1", "s")])
    new_tickets = []
    poller = Poller(client, on_issues=lambda issues: None, on_new_ticket=lambda k, s, u: new_tickets.append(k))
    poller.poll_now()
    assert new_tickets == []


def test_second_poll_notifies_only_new_issue():
    client = FakeClient([_issue("1", "A-1", "s")])
    new_tickets = []
    poller = Poller(client, on_issues=lambda issues: None, on_new_ticket=lambda k, s, u: new_tickets.append(k))
    poller.poll_now()  # baseline
    client._issues = [_issue("1", "A-1", "s"), _issue("2", "A-2", "new one")]
    poller.poll_now()
    assert new_tickets == ["A-2"]


def test_dedup_uses_immutable_id_not_key():
    """An issue whose key changed (e.g. project move) but kept the same id
    must not be treated as a new arrival."""
    client = FakeClient([_issue("1", "A-1", "s")])
    new_tickets = []
    poller = Poller(client, on_issues=lambda issues: None, on_new_ticket=lambda k, s, u: new_tickets.append(k))
    poller.poll_now()  # baseline
    client._issues = [_issue("1", "B-9", "s")]  # same id, new key
    poller.poll_now()
    assert new_tickets == []


def test_dedup_state_persists_across_poller_instances():
    client = FakeClient([_issue("1", "A-1", "s")])
    poller1 = Poller(client, on_issues=lambda issues: None, on_new_ticket=lambda k, s, u: None)
    poller1.poll_now()

    # A brand-new Poller (simulating app restart) should load the prior
    # snapshot and NOT re-notify for an issue it already saw.
    new_tickets = []
    poller2 = Poller(client, on_issues=lambda issues: None, on_new_ticket=lambda k, s, u: new_tickets.append(k))
    poller2.poll_now()
    assert new_tickets == []


def test_manual_and_scheduled_polls_never_overlap():
    call_order = []
    lock_released = threading.Event()

    class SlowClient:
        def get_active_issues(self):
            call_order.append("start")
            lock_released.wait(timeout=2)
            call_order.append("end")
            return []

    poller = Poller(SlowClient(), on_issues=lambda issues: None, on_new_ticket=lambda k, s, u: None)
    t = threading.Thread(target=poller.poll_now)
    t.start()
    time.sleep(0.05)  # let the first poll acquire the lock and block
    poller.poll_now()  # should be a no-op since the lock is held
    lock_released.set()
    t.join(timeout=2)
    assert call_order == ["start", "end"]


def test_auth_required_stops_further_polling():
    from app.jira_client import AuthRequiredError

    client = Mock()
    client.get_active_issues.side_effect = AuthRequiredError("nope")
    statuses = []
    poller = Poller(
        client,
        on_issues=lambda issues: None,
        on_new_ticket=lambda k, s, u: None,
        on_status=lambda s, d: statuses.append(s),
    )
    poller.poll_now()
    poller.poll_now()
    assert statuses == ["auth_required"]
    assert client.get_active_issues.call_count == 1


def test_allow_reauth_retry_resumes_polling():
    from app.jira_client import AuthRequiredError

    client = Mock()
    client.get_active_issues.side_effect = AuthRequiredError("nope")
    poller = Poller(client, on_issues=lambda issues: None, on_new_ticket=lambda k, s, u: None)
    poller.poll_now()
    assert client.get_active_issues.call_count == 1

    client.get_active_issues.side_effect = None
    client.get_active_issues.return_value = []
    poller.allow_reauth_retry()
    poller.poll_now()
    assert client.get_active_issues.call_count == 2


def test_on_issues_receives_full_issue_list():
    issues = [_issue("1", "A-1", "s")]
    client = FakeClient(issues)
    received = []
    poller = Poller(client, on_issues=lambda i: received.append(i), on_new_ticket=lambda k, s, u: None)
    poller.poll_now()
    assert received == [issues]
