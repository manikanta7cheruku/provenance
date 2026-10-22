# Provider: Mailpit (development mail inbox)

| Field | Value |
|---|---|
| Role in Provenance | Local inbox that catches verification and reset emails sent by the worker in development |
| Official documentation URL | https://mailpit.axllent.org/ |
| Container image | `axllent/mailpit`, tag from `MAILPIT_TAG` (default `v1.30.5`) |
| Capability class | Self-hosted development dependency |
| Current integration status | Part of the default compose stack since checkpoint 1.4 (UI port 8025, SMTP port 1025, STARTTLS off) |
| Last reviewed date | 2026-10-22 |
| Next review due | Checkpoint 3.7 (production email provider selection) |
| Notes | The `v1.30.5` release exists on the official GitHub release list (a security release). Newer releases exist (`v1.31.0` at the time of review). If `docker compose pull` cannot find the tag, change `MAILPIT_TAG` in `.env` to a tag shown on the project's release page. Mailpit must stay on localhost: never expose its ports publicly. Without it, set `SMTP_HOST=` empty and emails are written to the worker log. Production requires a real SMTP provider |
