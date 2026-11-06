# Privacy and Data Handling

Status: Draft. This document does not claim legal compliance. Applicable law must be researched and reviewed by a qualified person before real users are onboarded.

## 1. Data inventory

| Data | Purpose | Location | Retention |
|---|---|---|---|
| Account email, password hash | Authentication | Database | Until account deletion |
| Resume files | Parse into profile | Private object storage | Until user deletes or account deletion |
| Profile entries and evidence | Matching and preparation | Database | Same |
| Evidence chunks (the text of each profile entry) and embeddings | Retrieval and search | Database | Deleted with the entry. Vectors are deleted with their chunk |
| Preferences | Search and eligibility | Database | Same |
| Imported jobs (private) | Analysis | Database | Same |
| Materials | Tailoring output | Database | Same |
| Connector tokens | Evidence import | Database, encrypted | Until disconnect or deletion |
| Usage events | Quotas and cost | Database | Anonymized after deletion where retained |
| Logs | Operations | Log store | Short, PII-free |
| Audit events | Security | Database | Per policy, minimal personal data |

## 2. Principles

Data minimization, purpose limitation, no public file URLs, signed expiring links, PII-safe logs, no resume text in logs, encryption in transit, encryption at rest where the host provides it, secret management, access audit.

## 3. LLM provider data flow

Resume text and evidence snippets are sent to the LLM provider to perform analysis. From checkpoint 1.7 the text of each profile entry is also sent to the embedding model, and a search query is sent when meaning search is used. From checkpoint 1.9 the evidence agent also sends the requirement being checked, the evidence entries it found for it and any answer the person typed to the model. An answer is kept as evidence and is deleted with the job it was given for. The user is told this plainly during onboarding. Free-tier providers may use submitted data to improve products. Production must use a tier with documented no-training terms. Provider terms are recorded in `docs/providers/`.

Resume studio content (checkpoint 2.1) is stored as the person wrote it and is not sent to a model. PDFs made from it are kept privately for the person, at most five per resume, and are deleted with the resume. Deleting a resume deletes its saved versions, its PDFs and the files. Profile entries are not affected.

## 4. User rights features

View and correct profile, export data, delete account (see identity-and-data-lifecycle-requirements.md), disconnect connectors, delete individual resumes and evidence.

## 5. Regulation research list

To research and confirm with qualified advice before launch, per market: India DPDP Act, EU and UK GDPR, CCPA and other US state laws, Canada PIPEDA, UAE, Singapore PDPA, Australia Privacy Act. Cross-border transfer implications for LLM and hosting providers. Cookie consent obligations. No conclusions are drawn here.

## 6. Decisions made in checkpoint 3.7

| Decision | Choice | Where it is built |
|---|---|---|
| Backup retention | 30 days, then gone | `BACKUP_KEEP_DAYS` in `deploy/backup.sh`; stated in the privacy policy page |
| Deleted data in backups | Stays until the backup expires. After a restore, deletions made since that backup are repeated | Runbook "data deletion request" |
| Data export | One JSON file of what the person put in, from Settings, Your data (not their password, sessions, tokens or uploaded files) | `GET /api/v1/account/export` |
| Account deletion | A durable task removes the stored files first and then every row; sessions end at once; a minimal record with no person in it is kept | `delete_account`, migration 0023 |
| Usage records after deletion | Model call counts and cost stay, without the person or any text (the link to the person is cleared) | Foreign keys set to null; tested |
| Audit events after deletion | Kept without the person (the actor is cleared) and with no email in them | Tested |
| Reports | Deleted after 7 days | `REPORT_RETENTION_DAYS` |
| Sessions | End after 7 days idle or 30 days at most | Settings |
| Public documents | A privacy policy and terms of use, as a draft, at `/privacy` and `/terms`, linked from sign-in and Settings | `features/legal` |

## 7. Still open (the owner, with a lawyer)

- A lawyer reads the privacy policy and the terms, and the draft banner is removed (C-155).
- The contact address, the company name and the governing law are added.
- The hosting region is chosen, and the regulation research list above is worked through for the markets in scope.
- The model provider plan is confirmed to be one whose terms say inputs are not used to train models (C-42). Until then the policy tells people not to enter anything they would not want a provider to see.
- Whether sign-up needs an explicit tick for the terms, and a record of the version accepted.
- Whether and when a regulator and the people affected must be told of a breach (C-156).
- Hosting backups: where the copy off the machine lives, and that it is covered by the same 30-day rule (C-160).
