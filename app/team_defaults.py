"""Team-distribution defaults for a baked, single-file .exe build.

This lets the standalone .exe (built via `pyinstaller pyinstaller.spec`) run
with ZERO environment variables and zero companion launcher script -
teammates can be sent just the one .exe file and double-click it directly.
On first launch they'll still see the single one-time approval/consent
dialog (SPECIFICATION.md's release gate) - that's expected and is not an
extra setup step; it's remembered after the first click.

Every value here is only a *default*: if the corresponding
`JIRA_TRAY_...` environment variable is set (e.g. by `launcher.bat` or
`launcher_exe.bat`), that always wins. So filling these in does not break
the existing env-var-driven workflows - it only matters when no env vars
are set at all, which is exactly the "single .exe, nothing else" scenario.

IMPORTANT: Fill in TEAM_OAUTH_CLIENT_ID / TEAM_OAUTH_CLIENT_SECRET ONLY on
your own local machine, in your own downloaded copy of this project - never
inside a shared editor/workspace/session, and never commit a filled-in copy
to any shared or version-controlled location. Rebuild the .exe afterwards
so the real values get baked into the binary.
"""

TEAM_AUTH_MODE = "oauth"
TEAM_SITE_URL = "https://jira.idoc.intel.com"
TEAM_CHANNEL_JQL = "project = WLWG"

# Fill these in locally, then rebuild the .exe - never commit real values.
TEAM_OAUTH_CLIENT_ID = "O4oRg58FeE0Q0s3O0IMyu8sebE42cNw1"
TEAM_OAUTH_CLIENT_SECRET = "ATOAji9WlG7Uq1nsW9xNgqqVyVhU6oPdrV6Y5bcWGB6liNf9waRPmBDQ_HVe5H6Wlhs2F9494D55"
