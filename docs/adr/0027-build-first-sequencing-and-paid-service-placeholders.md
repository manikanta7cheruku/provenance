# ADR-0027: Build-first sequencing and paid-service placeholders

Status: Accepted (2026-10-30). Owner decision with an acknowledged risk.

## Context
A review of the roadmap and of competitors (see [competitor-landscape.md](../product/competitor-landscape.md)) raised the risk of building a large product before demand is confirmed. The review proposed validation gates (interviews, a hand-made concierge test, a pre-sale) before further building. The owner decided to build the complete product in sequence, without early users, and to defer paid services.

## Problem
How are the build order and the spending commitments recorded so the risk is visible and the later switch to real users is safe?

## Options considered
| Option | Result |
|---|---|
| Validate demand first, then build a thin core | Lowest wasted effort if the idea fails. Not chosen by the owner |
| Build the full product in sequence, then launch | Chosen |

## Decision
1. The roadmap in [implementation-plan.md](../roadmap/implementation-plan.md) (revision 2, 25 checkpoints) is built in order. Each checkpoint stays tested, documented and merged on its own.
2. **Accepted risk:** the product is built before any evidence of willingness to pay. Mitigations that cost little remain available at any time: real user conversations, a waitlist page, a pre-sale. They are not blocked by this decision.
3. **Paid services are placeholders until later.** The LLM provider keeps the free development tier with the owner's own test data only. Keys, model names, prices and the payment gateway are configuration or disabled interfaces. Nothing is hard coded.
4. **Launch gates that cannot be skipped** because they are legal or technical, not demand related: a paid LLM tier with no-training terms before any real person's resume is processed, official terms read before any source adapter, a legal review of privacy and terms, tested deletion and backups.
5. Pricing is set only after cost per analysis and per generation is measured. First users receive a lower founding price. The numbers are decided later.

## Why
The owner has chosen completeness over early feedback. Recording the decision, the risk and the unskippable gates keeps the plan honest.

## Consequences
- The first real feedback arrives late and may require changes to completed features. The structured design (ADR-0024, ADR-0026) limits the cost of such changes.
- Free-tier models may be shut down or changed. Model names are configuration (see [llm-provider-gemini.md](../operations/llm-provider-gemini.md)).

## Scale analysis
| Users | Posture |
|---|---|
| 10 | Developer and invited testers with test data only |
| 100 | Requires the paid LLM tier and the legal gates above |
| 10,000 | Requires the production hardening in checkpoint 3.7 |

## Revisit when
The owner wants early feedback, or a checkpoint reveals that an assumption about users is wrong.
