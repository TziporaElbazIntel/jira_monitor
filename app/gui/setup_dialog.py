"""Tkinter-based GUI for first-run setup, reauthentication, and simple
account info (SPECIFICATION.md 4.1: "packaged no-console builds must not
depend on terminal input").

Each function here opens a small blocking window and returns once the user
submits/cancels/acknowledges it. Keeping these as plain functions (rather
than a long-lived app window) lets `main.py` call them from a background
thread via `tkinter`'s default single-threaded model, by always running
them on the main thread before/around the tray's own event loop.
"""
import tkinter as tk
from tkinter import ttk

from app import config
from app.config import API_TOKEN_SETTINGS_URL, OAUTH_APPS_CONSOLE_URL, OAUTH_CALLBACK_PORT, OAUTH_SCOPES


class SetupCancelled(Exception):
    """The user closed the setup/reauth dialog without submitting."""


def collect_credentials(prefill_email: str = "", error_message: str = ""):
    """Blocking dialog collecting (email, api_token). Raises SetupCancelled
    if the window is closed without submitting.

    In the opt-in `datacenter` testing mode (SPECIFICATION.md scopes this
    app to Cloud only; see `config.DEPLOYMENT_TYPE`), the field collects a
    Personal Access Token instead and email is optional."""
    email = {"value": None}
    token = {"value": None}

    root = tk.Tk()
    root.title("Connect your Jira account")
    root.resizable(False, False)

    ttk.Label(root, text="Jira Tray Monitor Setup", font=("TkDefaultFont", 11, "bold")).grid(
        row=0, column=0, columnspan=2, padx=12, pady=(12, 4)
    )
    if config.IS_DATACENTER:
        instructions = (
            "1. Create a Personal Access Token from your Jira profile\n"
            "   settings (usually under your avatar menu).\n"
            "2. Paste it below. Email is optional for this on-prem\n"
            "   testing mode.\n"
            "The token is stored only in your OS credential manager."
        )
    else:
        instructions = (
            "1. Create a personal API token at:\n"
            f"   {API_TOKEN_SETTINGS_URL}\n"
            "2. Enter your Atlassian account email and the token below.\n"
            "The token is stored only in your OS credential manager."
        )
    ttk.Label(root, text=instructions, justify="left").grid(
        row=1, column=0, columnspan=2, padx=12, pady=4, sticky="w"
    )

    if error_message:
        ttk.Label(root, text=error_message, foreground="red", wraplength=380, justify="left").grid(
            row=2, column=0, columnspan=2, padx=12, sticky="w"
        )

    email_label = "Email (optional):" if config.IS_DATACENTER else "Email:"
    ttk.Label(root, text=email_label).grid(row=3, column=0, padx=12, pady=4, sticky="e")
    email_var = tk.StringVar(value=prefill_email)
    email_entry = ttk.Entry(root, textvariable=email_var, width=42)
    email_entry.grid(row=3, column=1, padx=12, pady=4)

    token_label = "Personal Access Token:" if config.IS_DATACENTER else "API Token:"
    ttk.Label(root, text=token_label).grid(row=4, column=0, padx=12, pady=4, sticky="e")
    token_var = tk.StringVar()
    # `show="*"` masks the token as it's typed, per spec ("Mask token input").
    token_entry = ttk.Entry(root, textvariable=token_var, width=42, show="*")
    token_entry.grid(row=4, column=1, padx=12, pady=4)

    def on_submit(_event=None):
        email["value"] = email_var.get()
        token["value"] = token_var.get()
        root.destroy()

    def on_cancel():
        root.destroy()

    button_frame = ttk.Frame(root)
    button_frame.grid(row=5, column=0, columnspan=2, pady=12)
    ttk.Button(button_frame, text="Connect", command=on_submit).pack(side="left", padx=6)
    ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side="left", padx=6)

    (token_entry if config.IS_DATACENTER else email_entry).focus_set()
    root.bind("<Return>", on_submit)
    root.protocol("WM_DELETE_WINDOW", on_cancel)
    root.mainloop()

    if token["value"] is None:
        raise SetupCancelled("Setup was cancelled before credentials were submitted.")
    return email["value"], token["value"]


