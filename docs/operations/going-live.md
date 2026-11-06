# Going live: what only the owner can do

Everything below needs an account, money, a decision or a person. Do them in order. Each step says how to know it is done.

1. **Choose a host.** One virtual machine with Docker (2 CPUs, 4 GB memory, 40 GB disk is enough to start) from any provider, in the region you want your data in. Done when you can SSH in and `docker run hello-world` works.
2. **Choose a domain** and point its A record at the machine. Open ports 80 and 443 only. Done when `ping your.domain` answers with the machine's address.
3. **Get a mail provider** (Resend, Brevo or your own) and verify the sending domain. Done when you have SMTP host, user and password.
4. **Choose a model plan.** A paid plan whose terms say inputs are not used to train models (C-42). Set the prices and a daily spend ceiling. Done when a job check works with that key.
5. **Fill `.env.production`** from `.env.production.example`. Generate each secret with `openssl rand -base64 48`. Store a copy in a password manager. Done when `check-config` prints no FAIL.
6. **Deploy:** `git clone`, `cp .env.production.example .env.production` and fill it, then `deploy/deploy.sh`. Done when the smoke test prints `15 passed, 0 failed`.
7. **Make yourself administrator:** register with an invite from `create-invite`, then `promote-admin`. Turn on nothing else yet.
8. **Backups:** schedule `deploy/backup.sh` nightly (cron), copy `./backups` to a second place (C-160), and run `deploy/restore.sh <backup> --drill` once. Done when a backup exists off the machine and the drill passed on the real host.
9. **Alerts:** schedule `pv_api.cli check-alerts` every 5 minutes and send a message when it exits 1 (C-141).
10. **Legal:** a lawyer reads the privacy policy and the terms. Add the company name, the contact address and the governing law, and remove the draft banner (C-155).
11. **Drills on the real host:** stop the worker, stop the database, deploy and roll back (docs/operations/drills.md). Done when each behaves as recorded there.
12. **Invite a few people**, watch Health for a week, then set the alert thresholds from what you saw (C-140).

Do not open sign-up to anyone until steps 8 to 11 are done.
