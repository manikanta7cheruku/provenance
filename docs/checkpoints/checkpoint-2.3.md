# Checkpoint 2.3: Template library, links, fonts and color themes

Phase 2, Resume studio and job sources. Branch `phase-2/checkpoint-2.3-templates`. Decision: [ADR-0035](../adr/0035-template-library-links-and-themes.md). Builds on the free canvas of [checkpoint 2.2](checkpoint-2.2.md).

After testing 2.2 the owner asked for professional templates and for more freedom: links in text, more fonts, color sets, images and icons, phone editing and saved themes. This checkpoint delivers templates, links, fonts and color sets. Images and icons, touch editing and saved themes are now checkpoints 2.11, 2.12 and 2.13 in the roadmap, because each changes storage, security or the editing model.

## 1. Build

**Template engine.** `canvas/templates/`: `specs.ts` (24 templates as data), `layout.ts` (`layoutTemplate`, one function for all of them), `content.ts` (the words of a resume, read from a guided resume or back from a canvas), `palettes.ts` (12 color sets), `TemplateGallery.tsx` and `PagePreview.tsx` (the gallery).

**The library.** 13 one-column designs (Ledger, Modern Plain, Compact Page, Executive, Graduate, Technical, Editorial, Centered Classic, Bold Name, Right Aligned, Quiet Minimal, Heavy Rule, Classic Serif) and 11 with more structure (Banner, Sidebar Left, Sidebar Right, Dark Sidebar, Split Header, Soft Panel, Boxed Titles, Timeline, Ribbon, Wide Sidebar, Accent Edge). Headers can be left, centered, right, split, a color band or a panel. Section titles can be ruled, plain, a short line, a side bar, a tinted bar or overlined. Dates can sit on the right, below or on the left.

**Gallery.** Each card is the template laid out in the browser with real text measurement, with its fonts and colors, plus a measured label: **ATS-safe** (the layout check passes) or **Designed layout**. A filter shows all, ATS-safe or Designed. On the start screen the previews use sample words, and your own words are filled in when you start.

**Change template.** For a canvas resume made from a template: pick another one in the gallery (shown with your own words), choose whether to keep your fonts and colors, apply. Every word, date, contact and link is kept. Moves made by hand are not, and boxes added by hand are counted and named before you confirm. The old layout is saved in Earlier versions. A resume laid out before 2.3 has no labels, and the dialog says why it cannot be swapped.

**Links.** A Link button in the formatting bar (on the page and in the side panel). Addresses are checked: https, http, mailto, tel only. Contacts in templates link themselves. In the PDF they are real links.

**Fonts.** Seven new families (Inter, Lato, Source Sans 3, Lora, Merriweather, Playfair Display, Montserrat) shipped with their licences, giving 12 font pairs in the Fonts list of both editors.

**Color themes.** Four colors per resume (accent, text, grey, tint), 12 themes in the Page and style tab, and custom boxes that refuse unreadable colors. Shapes can be filled with the tint.

**Server.** `link` mark and `clean_href`, `ink`, `muted`, `tint` in the canvas style with contrast checks, a `meta` label on elements (roles name, headline, contacts, title, item, dates, decor), the nine font families in the renderer, `tint` as a color. No migration.

## 2. UX

- A new person picks from a gallery of real previews and gets a finished page, not a blank one.
- Changing mind is safe: words carry over and the old layout is one click away.
- The label says why a layout is risky for tracking systems, and nothing is hidden.
- Everything stays editable on the canvas after choosing.

## 3. Technical acceptance criteria

1. At least 20 templates. All 24 are accepted by the server validator, drawn as HTML, and printed by the real PDF engine on the right number of pages with the shipped fonts and no fallback.
2. One layout function. Every template fits the page and margins and respects the 3-page and 150-element limits. Long content moves to further pages.
3. The one-column templates pass the layout check, and the sidebar, band, panel and tinted-bar templates do not. The list is pinned by a test.
4. The words survive: laying out, reading back and laying out again through five templates changes nothing the person wrote (every template, with names, headline, contacts with links, sections, items, dates).
5. Only https, http, mailto and tel links are kept. Whitespace, control characters, quotes, angle brackets, missing hosts and over-long addresses are refused, on the server and in the browser. A link is an anchor with `rel="noopener noreferrer"` in HTML and a link annotation in the PDF.
6. Every font file and licence exists. Each of the 12 pairs is accepted and the rest refused. The browser and the server write identical CSS for every element, including the new palette and font cases (golden file).
7. Text and grey colors must be readable on white and a tint must leave them readable. All 12 palettes pass a test.
8. Old documents (no tint, no labels) still validate with defaults.
9. Ruff, mypy, import-linter, unit, PDF, integration and web tests pass.

## 4. Accessibility acceptance criteria

Axe finds no WCAG 2.2 A or AA violation on the gallery, the Change template dialog, the Page and style tab with themes, and the link form, in light and dark. The gallery is a group of radio buttons with names that include what is shown (template, tags, the ATS label). The ATS label is text, not color alone. Theme buttons show their names and state with `aria-pressed`.

## 5. Test

| Where | What |
|---|---|
| `tests/unit/test_resume_links_fonts_palettes.py` | addresses, links in guided and canvas documents, fonts and licences, palettes, labels |
| `tests/unit/test_template_docs.py` | every template document is accepted and drawn |
| `tests/unit/test_resume_canvas.py` | CSS golden file with the new palette and font cases |
| `tests/pdf/test_template_pdfs.py` | the real engine for all 24 templates and a real link in the file |
| `tests/pdf/test_resume_pdf.py` | the 36 font files and 9 licences |
| `src/features/studio/canvas/templates/templates.test.ts` | library, palettes, layout limits, ATS list, round trip, sidebars, links, pages, fixture |
| `e2e/templates.spec.ts` | gallery, start from a template, change template, themes, fonts, links, old resume, axe in both themes |

## 6. Commit

```
feat(studio): add 24 templates, links, nine font families and color themes
```

## 7. Interview defense

- Why templates are data plus one function, and what that bought (one test suite for 24 designs).
- How Change template keeps words: labels on elements, reading them back, laying out again, saving the old layout.
- Why ATS-safe is measured by running the same check on the result, not declared per template.
- Why links accept four schemes, why the check is in two places, and what `rel="noopener noreferrer"` does.
- Why fonts are shipped and not fetched, and how the PDF test proves there is no fallback.
- Why text colors must be readable and how the tint check works (contrast in both directions).

## 8. Verified and not verified

Verified: unit 631, PDF 60 (all templates in the real engine, with real links), studio and canvas integration (36), web 235 unit tests, Playwright 137 with axe in both themes, build and the web checks, the gallery and two full templates (Banner, Sidebar Left) looked at in the browser with real fonts; the other templates were laid out and printed but not looked at one by one.

Not verified: a person using the gallery and templates, dense multi-page resumes in every template with real fonts (pages were checked with stand-in measurements and the real PDF engine, not every template with 3 full pages), screen reader use by a person, how every external tracking system reads each template (the label is the product's own check, not a test against any vendor), images, icons, touch editing and saved themes (2.11 to 2.13), more than the Latin alphabet in the new fonts.

## 9. Run it yourself

```
.\scripts\pv.ps1 up
```
If you already have a resume, delete it first or use Change template. Open Resume studio, scroll the gallery, pick a template and start. Then try Change template, the Color theme buttons in Page and style, the Fonts list, and double-click a text box and press Link.
