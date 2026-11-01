"""One renderer for the resume: the live preview and the PDF both use this HTML and CSS.

Layout lives in a single place, so "the preview differs from the PDF" cannot come from two code paths.
(The two are still drawn by different engines, a browser and the PDF library, so page breaks are
checked by a test on sample resumes and the PDF is the authority.)

Safety: the document model holds no markup. Every string is escaped here, every tag below is written
by this module. The only link is a validated web, mail or phone address, and there are no images or scripts. Reading order is the order of the HTML,
with no positioning tricks, so the PDF text comes out in the order a person reads it.
"""

from html import escape
from typing import Any

# CSS family name -> the file prefix of the shipped fonts. Each family has four files: 400 and 600,
# upright and italic. (Lato ships its bold as the 600 file.)
FAMILIES = {
    "PV Plex": "ibm-plex-sans",
    "PV Serif": "newsreader",
    "PV Inter": "inter",
    "PV Lato": "lato",
    "PV Source": "source-sans-3",
    "PV Montserrat": "montserrat",
    "PV Lora": "lora",
    "PV Merriweather": "merriweather",
    "PV Playfair": "playfair-display",
}
FONT_FILES = {
    (family, weight, style): f"{prefix}-latin-{weight}-{style}.woff"
    for family, prefix in FAMILIES.items()
    for weight in (400, 600)
    for style in ("normal", "italic")
}

_SERIF = "Georgia, serif"
_SANS = "Arial, sans-serif"
_STACKS = {
    "PV Plex": _SANS,
    "PV Serif": _SERIF,
    "PV Inter": _SANS,
    "PV Lato": _SANS,
    "PV Source": _SANS,
    "PV Montserrat": _SANS,
    "PV Lora": _SERIF,
    "PV Merriweather": _SERIF,
    "PV Playfair": _SERIF,
}


def _stack(family: str) -> str:
    return f'"{family}", {_STACKS[family]}'


# key -> (heading family, body family)
_PAIR_FAMILIES = {
    "plex-newsreader": ("PV Serif", "PV Plex"),
    "plex": ("PV Plex", "PV Plex"),
    "newsreader": ("PV Serif", "PV Serif"),
    "inter": ("PV Inter", "PV Inter"),
    "inter-lora": ("PV Lora", "PV Inter"),
    "lato": ("PV Lato", "PV Lato"),
    "montserrat-lato": ("PV Montserrat", "PV Lato"),
    "source": ("PV Source", "PV Source"),
    "source-merriweather": ("PV Merriweather", "PV Source"),
    "playfair-source": ("PV Playfair", "PV Source"),
    "lora": ("PV Lora", "PV Lora"),
    "merriweather": ("PV Merriweather", "PV Merriweather"),
}
# (heading font stack, body font stack)
FONT_PAIRS = {key: (_stack(h), _stack(b)) for key, (h, b) in _PAIR_FAMILIES.items()}
BASE_PT = {"small": 9.5, "medium": 10.5, "large": 11.5}
BLOCK_GAP_MM = {"tight": 1.8, "normal": 3.0, "relaxed": 4.6}
SECTION_GAP_MM = {"tight": 3.8, "normal": 5.5, "relaxed": 7.5}
MARGIN_MM = {"narrow": 12, "normal": 16, "wide": 22}
PAPER = {"a4": ("210mm", "297mm"), "letter": ("8.5in", "11in")}
RULES = {"none": "none", "thin": "0.6pt solid", "bold": "1.6pt solid", "dotted": "0.9pt dotted"}


def font_faces(font_base: str) -> str:
    faces = []
    for (family, weight, style), file in FONT_FILES.items():
        faces.append(
            f'@font-face{{font-family:"{family}";font-weight:{weight};font-style:{style};'
            f'src:url("{font_base}{file}") format("woff");}}'
        )
    return "\n".join(faces)


