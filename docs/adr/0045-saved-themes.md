# ADR-0045: Saved themes

Status: Accepted (checkpoint 2.13).

## Context
The owner asked to save a set of fonts and colors and reuse it. Today a person who makes a good look has to set a font pair and four colors again on every resume. The colors and fonts are already checked when a resume is saved (ADR-0035, ADR-0036): hex codes only, text readable on white, a tint the text stays readable on, fonts from a fixed list. A saved look must not become a way around those rules or a way to carry anything else from one resume to another.

## Decision

**A theme is the look and nothing else.** A name, a font pair and four colors (the accent, the text, the grey and a soft tint). It holds no words, no pictures, no margins and no paper size, so applying a theme can never change what a resume says. The browser tests check that the words are identical before and after applying one.

**The same rules as a resume.** A theme is checked by the function that checks a resume's style (`clean_style`), exposed for this one purpose. The font pair must be one we offer, every color a six digit hex code, the text colors readable on white and the tint readable under the text. The database repeats what it can (lowercase hex by a `CHECK`, name length). So a saved theme can never put into a resume anything the resume could not hold itself, and a resume checks its style again when it is saved, whatever theme it came from.

**A per-person library with Row Level Security** (`resume_themes`, migration 0017): tenant data, enabled and forced, goes with the person. A name is unique per person ignoring case (a unique index on `lower(name)`), so two people may both have "Blue". At most 20 themes per person, so the list stays a list. Someone else's theme is "not found", never "forbidden". Create, replace and delete are audited and rate limited, with no theme contents in the audit record.

**Save, use, update, rename, delete.** Save this look takes the current fonts and colors of the resume under a name. Use puts a saved look on the resume (the browser sets the style, which is saved like any other change and can be undone). Update replaces a theme with the current look of the resume. Rename and delete are separate. Deleting a theme leaves resumes that used it unchanged, because applying copies the values and keeps no link. Delete asks first.

**One write route.** `PUT` replaces the whole theme (name and look) so there is one place that validates, and a rename is a replace with the same look.

## Alternatives considered
- **A theme that resumes point to.** Rejected: changing a theme would change every resume that used it, silently, and a deleted theme would leave resumes pointing at nothing. Copying values is simpler and predictable.
- **A theme that also holds margins, paper and layout.** Rejected: that is a template (ADR-0035). A theme is the part that changes the feel and nothing that moves things around.
- **Keep themes in the browser.** Rejected: they would not follow the person to another device.
- **Store themes inside the resume documents.** Rejected: they must be shared across resumes, and a library needs its own limits and names.
- **A separate rule set for theme colors.** Rejected: two rule sets drift. One function decides.

## Consequences
- A theme from before a rule changed could fail the newer rule. It would then be refused when applied (the resume's own save check), with the usual message, and can be updated.
- A person who wants one look across several resumes applies it to each. There is no "apply to all".
- The built-in color sets are not saved themes and cannot be edited. A person copies one by applying it and saving the look.
- No sharing between people and no import or export of a theme.

## Evidence
Unit tests (17): a good theme, lowercase colors, names tidy and bounded, every part needed, font pairs, hex codes, readability on white and under the tint, not a theme, extra fields dropped. Integration tests with the real database (12): forced Row Level Security and checks, create and list, replace, rename and delete, same name, case-insensitive uniqueness, two people with one name, a message per bad field, unknown fields refused, the limit, ownership (404 for another person, nothing visible under another person's session), sign-in and CSRF, audit trail. Browser tests (10) with axe in light and dark: empty state, save, apply and saved with the resume, words unchanged, update, rename, delete and cancel, name taken keeps the text, a phone.
