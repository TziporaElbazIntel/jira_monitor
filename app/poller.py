"""Background polling thread: fetches active issues and reports diffs/status.

Serializes manual ("Refresh Now") and scheduled polls so they never overlap,
persists a dedup baseline (by immutable issue id) across restarts, applies
jitter so clients don't poll in lockstep, and backs off on repeated failures
(SPECIFICATION.md 4.3 and 4.4).
"""
import random
import threading
import time
from typing import Callable, List, Optional, Set

from app import state_store
from app.config import (
    BACKOFF_BASE_SECONDS,
    BACKOFF_MAX_SECONDS,
    POLL_INTERVAL_SECONDS,
    POLL_JITTER_FRACTION,
)
from app.jira_client import AuthRequiredError, JiraClient, PermissionDeniedError, RateLimitedError


def _jittered(seconds: float) -> float:
    spread = seconds * POLL_JITTER_FRACTION
    return max(0.0, seconds + random.uniform(-spread, spread))


class Poller:
    def __init__(
        self,
        jira_client: JiraClient,
        on_issues: Callable[[List[dict]], None],
        on_new_ticket: Callable[[str, str, str], None],
        on_status: Optional[Callable[[str, str], None]] = None,
        interval: int = POLL_INTERVAL_SECONDS,
    ):
        self._client = jira_client
        self._on_issues = on_issues
        self._on_new_ticket = on_new_ticket
        self._on_status = on_status or (lambda status, detail: None)
        self._interval = interval
        # None means "no baseline yet" (first run, or state file missing/corrupt);
        # the first successful poll in that case is silent per spec.
        self._known_ids: Optional[Set[str]] = state_store.load_known_ids()
        self._stop_event = threading.Event()
        self._poll_lock = threading.Lock()
        self._auth_required = threading.Event()
        self._consecutive_failures = 0
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=5)

    def poll_now(self):
        self._poll_once()

    def allow_reauth_retry(self):
        """Called after the user successfully reauthenticates, so polling
        resumes instead of staying stopped forever."""
        self._auth_required.clear()
        self._consecutive_failures = 0

    def _run(self):
        self._stop_event.wait(_jittered(1.0))  # small startup jitter
        while not self._stop_event.is_set():
            self._poll_once()
            self._stop_event.wait(self._next_wait_seconds())

    def _next_wait_seconds(self) -> float:
        if self._consecutive_failures == 0:
            return _jittered(self._interval)
        backoff = min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (self._consecutive_failures - 1)))
        return _jittered(backoff)

    def _poll_once(self):
        if self._auth_required.is_set():
            return  # Stopped normal polling until the user reauthenticates.

        if not self._poll_lock.acquire(blocking=False):
            return  # A poll (manual or scheduled) is already in flight.

        try:
            issues = self._client.get_active_issues()
        except AuthRequiredError:
            self._auth_required.set()
            self._on_status("auth_required", "Jira rejected the saved credentials. Please reauthenticate.")
            return
        except PermissionDeniedError as exc:
            self._consecutive_failures += 1
            self._on_status("error", str(exc))
            return
        except RateLimitedError as exc:
            self._consecutive_failures += 1
            if exc.retry_after:
                time.sleep(min(exc.retry_after, BACKOFF_MAX_SECONDS))
            self._on_status("stale", "Rate limited by Jira; backing off.")
            return
        except Exception as exc:
            # Network/API hiccup - keep the last results visible as stale and
            # retry with backoff; never let this crash the poll loop.
            self._consecutive_failures += 1
            self._on_status("stale", f"Jira is unreachable: {exc}")
            return
        finally:
            self._poll_lock.release()

        self._consecutive_failures = 0
        self._on_status("connected", "")
        self._on_issues(issues)

        current_ids = {issue["id"] for issue in issues}
        if self._known_ids is not None:
            new_ids = current_ids - self._known_ids
            for issue in issues:
                if issue["id"] in new_ids:
                    summary = issue.get("fields", {}).get("summary", "")
                    self._on_new_ticket(issue["key"], summary, self._client.issue_url(issue["key"]))

        self._known_ids = current_ids
        state_store.save_known_ids(current_ids, time.time())