def _css(style: dict[str, Any], font_base: str, *, preview: bool) -> str:
    heading_font, body_font = FONT_PAIRS[style["font_pair"]]
    base = BASE_PT[style["size"]]
    block_gap = BLOCK_GAP_MM[style["spacing"]]
    section_gap = SECTION_GAP_MM[style["spacing"]]
    margin = MARGIN_MM[style["margins"]]
    width, height = PAPER[style["paper"]]
    accent = style["accent"]
    template = style["template"]
    rule = RULES[style["divider"]]
    name_pt = round(base * (2.0 if template == "compact" else 2.4), 1)
    title_case = "uppercase" if template != "modern" else "none"
    title_pt = round(base * (0.95 if template != "modern" else 1.2), 2)
    name_rule = "1.6pt solid" if template == "modern" else "none"
    sheet = (
        f"body{{background:#e9e9e6;margin:0;padding:16px 0}}"
        f".resume{{width:{width};min-height:{height};margin:0 auto;padding:{margin}mm;"
        f"box-sizing:border-box;background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.25)}}"
        if preview
        else f"@page{{size:{width} {height};margin:{margin}mm}}body{{margin:0}}"
    )
    return f"""{font_faces(font_base)}
{sheet}
html{{-webkit-text-size-adjust:100%}}
body{{font-family:{body_font};font-size:{base}pt;line-height:1.38;color:#1b1b1b}}
.resume{{--accent:{accent}}}
h1,h2,h3,p,ul,ol{{margin:0;padding:0}}
.name{{font-family:{heading_font};font-size:{name_pt}pt;font-weight:600;line-height:1.1;color:{accent};
  padding-bottom:{"1.4mm" if name_rule != "none" else "0"};
  border-bottom:{name_rule if name_rule != "none" else "0"} {accent}}}
.headline{{margin-top:1mm;font-size:{round(base * 1.1, 2)}pt}}
.contacts{{margin-top:1.4mm;display:flex;flex-wrap:wrap;gap:0 3.2mm;font-size:{round(base * 0.95, 2)}pt}}
.contacts span+span::before{{content:"|";margin-right:3.2mm;color:#6a6a6a}}
.section{{margin-top:{section_gap}mm}}
.section-title{{font-family:{heading_font};font-size:{title_pt}pt;font-weight:600;text-transform:{title_case};
  letter-spacing:{"0.08em" if template != "modern" else "0"};color:{accent};
  padding-bottom:0.8mm;border-bottom:{rule} {accent};margin-bottom:{block_gap}mm;break-after:avoid}}
.block{{margin-top:{block_gap}mm;break-inside:avoid}}
.block:first-of-type{{margin-top:0}}
.row{{display:flex;justify-content:space-between;align-items:baseline;gap:4mm}}
.heading{{font-weight:600;font-size:{round(base * 1.04, 2)}pt}}
.sub{{font-style:italic}}
.meta{{white-space:nowrap;font-size:{round(base * 0.95, 2)}pt;color:#3d3d3d}}
.loc{{font-size:{round(base * 0.95, 2)}pt;color:#3d3d3d}}
.body{{margin-top:0.8mm}}
.body p+p{{margin-top:0.8mm}}
/* Markers are real text in the flow, not list-style markers. A PDF draws list-style markers apart
   from the item, so a reader of the file would meet every bullet after the text. */
.body ul,.body ol{{list-style:none;padding-left:1.5mm;margin-top:0.4mm}}
.body ol{{counter-reset:item}}
.body li{{display:flex;gap:1.8mm;margin-top:0.3mm}}
.body li>p{{flex:1;min-width:0}}
.body ul>li::before{{content:"\\2022";flex:none}}
.body ol>li{{counter-increment:item}}
.body ol>li::before{{content:counter(item) ".";flex:none;min-width:3.2mm;text-align:right}}
strong{{font-weight:600}}
mark{{background:#fff1a8;color:inherit;padding:0 .4mm}}
u{{text-decoration:underline;text-underline-offset:1pt}}
a{{color:inherit;text-decoration:underline;text-underline-offset:1pt}}
"""


def _inline(node: dict[str, Any]) -> str:
    if node.get("type") == "hardBreak":
        return "<br>"
    out: str = escape(node.get("text", ""))
    for mark in node.get("marks", []):
        if mark["type"] == "link":
            href = escape(mark["attrs"]["href"], quote=True)
            out = f'<a href="{href}" rel="noopener noreferrer">{out}</a>'
            continue
        tag = {"bold": "strong", "italic": "em", "underline": "u", "highlight": "mark"}[
            mark["type"]
        ]
        out = f"<{tag}>{out}</{tag}>"
    return out


def _block(node: dict[str, Any]) -> str:
    kind = node["type"]
    if kind == "paragraph":
        return "<p>" + "".join(_inline(c) for c in node.get("content", [])) + "</p>"
    tag = "ul" if kind == "bulletList" else "ol"
    items = "".join(
        "<li>" + "".join(_block(c) for c in item.get("content", [])) + "</li>"
        for item in node.get("content", [])
    )
    return f"<{tag}>{items}</{tag}>"


def render_rich_nodes(body: dict[str, Any] | None) -> str:
    """The inner HTML of a rich body, without a wrapper."""
    return "".join(_block(n) for n in (body or {}).get("content", []))


def render_body(body: dict[str, Any] | None) -> str:
    if not body:
        return ""
    return '<div class="body">' + "".join(_block(n) for n in body.get("content", [])) + "</div>"


def render_html(doc: dict[str, Any], *, font_base: str, preview: bool = False) -> str:
    """The whole page. `font_base` ends with a slash: a web path for the preview, a file path for
    the PDF. The document must already have passed validate_document."""
    if doc.get("version") == 2:
        from pv_domain.resume_canvas import render_canvas_html

        return render_canvas_html(doc, font_base=font_base, preview=preview)
    header = doc["header"]
    style = doc["style"]
    parts = ['<main class="resume">']
    if header["name"]:
        parts.append(f'<h1 class="name">{escape(header["name"])}</h1>')
    if header["headline"]:
        parts.append(f'<p class="headline">{escape(header["headline"])}</p>')
    if header["contacts"]:
        parts.append(
            '<p class="contacts">'
            + "".join(f"<span>{escape(c)}</span>" for c in header["contacts"])
            + "</p>"
        )
    for section in doc["sections"]:
        if not section["blocks"] and not section["title"]:
            continue
        parts.append('<section class="section">')
        if section["title"]:
            parts.append(f'<h2 class="section-title">{escape(section["title"])}</h2>')
        for block in section["blocks"]:
            left = ""
            if block["heading"]:
                left += f'<span class="heading">{escape(block["heading"])}</span>'
            if block["subheading"]:
                left += (
                    ", " if left else ""
                ) + f'<span class="sub">{escape(block["subheading"])}</span>'
            right = f'<span class="meta">{escape(block["dates"])}</span>' if block["dates"] else ""
            row = f'<div class="row"><div>{left}</div>{right}</div>' if (left or right) else ""
            loc = f'<div class="loc">{escape(block["location"])}</div>' if block["location"] else ""
            parts.append(f'<div class="block">{row}{loc}{render_body(block["body"])}</div>')
        parts.append("</section>")
    parts.append("</main>")
    title = f"{header['name']} - Resume" if header["name"] else "Resume"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title>"
        f"<style>{_css(style, font_base, preview=preview)}</style></head><body>"
        + "".join(parts)
        + "</body></html>"
    )
