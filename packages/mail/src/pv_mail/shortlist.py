"""The shortlist email. Plain text on purpose: no tracking pixels, no images, nothing to render wrongly.

It says why the person got it, lists a few jobs each with its reason and a link into the product, and
says how to change or stop it. It never links to an employer's site, and it is clear that the product
does not apply for anyone.
"""

from dataclasses import dataclass

from pv_mail.templates import RenderedEmail


@dataclass(frozen=True)
class ShortlistItem:
    title: str
    company: str
    place: str
    reason: str
    url: str


def render_shortlist(
    items: list[ShortlistItem], *, schedule_text: str, settings_url: str
) -> RenderedEmail:
    count = len(items)
    subject = f"Your Provenance shortlist: {count} {'job' if count == 1 else 'jobs'} worth a look"
    lines = [
        "These are the jobs on your list that look worth your time right now.",
        "Each one passed your eligibility checks and has a fit of Strong or Good against your own evidence.",
        "",
    ]
    for number, item in enumerate(items, start=1):
        head = item.title or "Untitled posting"
        where = " | ".join(p for p in (item.company, item.place) if p)
        lines.append(f"{number}. {head}")
        if where:
            lines.append(f"   {where}")
        lines.append(f"   {item.reason}")
        lines.append(f"   {item.url}")
        lines.append("")
    lines += [
        "Provenance does not apply for you. Open a job to read it, save it, or record that you applied.",
        "",
        f"You get this email: {schedule_text}.",
        f"Change the schedule or stop it here: {settings_url}",
    ]
    return RenderedEmail(subject=subject, body="\n".join(lines))
