"""Evidence chunks: what text stands for a profile entry, and how search results are combined.

Pure code. The text is deterministic: the same entry always renders the same words, so its
content hash tells us whether anything changed and the embedding is stale.
"""

import hashlib
import re
from typing import Any

from pv_domain.profile import ENTRY_SPECS

# Fixed by migration 0005 (vector(768)). Changing it needs a migration and re-embedding.
EMBEDDING_DIMENSIONS = 768
MAX_CHUNK_CHARS = 6000
MAX_QUERY_CHARS = 300

SOURCE_PROFILE_ENTRY = "profile_entry"
SOURCE_USER_ANSWER = "user_answer"

# Reciprocal rank fusion constant. 60 is the value from the original paper and common practice:
# it keeps one very high rank from drowning out agreement between the two searches.
RRF_K = 60

_SPACES = re.compile(r"\s+")


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _items(value: Any) -> list[str]:
    return (
        [item for item in value if isinstance(item, str) and item]
        if isinstance(value, list)
        else []
    )


def _span(data: dict[str, Any], *extra: str) -> str:
    start, end = _text(data.get("start_date")), _text(data.get("end_date"))
    period = f"{start} to {end}" if start and end else (f"from {start}" if start else end)
    parts = [part for part in (period, *extra) if part]
    return f" ({', '.join(parts)})" if parts else ""


def render_entry_text(entry_type: str, data: dict[str, Any]) -> str:
    """The sentence or two that stands for an entry in search. Empty if there is nothing to say."""
    spec = ENTRY_SPECS.get(entry_type)
    if spec is None or not _text(data.get(spec.primary_field)):
        return ""
    if entry_type == "education":
        studied = " ".join(
            part for part in (_text(data.get("degree")), _text(data.get("field_of_study"))) if part
        )
        where = _text(data.get("institution"))
        head = (
            f"Education: {studied} at {where}"
            if studied and where
            else f"Education: {studied or where}"
        )
        grade = f" Grade: {_text(data.get('grade'))}." if _text(data.get("grade")) else ""
        return _join(f"{head}{_span(data)}.{grade}", _text(data.get("details")))
    if entry_type in ("work", "internship"):
        label = "Internship" if entry_type == "internship" else "Work"
        role, company = _text(data.get("title")), _text(data.get("company"))
        head = (
            f"{label}: {role} at {company}" if role and company else f"{label}: {role or company}"
        )
        return _join(
            f"{head}{_span(data, _text(data.get('location')))}.",
            "; ".join(_items(data.get("highlights"))),
        )
    if entry_type == "project":
        tech = ", ".join(_items(data.get("technologies")))
        return _join(
            f"Project: {_text(data.get('name'))}{_span(data)}.",
            _text(data.get("description")),
            f"Technologies: {tech}." if tech else "",
            _text(data.get("url")),
        )
    if entry_type == "skill":
        group = _text(data.get("category"))
        return f"Skill: {_text(data.get('name'))}" + (f" ({group})" if group else "")
    if entry_type == "certification":
        issuer, date = _text(data.get("issuer")), _text(data.get("date"))
        tail = f", issued by {issuer}" if issuer else ""
        return f"Certification: {_text(data.get('name'))}{tail}" + (f" ({date})" if date else "")
    if entry_type == "achievement":
        date = _text(data.get("date"))
        return _join(
            f"Achievement: {_text(data.get('title'))}" + (f" ({date})" if date else "") + ".",
            _text(data.get("description")),
        )
    if entry_type == "link":
        return f"Link: {_text(data.get('label'))} {_text(data.get('url'))}".strip()
    return ""


def _join(*parts: str) -> str:
    return " ".join(part for part in parts if part)


def clean_chunk_text(text: str) -> str:
    return _SPACES.sub(" ", text).strip()[:MAX_CHUNK_CHARS]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def clean_query(query: str) -> str:
    return _SPACES.sub(" ", query).strip()[:MAX_QUERY_CHARS]


def reciprocal_rank_fusion[K](rankings: list[list[K]], *, k: int = RRF_K) -> list[tuple[K, float]]:
    """Combine ranked lists. Each item scores the sum of 1 / (k + rank) over the lists it is in.

    Ranks start at 1. Only the order inside each list matters, so scores from different search
    methods (a text rank and a cosine distance) never need to be put on one scale. Ties break by
    the better of the item's ranks, then by first appearance, so the result is deterministic.
    """
    scores: dict[K, float] = {}
    best: dict[K, int] = {}
    first_seen: dict[K, int] = {}
    for ranking in rankings:
        for position, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + position)
            best[item] = min(best.get(item, position), position)
            first_seen.setdefault(item, len(first_seen))
    return sorted(scores.items(), key=lambda pair: (-pair[1], best[pair[0]], first_seen[pair[0]]))
