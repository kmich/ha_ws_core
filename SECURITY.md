# Security Policy

## Supported versions

Weather Station Core is a community project. Security fixes are applied to the latest
released version. Please make sure you are on the current release before reporting.

## Reporting a vulnerability

Please report suspected security issues **privately** rather than in a public issue:

- Use GitHub's **Report a vulnerability** button under the repository's **Security** tab
  (Private vulnerability reporting), or
- open a minimal issue asking for a private contact channel, without including any
  sensitive details.

Please include the affected version, a description of the issue, and reproduction steps.
We aim to acknowledge reports within a few days.

## Handling credentials

`ws_core` can store API keys and passwords for optional forecast providers and upload
networks in the Home Assistant config entry. The diagnostics export redacts all
credential-like fields and location coordinates, so it is safe to attach to a bug report.
If you shared a diagnostics export produced before v2.6.2, rotate any keys it may have
contained, as earlier versions did not redact them.
