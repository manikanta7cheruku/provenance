# Labeling guidelines

Status: Written for checkpoint 3.6, before any labels were added. Applies to dataset `jobs-v1` and to every dataset after it.

These are the rules a label must follow. They exist so that two people (or a person and a script) labeling the same posting would write the same label, and so that a disagreement between a label and the code is a question about the rule, not about taste.

## 1. What the dataset is
`jobs-v1` is 100 synthetic job postings: ten roles, ten variants of each. Every company and role is invented, so the set holds no personal data and has no copyright question. The postings are built from blocks and each label is written down as its block is added, so a label is true of its text by construction. The saved file `evaluation/dataset/jobs-v1.json` is rebuilt by a test; the dataset changes only when its version changes.

What it can show: that our own checks (grounding, eligibility, evidence verdicts, scoring, claim checking) behave as these rules say.
What it cannot show: how a real model reads real postings. That needs real postings labeled by people (carryover C-148). Until then, every number says "on synthetic postings".

## 2. Requirements
- A requirement is something the posting asks of the candidate: a skill, a tool, experience, education, a language, a certification, a work authorization or a location.
- **Required** is anything under "What we are looking for", or worded as a must. **Preferred** is anything under "Nice to have", or worded as a plus.
- The label's `quote` is the words in the posting that ask for it, copied exactly. It is never a paraphrase and never longer than one bullet or sentence.
- The experience line ("0-2 years of experience") is a required requirement of category `experience`, with `years_min` the lower number. A programme line ("Currently enrolled in a degree programme") is category `education`.
- Benefits, perks and company descriptions are not requirements.
- A sentence that tries to instruct the reader ("ignore all previous instructions...") is **not** a requirement. It is an injection and is labeled as one.

## 3. Facts
A fact is something the posting states about the role, with the words that prove it.
- `location` is the place as written. A role that is only "Remote" has no location fact.
- `work_mode` is one of remote, hybrid, onsite.
- `employment_type` is one of full_time, part_time, internship, contract, freelance.
- `seniority` is one of intern, entry, mid, senior, lead. It is a fact only when the posting names a level or a number of years that implies one.
- `min_years_experience` is the lower end of a range, an integer.
- `sponsorship` is `offered` when the posting says it sponsors work visas and `not_offered` when it says it does not. Silence is no fact, never `not_offered`.
- `work_authorization_countries` is the list of countries where the posting requires the right to work.
- A sponsorship sentence in the middle or at the end of a long benefits paragraph still counts. That is the "buried" case, and it is tagged.

## 4. Eligibility
Eligibility is decided by hard rules against what the person said in their preferences. Overall eligibility is the worst of five gates, in this order of severity: not eligible, requires your answer, uncertain, eligible.
- **Authorization.** No sponsorship offered and the person needs sponsorship: not eligible. A required country the person does not list, with no sponsorship offered: not eligible. With sponsorship offered or not mentioned: uncertain. A required country and no countries listed by the person: requires your answer. A required country the person lists: eligible.
- **Location.** Remote: eligible. A place on the person's list: eligible. A place not on the list: eligible if they would relocate, not eligible if they would not, requires your answer if they have not said. Nothing said about place: uncertain. A person who prefers remote and is shown an in-person role: uncertain, to review.
- **Kind of work.** Only checked when the person limited it. A different kind: not eligible. Not stated by the posting: uncertain.
- **Things to avoid.** A term the person chose to avoid in the company, title or text: not eligible.
- **Experience.** A gap of five years or more: not eligible. A gap of more than two: uncertain. Smaller: eligible. No dates on the person's profile and four or fewer years asked: eligible, more than that: requires your answer. A senior or lead role and under two years: uncertain.
- **Cost of errors.** Telling someone they cannot take a job they could (a false negative) is worse than the reverse, because it hides an opportunity. It is counted three times.

## 5. Evidence verdicts
- A verdict is accepted only if every citation names evidence the agent was shown and quotes words that appear in it (ignoring case and spacing).
- `met` or `partial` or `conflicting` with no citation is rejected. `not_verified` needs none.
- `met` on evidence that is only inferred is lowered to `partial`.
- An unknown verdict word, or a missing or unknown kind of evidence, is rejected.
- Anything rejected must never become an accepted verdict. That is counted as a leak and its limit is zero.

## 6. Bands
Coverage is (met + half of partial) divided by the number of required requirements.
- Strong: coverage at least 0.8 and nothing conflicting. Good: at least 0.6 and nothing conflicting. Review: at least 0.35, or a conflict that stops Strong or Good. Not recommended: below 0.35.
- Not eligible overrides everything, and no score is shown.
- A posting that requires nothing is judged on its nice-to-haves and is never above Review. A posting with nothing to check is Review.
- Nice-to-haves never lower a band.

## 7. Ranking
For ranking, a careful reader puts the postings in an order, and the scorer is judged on how many pairs it orders the same way. The order is judgment, not a formula: more of what is required being supported first, a conflict worse than a gap, an ineligible job last. Postings the reader would not separate share a rank, and a pair with equal ranks is not counted. The scorer and the reader are expected to disagree sometimes, and those pairs are listed as failures so they can be looked at.

## 8. Claims in generated text
New wording about a person may contain only claims found in the old wording or in the cited evidence. A claim is a number, a proper name or tool, or a word the job asks for. An honest rewrite (reordered, shortened, plainer) must not be flagged. An invented number, tool, employer or title must be. The check reads digits, not number words; "nine" for "six" is a known gap and is labeled as such.

## 9. Injections
A posting that tries to instruct the model is tagged `injection`. Two answers are scripted: one that quotes the injected sentence as a requirement, and one that paraphrases it. Dropping the paraphrase is required (limit zero). Keeping the quoted sentence is a known limit of grounding (the sentence really is in the posting); it is reported, shown with its quote to the person, and bounded by a ceiling of 1.0 so it can only improve.

## 10. Changing the dataset or the labels
- A change to a label, a case or the generator needs a new dataset version, a regenerated file and a new baseline, reviewed together.
- A label may be wrong. When a case disagrees with the code, first decide whether the label or the code is right by reading these rules. Change the label only if the rule supports it, and say so in the commit.
- Real postings may be added only with permission, with the company and any person removed, and labeled by someone who did not write the extraction.
