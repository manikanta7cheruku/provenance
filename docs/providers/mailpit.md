# Provider: Mailpit (development mail inbox)

| Field | Value |
|---|---|
| Role in Provenance | Optional local inbox that catches verification and reset emails in development |
| Official documentation URL | https://mailpit.axllent.org/ |
| Container image | `axllent/mailpit`, tag from the `MAILPIT_TAG` variable. Verify the tag on Docker Hub before use |
| Capability class | Self-hosted development dependency |
| Current integration status | Optional compose profile `mail` (checkpoint 1.3) |
| Last reviewed date | 2026-10-08 |
| Next review due | Checkpoint 3.7 (production email provider selection) |
| Notes | Without it, development emails are written to the API log. Production requires a real SMTP provider (SMTP_HOST) |
