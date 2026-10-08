# Search, Company and Source Requirements

Status: Decided (Phase 0)

## 1. Principle

Company and source are first-class filters in the search model, in the database schema, and in the source resolver. They are not text keywords.

## 2. Structured search intent

```
SearchIntent:
  roles: list[str]
  skills: list[str]
  experience: {min_years, max_years} | null
  locations: list[LocationFilter]
  work_mode: remote | hybrid | onsite | any
  employment_types: list
  compensation: {min, currency, period} | null
  companies: list[CompanyRef]          # empty means any
  sources: list[SourceKey] | "all_permitted"
  exclusions: list
  candidate_authorization_context: derived from profile, never from free text
```

Natural language is converted to this structure by one validated LLM call (class L). Everything after that is code and SQL. The LLM is not responsible for filtering.

## 3. Required query shapes

| Example | Resolved handling |
|---|---|
| AI Engineer, India, 0 to 2 years | Role and location filters over permitted sources |
| AI Engineer, remote, any company | Remote filter, no company constraint |
| Backend Engineer at Google, India | Company filter. Resolve Google in the company registry. Prefer first-party career system if capable, else say so |
| AI Engineer at selected companies | Company list resolved individually |
| Backend roles on selected permitted sources | Source filter checked against registry capabilities |
| Jobs from a specific platform | Capability check. Search, or offer import. Never substitute silently |

## 4. Resolver decision table

| Condition | Outcome | User message pattern |
|---|---|---|
| Source has can_search and compliance_status verified | search | "Searching X" |
| Source lacks can_search but supports user import | import_required | "Automated search for X is not available. Import jobs by URL, paste, or CSV/XLSX and we will analyze them." |
| Source disabled or compliance unverified or expired | unavailable | "X is currently unavailable. Reason: ..." |
| Company has first-party ATS adapter | prefer first party | "Using the company's own career system" |
| Company has no known first-party source | fall back to permitted aggregators that have supports_company_filter, else import | Explain which was used |

Never claim a platform was searched if jobs were user supplied. Copy is generated from source and acquisition_method.

## 5. Source registry (first-class component)

Registry is data in the database, seeded from versioned files, editable by admins with audit events.

| Field | Meaning |
|---|---|
| key, display_name | Identity |
| source_type | ats_board, job_api, public_feed, company_careers, user_import_only |
| adapter | Adapter identifier or null |
| endpoint_or_feed | Documented endpoint or feed URL |
| capabilities | can_search, can_enumerate, supports_full_description, supports_company_filter, supports_location_filter, requires_auth, requires_attribution |
| auth_requirements | None, API key, OAuth, and where the credential is stored |
| compliance_status | verified, unverified, restricted, prohibited |
| terms_checked_at, terms_url, verification_owner | Evidence of review |
| rate_limit, quota_policy, min_poll_interval | Enforced by the fetch layer |
| attribution_text | Rendered where required |
| geographic_coverage | Country list |
| enabled | Admin switch |
| health_status, last_success_at, last_failure_at, failure_streak | Updated by fetch logs. Drives circuit breaker |
| compliance_notes | Free text |

Rules:

1. A source cannot be enabled unless compliance_status is verified and terms_checked_at is within the review window set in configuration.
2. The fetch layer enforces min_poll_interval and rate limits regardless of caller.
3. Capabilities are never assumed to be uniform across sources.
4. Failing sources trip a circuit breaker. Other sources continue.

## 6. Company registry

canonical_name, aliases, domain, career_url, ats_platform, ats_board_id, industry, country, source availability, last_verified_at. Company resolution is deterministic: exact alias match, then normalized match, then trigram similarity with a confidence threshold, and ambiguity returns candidates for the user to pick. An LLM does not choose the company.

## 7. Filtering and ranking in SQL

Role, location, remote, salary, employment type, source, company, seniority, date discovered and analysis status are SQL predicates over normalized columns. Sorting is SQL. Saved views store the filter definition, not results.

## 8. Geography

Initial markets: India first, then South Asia neighbors, US, Canada, UK, Germany, UAE, Singapore, Australia. Work authorization rules are per-country data records with a version, never hardcoded branches. Salary parsing handles currencies and local conventions such as LPA, with unit tests.

## 9. Acceptance criteria

1. Each example in section 3 produces a deterministic plan that can be unit tested without an LLM.
2. Selecting an unsupported platform never yields silent substitution.
3. Search progress shows persisted counters.
4. The UI shows, for every result list, which sources were searched and which jobs were imported by the user.
