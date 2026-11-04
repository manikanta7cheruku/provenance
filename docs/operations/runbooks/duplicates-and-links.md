# Runbook: Duplicates, links and sightings

Two different jobs are shown as one, the same job is shown twice, a person says a match is wrong, or an administrator needs to review suggestions.

## Detection
- Find jobs: "Also posted at" under a job.
- Job page: "Where else this job appears", with the reason for every match.
- `GET /api/v1/admin/job-links?state=suggested` (and `auto`, `confirmed`, `undone`): every link with its method, score, reason and the two jobs.
- `audit_events` actions `job_link.confirmed`, `job_link.undone` and `job.match_decided` (the person's own decisions, no text).

## Diagnosis
| What is seen | Meaning | Action |
|---|---|---|
| Two different jobs are shown as one | An auto link joined them | Undo the link (below). Note its `method` and `reason`, and add a case to `tests/unit/test_dedupe.py` if a rule should have stopped it |
| The same job is shown twice | No link was made. Different company spelling (Google LLC and Alphabet), different place spelling (Bengaluru and Bangalore), or the text differs | Add the company alias to `registry_data/companies.json`. If it is only suggested, confirm it |
| A match says "Possible match" | A suggested link: the title and place agree but the text does not settle it | The person decides, or an administrator confirms or undoes |
| A person undid a match and it came back | It did not: decisions persist. Check they undid the right group | Reload. "Decide again" clears the decision |
| A pasted posting has no matches | Its company is missing, no source is usable, or no public job agrees | Expected. The page says so. Matches are looked up on read, so they appear once a matching job is fetched |
| Matches disappeared for everyone | The source stopped being usable (switched off, review expired) | Renew the review or switch the source back on. See the [source health runbook](source-health.md) |

## Undoing or confirming a link (administrator)
`POST /api/v1/admin/job-links/{id}/undo` or `/confirm`. The groups are worked out again at once: undoing splits a group only where that link was the only join. An undone link is never made again by code. Undo is itself reversible with `confirm`.

## Mitigation
Undoing a wrong link is immediate and loses nothing. If a rule is producing many wrong links, undo them and fix the rule before the next poll.

## Recovery
Groups are derived. If `group_id` values ever look wrong, `regroup` rebuilds them from the active links. Never edit `group_id` by hand.

## Prevention
Add a unit test case for every wrong link and every missed duplicate you find. Review `suggested` links regularly. Keep company aliases in the registry.
