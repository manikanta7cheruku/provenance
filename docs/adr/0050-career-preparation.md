# ADR-0050: Career preparation

Status: Accepted (checkpoint 3.2).

## Context
The product tells a person whether a job fits and what their evidence shows. The next question is "what should I do about it before the interview?" The requirements document (career-preparation-requirements.md) asks for structured actions (questions, answer guidance, concepts, resume and project questions, coding and system design, behavioral, company research, a plan, gap analysis, a mock interview) and for outreach and referral drafts the person sends. It also says this is a workflow on existing services, not a new agent (ADR-0017), that every statement about the person must trace to their evidence, and that predictions must be hedged. The risks are a model that flatters, invents experience or interviewers, claims a question will be asked, treats missing evidence as proof of inability, or sends something for the person.

## Decision

**Code decides what to prepare. A model only writes.** Everything that can be a rule is one, in `pv_domain.preparation`:
- *Priority.* A required requirement the profile does not show is **Critical**, a partly shown one is **High**, a preferred one not met is **Useful**, anything else **Optional**. The rules are versioned (`prep-rules-1`) and the screen says how they work.
- *Difficulty.* From the seniority the posting asks for and the priority, never above what the seniority supports.
- *What applies.* Coding only for software roles, system design only for software roles that ask for some seniority, project questions only when the profile has projects, questions about the resume only when there is evidence.
- *The plan.* From today to the interview date, critical first, with a review and a mock interview on the last two days. No date gives no plan.
- *Progress.* Counted from what the person ticks, by stable keys.
- *Company.* What the posting itself says, plus notes and a link the person adds. Nothing is looked up on the web for them.

**Generated material is proposed, then checked.** One task (`prepare_job`) writes one kind of preparation for one job. The model sees every requirement (labelled R1, R2, with whether the evidence shows it) and the evidence the check found (E1, E2) between markers it cannot contain. It can only cite what it was shown. Code then checks each item's text and guidance against the evidence the item cited and the job's own words (the same check tailoring and drafts use), stores every claim that is in neither, and marks an item that cites no evidence "your profile does not currently contain enough evidence to answer this confidently". A requirement that is not shown is named to the model so it explains the idea in general terms and never says the person has done it. Nothing is hidden: the person sees the unsupported claims beside the item.

**Messages are drafts the person sends.** Outreach and referral messages are written like application drafts (first person, only facts from the evidence, no greeting or placeholder, no claim to know anyone), checked as drafts are, editable (an edit is re-checked and becomes the person's own, and writing again asks first), and copied by the person. Nothing is sent by Provenance.

**A mock interview that is mostly rules.** The questions come from the concepts in priority order, a gap is asked as a gap ("how would you approach learning it"), one at a time. Each answer is scored from the answer by a rubric computed in code (structure, specifics, relevance, honesty), and any claim in it that is not in the person's evidence is named so they can fix the answer or the profile. No model is involved, so it is instant, repeatable and cannot flatter. A model-written follow-up can be added later if evaluation shows it is worth it.

**Hedged words, always.** "Likely question", "High-priority preparation area", "based on this job description". The screen never says a question will be asked, invents an interview process, or reports what employees say. A rule, a tested prompt and a label on every list say so.

**Cached, explicit, limited.** One output per person, job and kind. Writing again is explicit (and asks first after an edit). A task for an older request does nothing. Starts are rate limited and every start is audited without its text. Each write is a billable unit for the quota work in 3.3.

**Off without a key, useful without one.** The overview, the plan, progress, company notes and the mock interview need no model. Only the written material needs one, and without a key it says so in one sentence.

## Alternatives considered
- **A new preparation agent.** Rejected (ADR-0017): code owns the control flow, and a model is asked for wording only.
- **Let the model rank the gaps.** Rejected: a ranking that changes between runs cannot be explained. The rules can.
- **Fetch the company's pages.** Deferred. It needs the hardened fetch, terms checks per site, and a place to show the source and retrieval time. Today the screen shows only what the posting states and what the person adds (carryover).
- **Curated learning resources with links.** Deferred: a list of real, reviewed resources must be built and kept current (carryover). Until then the product names no resource and no URL, which is why the prompt forbids them.
- **A model-scored mock interview.** Deferred: the rubric is deterministic and honest, and a model score would need an evaluation set (3.6) before it can be trusted.
- **A chat.** Rejected as the primary interface: structured actions first.

## Consequences
- A person without an evidence check sees what is needed and nothing generated.
- The rubric is blunt. It rewards structure, numbers and names, and catches claims not in the profile. It cannot judge whether an answer is good for this company.
- "Not shown" is wording the product is careful with everywhere: it means the profile does not say so, not that the person cannot do it.
- Written material was tested with a stub model. Quality on a real model is carryover (C-125).

## Evidence
Unit tests (31) for the rules: every priority case, the example in the requirements document (AWS critical, the partial ones high), gates excluded, coverage counts, difficulty by seniority and never beyond it, role family, coding and design only where they apply, the plan (no date, past, today, a week, capped), progress, the mock questions and the rubric (a good answer, a thin one, a long one, an answer that misses the point, a claim not in the profile). Integration tests with the real database (26): forced Row Level Security and checks, a job not yet checked, the ranked overview, what applies, ownership on every route, the plan, progress, company notes, queued writing and one at a time, good output with evidence and flagged items, an invented fact listed, messages checked and edited and rewritten, unusable output, needing evidence, the prompt, a missing key, retry then failure, an older request, the mock interview (question by question, claims named, finished, replaced, ownership), cleanup on delete, audit without text. Browser tests (15) with axe in light and dark on every tab, and a phone.
