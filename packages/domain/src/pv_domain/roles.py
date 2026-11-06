"""Does a job title match a role the person said they want?

Plain code, no model. Used to put matching jobs first. It is a signal for ordering, never a
reason to hide or block a job: a title that does not match may still be a good job, so the answer
only moves it down the list.

A role matches when every meaningful word of it is in the title, after treating the common ways of
saying the same thing (engineer, developer, programmer; SDE, software engineer) as one word.
"""

import re
import unicodedata

_WORD = re.compile(r"[a-z0-9+#]+")
_FILLER = frozenset(
    {"a", "an", "and", "the", "of", "for", "in", "at", "to", "ii", "iii", "iv", "i"}
)
_SENIORITY = frozenset(
    {"junior", "jr", "senior", "sr", "lead", "principal", "staff", "associate", "intern", "trainee"}
)
_SAME = {
    "developer": "engineer",
    "programmer": "engineer",
    "sde": "software engineer",
    "swe": "software engineer",
    "frontend": "front end",
    "backend": "back end",
    "fullstack": "full stack",
    "ml": "machine learning",
    "ui": "design",
    "ux": "design",
    "designer": "design",
    "analytics": "analyst",
    "scientist": "science",
}


def _words(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKC", text).casefold().replace("-", "")
    out: set[str] = set()
    for word in _WORD.findall(folded):
        if word in _FILLER:
            continue
        out.update(_SAME.get(word, word).split())
    return out


def role_matches(title: str, target_roles: tuple[str, ...] | list[str]) -> bool | None:
    """True when the title fits one of the wanted roles, False when it fits none, None when the
    person named no role (nothing to compare)."""
    roles = [r for r in target_roles if r.strip()]
    if not roles:
        return None
    title_words = _words(title)
    for role in roles:
        wanted = _words(role) - _SENIORITY
        if wanted and wanted <= title_words:
            return True
    return False
