# Privacy and Data Handling

Status: Draft. This document does not claim legal compliance. Applicable law must be researched and reviewed by a qualified person before real users are onboarded.

## 1. Data inventory

| Data | Purpose | Location | Retention |
|---|---|---|---|
| Account email, password hash | Authentication | Database | Until account deletion |
| Resume files | Parse into profile | Private object storage | Until user deletes or account deletion |
| Profile entries and evidence | Matching and preparation | Database | Same |
| Embeddings | Retrieval | Database | Same |
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

Resume text and evidence snippets are sent to the LLM provider to perform analysis. The user is told this plainly during onboarding. Free-tier providers may use submitted data to improve products. Production must use a tier with documented no-training terms. Provider terms are recorded in `docs/providers/`.

## 4. User rights features

View and correct profile, export data, delete account (see identity-and-data-lifecycle-requirements.md), disconnect connectors, delete individual resumes and evidence.

## 5. Regulation research list

To research and confirm with qualified advice before launch, per market: India DPDP Act, EU and UK GDPR, CCPA and other US state laws, Canada PIPEDA, UAE, Singapore PDPA, Australia Privacy Act. Cross-border transfer implications for LLM and hosting providers. Cookie consent obligations. No conclusions are drawn here.

## 6. Open decisions

Retention period for backups, retention for audit events, whether usage records are anonymized or deleted, hosting region.