def collect_oauth_client(prefill_client_id: str = "", error_message: str = ""):
    """Blocking dialog collecting (client_id, client_secret) for orgs whose
    authentication policy blocks Basic Auth/API tokens and requires real
    Atlassian OAuth 2.0 (3LO) sign-in instead (see `app/auth/oauth_flow.py`).
    Raises SetupCancelled if the window is closed without submitting."""
    client_id = {"value": None}
    client_secret = {"value": None}

    root = tk.Tk()
    root.title("Connect your Jira account")
    root.resizable(False, False)

    ttk.Label(root, text="Jira Tray Monitor Setup", font=("TkDefaultFont", 11, "bold")).grid(
        row=0, column=0, columnspan=2, padx=12, pady=(12, 4)
    )
    instructions = (
        "Your organization requires Atlassian sign-in (OAuth) instead of API\n"
        "tokens. One-time setup:\n"
        f"1. Register an app at:\n   {OAUTH_APPS_CONSOLE_URL}\n"
        "2. Under Authorization, enable OAuth 2.0 (3LO) with callback URL:\n"
        f"   http://localhost:{OAUTH_CALLBACK_PORT}/callback\n"
        "3. Under Permissions, add the Jira API with scopes:\n"
        f"   {OAUTH_SCOPES}\n"
        "4. Paste the app's Client ID and Secret below, then click Connect\n"
        "   to sign in with Atlassian in your browser."
    )
    ttk.Label(root, text=instructions, justify="left").grid(
        row=1, column=0, columnspan=2, padx=12, pady=4, sticky="w"
    )

    if error_message:
        ttk.Label(root, text=error_message, foreground="red", wraplength=380, justify="left").grid(
            row=2, column=0, columnspan=2, padx=12, sticky="w"
        )

    ttk.Label(root, text="Client ID:").grid(row=3, column=0, padx=12, pady=4, sticky="e")
    client_id_var = tk.StringVar(value=prefill_client_id)
    client_id_entry = ttk.Entry(root, textvariable=client_id_var, width=42)
    client_id_entry.grid(row=3, column=1, padx=12, pady=4)

    ttk.Label(root, text="Client Secret:").grid(row=4, column=0, padx=12, pady=4, sticky="e")
    client_secret_var = tk.StringVar()
    client_secret_entry = ttk.Entry(root, textvariable=client_secret_var, width=42, show="*")
    client_secret_entry.grid(row=4, column=1, padx=12, pady=4)

    def on_submit(_event=None):
        client_id["value"] = client_id_var.get()
        client_secret["value"] = client_secret_var.get()
        root.destroy()

    def on_cancel():
        root.destroy()

    button_frame = ttk.Frame(root)
    button_frame.grid(row=5, column=0, columnspan=2, pady=12)
    ttk.Button(button_frame, text="Connect", command=on_submit).pack(side="left", padx=6)
    ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side="left", padx=6)

    (client_id_entry if not prefill_client_id else client_secret_entry).focus_set()
    root.bind("<Return>", on_submit)
    root.protocol("WM_DELETE_WINDOW", on_cancel)
    root.mainloop()

    if client_secret["value"] is None:
        raise SetupCancelled("Setup was cancelled before credentials were submitted.")
    return client_id["value"], client_secret["value"]


def show_message(title: str, message: str) -> None:
    """Simple blocking acknowledgement dialog (signed-in confirmation,
    account info, or an actionable error) without a console dependency."""
    root = tk.Tk()
    root.title(title)
    root.resizable(False, False)
    ttk.Label(root, text=message, wraplength=380, justify="left").grid(
        row=0, column=0, padx=16, pady=16
    )
    ttk.Button(root, text="OK", command=root.destroy).grid(row=1, column=0, pady=(0, 12))
    root.bind("<Return>", lambda _event: root.destroy())
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


def confirm(title: str, message: str) -> bool:
    """Blocking Yes/No dialog. Closing the window counts as No."""
    answer = {"value": False}
    root = tk.Tk()
    root.title(title)
    root.resizable(False, False)
    ttk.Label(root, text=message, wraplength=380, justify="left").grid(
        row=0, column=0, columnspan=2, padx=16, pady=16
    )

    def on_yes():
        answer["value"] = True
        root.destroy()

    def on_no():
        root.destroy()

    button_frame = ttk.Frame(root)
    button_frame.grid(row=1, column=0, columnspan=2, pady=(0, 12))
    ttk.Button(button_frame, text="Yes", command=on_yes).pack(side="left", padx=6)
    ttk.Button(button_frame, text="No", command=on_no).pack(side="left", padx=6)

    root.protocol("WM_DELETE_WINDOW", on_no)
    root.mainloop()
    return answer["value"]
