"""Tests for config.py: release gate and JQL construction (section 2 and 11)."""
import importlib

import pytest

from app import config


def test_build_search_jql_defaults_to_every_user_own_issues(monkeypatch):
    monkeypatch.setattr(config, "CHANNEL_JQL", "")
    jql = config.build_search_jql()
    assert jql == "assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC"


def test_build_search_jql_combines_channel_and_user_scope(monkeypatch):
    monkeypatch.setattr(config, "CHANNEL_JQL", 'project = ABC AND labels = "team-queue"')
    jql = config.build_search_jql()
    assert "assignee = currentUser()" in jql
    assert 'project = ABC AND labels = "team-queue"' in jql
    assert "statusCategory != Done" in jql


def test_approval_not_recorded_by_default(monkeypatch):
    monkeypatch.delenv("JIRA_TRAY_APPROVAL_RECORDED", raising=False)
    reloaded = importlib.reload(config)
    try:
        assert reloaded.APPROVAL_RECORDED is False
    finally:
        importlib.reload(config)  # restore original env-derived state for other tests


def test_poll_interval_has_safe_minimum(monkeypatch):
    monkeypatch.setenv("JIRA_TRAY_POLL_INTERVAL", "1")
    reloaded = importlib.reload(config)
    try:
        assert reloaded.POLL_INTERVAL_SECONDS >= reloaded.MIN_POLL_INTERVAL_SECONDS
    finally:
        monkeypatch.delenv("JIRA_TRAY_POLL_INTERVAL", raising=False)
        importlib.reload(config)


def test_deployment_defaults_to_cloud_with_v3_api(monkeypatch):
    monkeypatch.delenv("JIRA_TRAY_DEPLOYMENT", raising=False)
    monkeypatch.setenv("JIRA_TRAY_SITE_URL", "https://example.atlassian.net")
    reloaded = importlib.reload(config)
    try:
        assert reloaded.DEPLOYMENT_TYPE == "cloud"
        assert reloaded.IS_DATACENTER is False
        assert reloaded.API_BASE == "https://example.atlassian.net/rest/api/3"
    finally:
        monkeypatch.delenv("JIRA_TRAY_SITE_URL", raising=False)
        importlib.reload(config)


def test_datacenter_mode_opts_into_v2_api(monkeypatch):
    monkeypatch.setenv("JIRA_TRAY_DEPLOYMENT", "datacenter")
    monkeypatch.setenv("JIRA_TRAY_SITE_URL", "https://jira.example.com")
    reloaded = importlib.reload(config)
    try:
        assert reloaded.IS_DATACENTER is True
        assert reloaded.API_BASE == "https://jira.example.com/rest/api/2"
    finally:
        monkeypatch.delenv("JIRA_TRAY_DEPLOYMENT", raising=False)
        monkeypatch.delenv("JIRA_TRAY_SITE_URL", raising=False)
        importlib.reload(config)


def test_invalid_deployment_type_raises(monkeypatch):
    monkeypatch.setenv("JIRA_TRAY_DEPLOYMENT", "bogus")
    try:
        with pytest.raises(RuntimeError):
            importlib.reload(config)
    finally:
        monkeypatch.delenv("JIRA_TRAY_DEPLOYMENT", raising=False)
        importlib.reload(config)


def test_ca_bundle_path_feeds_requests_verify(monkeypatch):
    monkeypatch.setenv("JIRA_TRAY_CA_BUNDLE", "/etc/ssl/internal-ca.pem")
    reloaded = importlib.reload(config)
    try:
        assert reloaded.REQUESTS_VERIFY == "/etc/ssl/internal-ca.pem"
    finally:
        monkeypatch.delenv("JIRA_TRAY_CA_BUNDLE", raising=False)
        importlib.reload(config)


def test_no_ca_bundle_defaults_requests_verify_to_true(monkeypatch):
    monkeypatch.delenv("JIRA_TRAY_CA_BUNDLE", raising=False)
    reloaded = importlib.reload(config)
    assert reloaded.REQUESTS_VERIFY is True
