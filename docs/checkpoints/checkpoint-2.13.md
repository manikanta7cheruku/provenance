# Checkpoint 2.13: Saved themes

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.13-saved-themes`, built on 2.12. Decision: [ADR-0045](../adr/0045-saved-themes.md). Builds on the colors and fonts of [2.3](checkpoint-2.3.md).

## What this checkpoint is for
The owner asked to save a set of fonts and colors and reuse it. This is the last checkpoint of Phase 2.

## 1. Build
- Page and style, My themes: name the current fonts and colors and save them. Use puts a saved look on the resume. Update replaces a theme with the current look. Rename. Delete (asks first).
- A theme is a font pair and four colors. No words, pictures, margins or paper.
- Up to 20 themes per person, names unique per person ignoring case.
- Data: migration 0017 `resume_themes` (Row Level Security, forced). Routes: `GET|POST /studio/themes`, `PUT|DELETE /studio/themes/{id}`.
- Rules: the same ones a resume's style follows, through `clean_style`.

## 2. UX
- Every refusal says what to change: a name is needed, a name is taken, a color is too light, the limit is reached.
- Using a theme is one click and can be undone like any other change. The theme in use is marked.
- Deleting says that resumes keep their colors.
- Works with a finger: the panel fits at 390 pixels.

## 3. Technical acceptance criteria
1. A theme is accepted only if its font pair is offered, its colors are hex codes, its text colors are readable on white and its tint is readable under the text.
2. A name is one tidy line up to 40 characters, unique per person ignoring case. Two people may use the same name.
3. A person has at most 20 themes.
4. Another person's theme is "not found" for replace and delete, is not listed, and is not visible under another session (Row Level Security).
5. Applying a theme changes the style and none of the words.
6. Create, replace and delete are audited and rate limited. Unknown fields are refused.
7. Ruff, mypy, import-linter, unit, integration and web tests pass.

## 4. Accessibility acceptance criteria
Axe finds no WCAG 2.2 A or AA violation on the panel with a theme listed, with a delete question and with the rename form, in light and dark. Each button names the theme it acts on. The status of a save is announced.

## 5. Test
| Where | What |
|---|---|
| `tests/unit/test_theme_rules.py` | the rules a theme must follow |
| `tests/integration/test_resume_themes.py` | the database and routes, ownership, limits, audit |
| `e2e/themes.spec.ts` | the panel in the browser, axe in both themes, a phone |

## 6. Not verified
Themes against a real long-term library (many themes, many devices), a screen reader pass, and a new rule being added after themes were saved (see the ADR).

## Phase 2 is complete in code
All thirteen checkpoints of Phase 2 are built. What remains for the phase is the owner's carryover (real AI key, real devices, real PDFs in real readers), listed in the [carryover register](../carryover/register.md).
