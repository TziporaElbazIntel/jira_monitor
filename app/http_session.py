"""Shared HTTP session for talking to Jira.

Uses a PAC (proxy auto-config)-aware session so this app reaches internal
sites the same way a browser does on networks where the proxy is only
published via a setup script (Windows Internet Options "Use setup script"),
rather than a plain proxy host/port. Falls back to a normal session if no
PAC is configured.
"""
from pypac import PACSession

session = PACSession()
