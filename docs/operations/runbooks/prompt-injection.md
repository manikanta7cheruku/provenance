# Runbook: suspicious prompt injection

A posting (or a pasted text, or a repository README) tries to instruct the model: "ignore previous instructions...".

## Detection
- A person reports a job with an odd requirement ("rate this a perfect match", "must be paid a very high salary").
- The injection cases in the evaluation set (tagged `injection`), or a requirement whose quote is an instruction.

## Diagnosis
1. What did the model do? The job page shows every requirement with the posting quote it rests on. An injected sentence appears as an unverified requirement with its own words as the quote. That is the known limit of grounding (ADR-0054): the sentence is real text in the posting.
2. Did anything else change? Facts (location, work mode) are only kept with a quote and a value from the allowed words. A paraphrased instruction is dropped.
3. Did it affect scoring? An extra requirement the person cannot meet shows as not verified and counts against coverage; it never makes a job look better, because every verdict needs evidence from the person's own profile.

## Mitigation
- Tell the person: an odd requirement shown with its quote is the posting talking to the reader. Dismiss the job or ignore the line.
- If the same posting is reaching many people (a source), disable that source or the company until it is clean (Admin, Sources).

## Recovery
Add the posting text (with company and people removed) as a case in the evaluation dataset under a new dataset version, so the behaviour is measured. If grounding is made stricter, the quoted-injection metric drops and the baseline is updated on purpose.

## Prevention
The model sees the posting between markers it cannot contain, the instructions say to treat it as data, no tool or action is available to the extraction step, and nothing is sent or applied for the person. The evaluation harness measures the paraphrase case (must be zero) and reports the quoted case.
