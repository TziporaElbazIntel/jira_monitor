# Jira Tray Monitor - Privacy Policy (Draft)

**Status: Draft for organizational privacy, security, and legal review. Not approved for publication.**

This draft describes the current desktop implementation. Before publication,
replace every bracketed placeholder, confirm the production configuration and
hosting arrangements, and obtain the required organizational approvals.
This document is not legal advice.

- Effective date: [DATE AFTER APPROVAL]
- Application owner / responsible entity: [APPROVED NAME]
- Privacy contact: [EMAIL OR CONTACT PAGE]
- Support contact: [EMAIL OR SUPPORT PAGE]
- Intended audience: [ORGANIZATION / AUTHORIZED INTERNAL USERS]

## 1. Purpose

Jira Tray Monitor is a desktop application that displays the signed-in user's
active, assigned Jira issues and provides desktop notifications when issues
newly match the configured filter. It is not a timesheet application.

The application reads Jira data on the user's behalf. It does not create,
modify, or delete Jira issues. Jira permissions determine which information
the user can access.

## 2. Information processed

Depending on the configured authentication method, the application processes:

- Account information returned by Jira or supplied during sign-in, which may
  include email address, account identifier, and display name.
- Authentication credentials: a personal API token, a Personal Access Token
  for an explicitly configured on-premises deployment, or OAuth access and
  refresh tokens. The current OAuth implementation also handles and stores
  application Client ID and Client Secret values.
- Jira site information, including its URL and, for OAuth, its cloud identifier.
- Matching issue identifiers, issue keys, summaries, statuses, and update times.
- Local application settings and the timestamp of the last successful poll.

The normal issue-search request does not request issue descriptions,
comments, attachments, or worklogs.

## 3. Purposes of processing

Information is used to authenticate the user, retrieve matching issues,
display issue lists and account information, open issues in the user's
browser, and deliver notifications. Issue identifiers and polling timestamps
are saved to avoid duplicate notifications across restarts.

The application normally checks Jira approximately every 60 seconds, subject
to configuration, random timing variation, and retry delays.

## 4. Local storage and retention

Authentication credentials and associated account/site information are saved
through the operating system's credential manager, such as Windows
Credential Manager, macOS Keychain, or Linux Secret Service. They persist
across application restarts; there is no automatic time-based deletion.

The current OAuth implementation also saves a separate application-client
credential entry that survives sign-out.

The application stores the latest successful issue-ID snapshot and poll
timestamp in a local application-data file. Each successful poll replaces
that snapshot. A separate local file stores the user's startup confirmation.
These files are not automatically deleted after 24 hours.

Issue details used by the tray are held in application memory rather than
deliberately saved to the application's state file. Notifications include an
issue key and up to 200 characters of its summary. The operating system may
retain notification content in notification history or show it on the lock
screen, depending on the user's settings.

Operating-system backups, crash dumps, and administrative device-management
tools may have their own retention rules.

## 5. Connections and recipients

The current application has no application-operated backend. It connects to
the configured Jira service. In Jira Cloud OAuth mode, it also connects to
Atlassian's authentication and API services. Browser-based sign-in may use
the organization's identity provider.

Requests necessarily expose connection information, such as the source IP
address, to the receiving services and any applicable organizational network
infrastructure. Atlassian, the identity provider, and the organization govern
their own processing, hosting locations, and retention.

Desktop notifications are delivered through the operating system's
notification facilities. Selecting an issue opens its Jira URL in the
default browser.

The application code does not include an analytics or advertising telemetry
service. It does not implement a separate upload of credentials or issue
contents to the application maintainer.

## 6. User controls and deletion

Users can mute application notifications, exit the application to stop
polling, and sign out to remove the saved sign-in bundle and local issue
snapshot.

**Sign-out does not currently delete the separate saved OAuth application
Client ID/Secret entry, the local startup-confirmation setting, or operating
system notification history.** For complete local removal, remove remaining
application credentials from the OS credential manager, delete the
application-data directory, and clear relevant notifications as appropriate.
Contact support for platform-specific assistance.

Uninstalling or deleting the executable alone should not be assumed to
remove saved credentials or application data.

For OAuth, users can revoke the application's access through their
Atlassian account's connected-app settings. API tokens can be revoked in
Atlassian account security settings; on-premises Personal Access Tokens can
be revoked in the Jira profile's token settings. Local deletion is not the
same as revocation at Jira.

## 7. Security and user responsibilities

The application uses HTTPS with certificate validation and the OS
credential-manager integration. These measures do not guarantee absolute
security. Users should protect their OS account and should not share tokens,
application secrets, or screenshots containing sensitive Jira information.

Notification visibility should be configured according to organizational
policy, particularly on shared devices or lock screens.

## 8. Privacy requests and applicable policies

For questions, access/correction/deletion requests, or privacy concerns,
contact [PRIVACY CONTACT]. Requests concerning Jira records themselves may
also require the Jira administrator or the organization's privacy team.

[PRIVACY/LEGAL REVIEW: INSERT APPLICABLE LEGAL BASIS, RESPONSIBLE ENTITY,
RELEVANT USER RIGHTS, INTERNATIONAL-TRANSFER INFORMATION, AND LINKS TO
APPLICABLE ORGANIZATIONAL POLICIES AS REQUIRED.]

## 9. Changes

The responsible entity will update this policy when the application's
processing changes and communicate material changes through
[APPROVED NOTIFICATION METHOD].

## Publication checklist - remove after approval

- Confirm this is the policy for Jira Tray Monitor, not "Timesheets for Jira."
- Complete all placeholders and verify the actual release's behavior.
- Confirm OAuth scopes and site-access restrictions against the production
  authorization flow; do not promise single-site access without verification.
- The current desktop OAuth design collects an application secret. It must
  not be embedded in a distributed executable or configuration file.
- If a backend is introduced for distribution-ready OAuth, revise this
  policy before release to identify the backend operator, processed data,
  storage, retention, access controls, and hosting/transfer arrangements.
- Confirm the personal-data declaration with the organizational privacy team.
- Obtain privacy, security, and legal approval as required.
- Publish the approved policy at a stable URL accessible to intended users
  and compliant with Atlassian's publication requirements. A local Markdown
  file alone is not the URL required by the Distribution form.
