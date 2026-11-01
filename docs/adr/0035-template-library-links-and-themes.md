# ADR-0035: Template library, links, fonts and color themes

Status: Accepted (checkpoint 2.3).

## Context
The free canvas (ADR-0034) lets a person place anything anywhere, but a blank page is a poor starting point and a person should not have to design a resume from nothing. Checkpoint 2.3 adds a library of 20 or more templates. The owner also asked for links in text, more fonts and color sets. Images, icons, phone editing and saved themes were asked for too and are scheduled as their own checkpoints (2.11 to 2.13), because each changes storage, security or the editing model.

## Decision

**A template is data, and one function lays it out.** A template spec says how the header is set, how section titles look, where dates go, whether there is a sidebar, and which fonts and colors it starts with. `layoutTemplate(content, spec, measure)` turns the person's words and a spec into positioned boxes. `measure` asks the browser how tall a text box is, so the function stays plain and testable. There are 24 specs. They are variations of one engine, not 24 hand-drawn pages, which is why they can all be tested the same way.

**Content is separate from layout.** A template lays out a small model of the resume: name, headline, contacts, sections with items and dates. A guided resume converts into it. A canvas resume made by a template can be read back into it, because every element carries a label (`meta`: role, section, item, kind). That is what makes **Change template** possible without losing words: read the words, lay them out again, keep the old layout as an earlier version. Elements the person added by hand have no label and do not carry over, and the dialog says how many. A resume laid out before 2.3 has no labels, and the dialog says so and does not offer the swap.

**ATS-safe is measured, not declared.** The gallery lays every template out with the person's words, runs the layout check on the result and shows "ATS-safe" only when it passes. One column of plain text passes. Sidebars, color bands, panels and tinted title bars put text on shapes or in columns, so they are shown as "Designed layout". A test pins the list of ATS-safe templates.

**Links are a rich text mark with an address that is checked twice.** The mark `link` carries `href`. The server keeps only `https:`, `http:`, `mailto:` and `tel:` addresses, refuses whitespace, control characters, quotes and angle brackets, and requires a host for web addresses. The browser applies the same rule before it lets the editor create a link. In HTML the link is an anchor with `rel="noopener noreferrer"`, and the PDF engine writes a real link annotation. On the editing page links are drawn but not followed, so a click selects or edits the box. Contacts in templates are linked automatically: an email becomes `mailto:`, a phone number `tel:`, a site `https:`.

**Fonts: nine families, twelve pairs.** Inter, Lato, Source Sans 3, Lora, Merriweather, Playfair Display and Montserrat join IBM Plex Sans and Newsreader. Each ships as four WOFF files (400 and 600, upright and italic) next to its licence, so the PDF engine never reaches the network. A test checks every file and licence exists, and the PDF test checks that none of the 24 templates falls back to a system font.

**Colors: four per resume.** A style now has an accent, a text color (`ink`), a grey (`muted`) and a soft `tint`. Twelve ready-made palettes set all four. The server refuses a text color or grey that is not readable on white (4.5 to 1) and a tint that makes the text on it unreadable. A test checks every shipped palette. `tint` is also a fill color for shapes. Older documents without these fields get the defaults, so no migration was needed.

## Alternatives considered
- **Hand-built pages per template.** More freedom per template, but 24 pieces of layout code with no shared test. Rejected: the engine plus specs gives the same variety and one set of guarantees.
- **Store the template choice and re-render on the server.** Would make changing templates trivial, but the canvas is edited by hand, so the stored positions must be the truth. Rejected for the same reason as in ADR-0034.
- **Allow any URL scheme.** Rejected: `javascript:` and `data:` links are a classic injection. Four schemes cover what a resume needs.
- **Load web fonts from a CDN.** Rejected: the PDF engine may read only shipped files (ADR-0025).

## Consequences
- Templates need a browser to be laid out, because heights come from real text layout. Choosing a template on the start screen therefore happens in the browser, and the result is saved like any other canvas edit.
- The reading order of two-column templates follows the page row by row, so a system that reads in that order will interleave the columns. That is exactly what the "Designed layout" label warns about.
- Saved themes shared across resumes, images, icons and touch editing are not here. They are planned as 2.11 to 2.13.

## Evidence
All 24 templates: accepted by the server validator, drawn as HTML, and printed by the real PDF engine with the shipped fonts, the right page count and working links (tests/unit/test_template_docs.py, tests/pdf/test_template_pdfs.py). Palettes, links, fonts and labels are covered in tests/unit/test_resume_links_fonts_palettes.py and the web tests.
