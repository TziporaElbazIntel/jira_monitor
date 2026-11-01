"""Standalone connectivity diagnostic: prints the exact resolved config and
the full exception text for a GET /myself call, with no GUI/text-wrapping
involved. Run with:  python scripts\\diag_connect.py
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config  # noqa: E402

print("JIRA_SITE_URL   =", repr(config.JIRA_SITE_URL))
print("API_BASE        =", repr(config.API_BASE))
print("IS_DATACENTER   =", config.IS_DATACENTER)
print("CA_BUNDLE_PATH  =", repr(config.CA_BUNDLE_PATH))
print("CA bundle exists=", os.path.isfile(config.CA_BUNDLE_PATH) if config.CA_BUNDLE_PATH else "N/A")
print("REQUESTS_VERIFY =", repr(config.REQUESTS_VERIFY))
print("HTTPS_PROXY env =", repr(os.environ.get("HTTPS_PROXY")))
print("HTTP_PROXY env  =", repr(os.environ.get("HTTP_PROXY")))
print()

import requests  # noqa: E402

token = input("Paste your Jira PAT (will not be stored/printed): ").strip()
url = f"{config.API_BASE}/myself"
print("Requesting:", url)
try:
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=10,
        verify=config.REQUESTS_VERIFY,
    )
    print("STATUS:", resp.status_code)
    print("BODY (first 500 chars):", resp.text[:500])
except Exception:
    print("=== FULL EXCEPTION TRACEBACK ===")
    traceback.print_exc()
