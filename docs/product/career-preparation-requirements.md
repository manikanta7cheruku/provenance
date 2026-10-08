# Career Preparation Requirements

Status: Decided (Phase 0). Implemented in Phase 3, checkpoint 3.2.

## 1. Purpose

Answer: "Given this specific job and what we know about this candidate, what should this person prepare next, and why?" It is not a generic interview chatbot.

## 2. Pipeline

```
Job -> Requirements -> Candidate Evidence -> Candidate Gaps -> Interview Topics -> Questions -> Preparation Plan
```

Built on existing services: extraction output, evidence retrieval, requirement verdicts, scoring gap logic, grounding verifier, source compliance, rate limiting, quotas. No new agent (ADR-0017).

## 3. Structured actions (primary UX)

| Action | Output | Class |
|---|---|---|
| Interview questions | Questions grouped by category and difficulty, tied to requirements | L |
| Model answer guidance | Guidance per question grounded in candidate evidence. Unsupported claims shown as insufficient evidence | L plus verification |
| Concepts to prepare | Prioritized learning list: Critical, High priority, Useful, Optional | D prioritization, L explanations |
| Resume questions | Claims and technologies an interviewer is likely to probe | L from evidence |
| Project questions | Deep questions on the candidate's actual projects | L from evidence |
| Technical preparation | Role specific concepts only | L |
| Coding and DSA | Topics and patterns, only for software roles, prioritized by requirements and gaps | D plus L |
| System design | Topics by target seniority, only for applicable roles | D plus L |
| Behavioral | STAR-style prompts using real experiences | L |
| Company research | Summary from allowed sources with URL and retrieval timestamp | W |
| Interview preparation plan | Roadmap by interview date, strengths, gaps, seniority, difficulty | D scheduling, L text |
| Gap analysis | Demonstrated, partial, missing evidence, likely gap, unverifiable | D |
| Mock interview | One question at a time, rubric scored feedback, follow-up recommendations | W with adaptive routing |
| Ask anything | Free-form secondary action, grounded in the same evidence | L |

The primary interface is these actions. Free-form chat is secondary.

## 4. Deterministic rules

- Priority: Critical when a required requirement is unverified or a blocker for the interview topic. High when required and partial. Useful when preferred and not met. Optional otherwise. Rules are versioned config.
- Difficulty: Easy, Medium, Hard, Expert, capped by role seniority and requirement level.
- Only categories relevant to the role appear.
- Progress is computed from stored completion state.

## 5. Grounding

| Statement about | Must trace to |
|---|---|
| The candidate | Evidence chunk IDs |
| The job | The analyzed posting and requirement spans |
| The company | An allowed source with URL and retrieval timestamp |
| A learning resource | A real URL recorded with title, source type, retrieval timestamp. URLs are never generated from model memory. They come from a curated resource list or from permitted retrieval |

If a candidate-specific claim cannot be verified, the UI shows: "Your profile does not currently contain enough evidence to answer this confidently," and suggests what to learn or add.

Missing evidence is never presented as proof the candidate lacks the skill.

## 6. Safety wording

Use: "Likely question", "High-priority preparation area", "Potential interview topic", "Based on this job description". Never claim a question will be asked. Never invent interview processes, employee experiences, or hiring practices. Facts, predictions and recommendations are visually distinguished.

## 7. Company research sourcing

Official company sources and legally accessible public sources only. Respect robots.txt, terms, authentication boundaries, rate limits, copyright. No bypassing CAPTCHAs, paywalls, anti-bot or access controls. All fetching goes through the same SSRF-hardened fetch layer as URL import.

## 8. UI requirements

Preparation overview, priority cards, requirement coverage, skill gaps, question groups with expandable answers, evidence references, learning resources, progress, roadmap, mock interview entry, Ask Anything secondary. States: loading, empty, partial, error, retry, insufficient evidence, quota exceeded.

## 9. Quotas and cost

Each generation action is a billable unit. Results are cached per (user, job, action, inputs hash). Regeneration is explicit.

## 10. Acceptance criteria

1. Example: job needs Python, FastAPI, PostgreSQL, REST, AWS. Candidate evidence covers all but AWS. Output ranks AWS as Critical gap, then PostgreSQL indexing, REST design, FastAPI architecture as High priority, and ties questions to real projects.
2. Every personalized answer has claim to evidence links, verified by the grounding verifier.
3. No resource URL exists that was not retrieved or curated.
4. Tests run with deterministic stub models.
