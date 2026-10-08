# Business Model

Status: Draft. Contains no invented revenue or cost numbers. Numbers are filled from measurement.

## 1. Lean canvas

| Block | Content |
|---|---|
| Problem | Job seekers drown in postings, cannot tell which they truly qualify for, and generic AI tools give confident but ungrounded advice |
| Customer segments | Early-career and switching candidates, starting in India, then US, Canada, UK, Germany, UAE, Singapore, Australia |
| Unique value | Evidence-traced fit analysis. Every verdict links to proof. Honest about what was and was not searched |
| Solution | Requirement-by-requirement analysis, transparent ranking, approval-gated tailoring, interview preparation grounded in the same evidence |
| Channels | Job seeker, student and developer communities, public examples of real analyses |
| Revenue | Subscription tiers by analysis volume and generation features (later) |
| Cost structure | LLM calls, embeddings, hosting, storage, email, support |
| Key metrics | Product requirements section 7 |
| Unfair advantage | Compliance-first source strategy and an evidence graph competitors skip |
| Honest risk | Platforms and aggregators may restrict access. See source-compliance.md |

## 2. Cost model (formula, not numbers)

```
C_job_user = C_extraction / N_users_sharing_this_job
           + C_eligibility            (code only, effectively zero)
           + C_agent_calls            (tokens x price, per requirement x iterations)
           + C_embeddings_for_new_evidence
```

Levers, in order of impact:

1. **Global extraction cache.** Extraction is paid once per unique content hash, not once per user.
2. **Deterministic gates first.** A job failing a hard gate never reaches the agent.
3. **Agent budget caps.** Hard limits on iterations, tool calls, tokens.
4. **Model routing.** A cheaper model for extraction and simple verdicts. A stronger model only on escalation.
5. **Explicit generation.** Tailoring and preparation run only on user request.

The usage ledger records real cost per call, so these numbers come from data after the first cohort.

## 3. Plan architecture

```
Plan -> Entitlements -> QuotaPolicy -> UsageLedger -> RateLimiter
```

No code path checks `plan == "PRO"`. Code asks the entitlement service whether this user may perform operation X now.

Billable units:

| Unit | Definition |
|---|---|
| Discovery run | One user request that triggers a search over configured sources |
| Job analysis | One unique (user, job) analysis |
| URL analysis | One externally supplied posting analyzed |
| Material generation | One tailoring or preparation generation workflow |
| Deep evidence investigation | One agent run that used expanded retrieval |

Example plan shape (illustrative only):

| Plan | Discovery runs | Job analyses | Material generations | Scheduled runs |
|---|---|---|---|---|
| Free | small | small | small | No |
| Starter | moderate | moderate | moderate | Yes |
| Pro | high | high | high | Yes |

Free users keep full access to evidence-based explanations. The free tier limits volume, not trust features.

## 4. Free-tier LLM privacy warning

Free LLM tiers from some providers may use submitted prompts to improve their products. That is acceptable for your own test data and not acceptable for real users' resumes. Before real users are onboarded, production must use a paid tier with a no-training policy, verified in the provider's current terms. This is a launch gate.

## 5. Go-live gates

- Paid LLM tier with documented no-training terms.
- Privacy policy and terms of service reviewed by a qualified person.
- Data protection rules researched per target market (for example India's DPDP Act, GDPR for EU users, UK GDPR, CCPA for California). This repository makes no claim of compliance.
- Source compliance records current for every enabled source.
- Deletion flow tested.
- Domain with SPF and DKIM configured for email.

## 6. Pricing approach

Set no prices until cost per analyzed job and per generation are measured on at least one real cohort. Then price so a typical user's cost is a modest fraction of revenue, with headroom for support and growth. The margin is a business decision made with that data.
