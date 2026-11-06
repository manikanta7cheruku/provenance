"""The workbench: what a person has decided about each job, and how the list is searched and sorted.

Two parts, both pure:

1. The decision state machine. A job a person has added is New until they act. They can Save it,
   Dismiss it, Approve it for preparation, or record that they Applied. Save, Dismiss and Applied can
   be taken back. Every move is checked here, never in the browser, and each one has a reason when it
   is refused. There is deliberately no "submitted" state: the product cannot apply for anyone.
   `applied` is the person's own record that they applied on the employer's site.

   This is the person's half of the match lifecycle (ADR-0014). The reading and scoring states stay
   with the posting (ui_state, the evidence check). The states after approval (materials made,
   ready to apply) arrive with preparation in Phase 3.

2. The list rules: views (Active, Saved, Applications, Dismissed, Archived, All), text search, filters,
   sorting and facet counts. The server applies them so the rules live in one place and are tested.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

MAX_NOTE_CHARS = 2000
MAX_BULK = 100
MAX_VIEWS = 20
MAX_VIEW_NAME = 60
MAX_QUERY_CHARS = 200


class DecisionState(StrEnum):
    NEW = "new"
    SAVED = "saved"
    DISMISSED = "dismissed"
    APPROVED_FOR_PREP = "approved_for_prep"
    APPLIED = "applied"
    ARCHIVED = "archived"


class Action(StrEnum):
    SAVE = "save"
    UNSAVE = "unsave"
    DISMISS = "dismiss"
    UNDO_DISMISS = "undo_dismiss"
    APPROVE = "approve"
    MARK_APPLIED = "mark_applied"
    UNDO_APPLIED = "undo_applied"
    ARCHIVE = "archive"


STATE_LABELS = {
    DecisionState.NEW: "New",
    DecisionState.SAVED: "Saved",
    DecisionState.DISMISSED: "Dismissed",
    DecisionState.APPROVED_FOR_PREP: "Approved for preparation",
    DecisionState.APPLIED: "Applied",
    DecisionState.ARCHIVED: "Archived",
}

ACTION_LABELS = {
    Action.SAVE: "Save",
    Action.UNSAVE: "Unsave",
    Action.DISMISS: "Dismiss",
    Action.UNDO_DISMISS: "Undo dismiss",
    Action.APPROVE: "Approve for preparation",
    Action.MARK_APPLIED: "Mark applied",
    Action.UNDO_APPLIED: "Undo applied",
    Action.ARCHIVE: "Archive",
}

# The action that takes each reversible action back. Approve and archive are not taken back.
REVERSE = {
    Action.SAVE: Action.UNSAVE,
    Action.DISMISS: Action.UNDO_DISMISS,
    Action.MARK_APPLIED: Action.UNDO_APPLIED,
}

_FROM: dict[Action, frozenset[DecisionState]] = {
    Action.SAVE: frozenset({DecisionState.NEW}),
    Action.UNSAVE: frozenset({DecisionState.SAVED}),
    Action.DISMISS: frozenset(
        {DecisionState.NEW, DecisionState.SAVED, DecisionState.APPROVED_FOR_PREP}
    ),
    Action.UNDO_DISMISS: frozenset({DecisionState.DISMISSED}),
    Action.APPROVE: frozenset({DecisionState.NEW, DecisionState.SAVED}),
    Action.MARK_APPLIED: frozenset(
        {DecisionState.NEW, DecisionState.SAVED, DecisionState.APPROVED_FOR_PREP}
    ),
    Action.UNDO_APPLIED: frozenset({DecisionState.APPLIED}),
    Action.ARCHIVE: frozenset({DecisionState.APPLIED, DecisionState.DISMISSED}),
}

_TO = {
    Action.SAVE: DecisionState.SAVED,
    Action.UNSAVE: DecisionState.NEW,
    Action.DISMISS: DecisionState.DISMISSED,
    Action.UNDO_DISMISS: DecisionState.NEW,
    Action.APPROVE: DecisionState.APPROVED_FOR_PREP,
    Action.MARK_APPLIED: DecisionState.APPLIED,
    Action.ARCHIVE: DecisionState.ARCHIVED,
}

# What an undone "applied" falls back to: where the job was before. Anything else falls back to New.
_UNDO_APPLIED_TARGETS = frozenset(
    {DecisionState.NEW, DecisionState.SAVED, DecisionState.APPROVED_FOR_PREP}
)


class TransitionError(Exception):
    """A move that is not allowed. code is short and stable, message is for the person."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def transition(
    state: DecisionState,
    action: Action,
    *,
    eligibility: str | None = None,
    previous: DecisionState | None = None,
) -> DecisionState:
    """The state after an action, or TransitionError.

    eligibility is the job's current eligibility state. A job a hard rule rules out cannot be
    approved for preparation. previous is where the job was before it was marked applied (the
    last move into Applied), used by Undo applied."""
    if state not in _FROM[action]:
        raise TransitionError(
            "not_allowed",
            f"{ACTION_LABELS[action]} is not available for a job that is {STATE_LABELS[state].lower()}.",
        )
    if action is Action.APPROVE and eligibility == "not_eligible":
        raise TransitionError(
            "not_eligible",
            "A hard requirement stands in the way of this job, so it cannot be approved for "
            "preparation. You can still save it or dismiss it.",
        )
    if action is Action.UNDO_APPLIED:
        return previous if previous in _UNDO_APPLIED_TARGETS and previous else DecisionState.NEW
    return _TO[action]


def available_actions(state: DecisionState, eligibility: str | None = None) -> list[Action]:
    """The actions the interface offers now, in the order it shows them."""
    order = (
        Action.SAVE,
        Action.UNSAVE,
        Action.APPROVE,
        Action.MARK_APPLIED,
        Action.DISMISS,
        Action.UNDO_DISMISS,
        Action.UNDO_APPLIED,
        Action.ARCHIVE,
    )
    out: list[Action] = []
    for action in order:
        try:
            transition(state, action, eligibility=eligibility, previous=None)
        except TransitionError:
            continue
        out.append(action)
    return out


# ---- the list

VIEWS = ("active", "saved", "applications", "dismissed", "archived", "all")
VIEW_LABELS = {
    "active": "Active",
    "saved": "Saved",
    "applications": "Applications",
    "dismissed": "Dismissed",
    "archived": "Archived",
    "all": "All",
}
_VIEW_STATES: dict[str, frozenset[str]] = {
    "active": frozenset(
        {DecisionState.NEW.value, DecisionState.SAVED.value, DecisionState.APPROVED_FOR_PREP.value}
    ),
    "saved": frozenset({DecisionState.SAVED.value, DecisionState.APPROVED_FOR_PREP.value}),
    "applications": frozenset({DecisionState.APPLIED.value}),
    "dismissed": frozenset({DecisionState.DISMISSED.value}),
    "archived": frozenset({DecisionState.ARCHIVED.value}),
    "all": frozenset(s.value for s in DecisionState),
}

SORTS = ("best", "added", "title", "company", "fit", "eligibility", "applied")
_ELIGIBILITY_RANK = {"eligible": 0, "uncertain": 1, "requires_user_input": 2, "not_eligible": 3}
_BAND_RANK = {"strong": 0, "good": 1, "review": 2, "not_recommended": 3, "not_eligible": 4}
WORK_MODES = ("remote", "hybrid", "onsite")
ELIGIBILITY_STATES = tuple(_ELIGIBILITY_RANK)
BANDS = tuple(_BAND_RANK)


@dataclass(frozen=True)
class WorkRow:
    """One job in the list, with everything the list can filter or sort by."""

    id: str
    title: str
    company: str
    source_name: str
    acquisition_method: str
    work_mode: str | None
    location: str
    employment_type: str | None
    seniority: str | None
    eligibility: str | None  # None while the job is still being read
    band: str | None  # None until the evidence check is complete
    reading: str  # reading, ready or failed
    state: str
    created_at: datetime
    applied_at: datetime | None
    note: str = ""
    # True when the title fits a role the person wants, False when it does not, None when they
    # named no role.
    role_match: bool | None = None


@dataclass(frozen=True)
class WorkQuery:
    view: str = "active"
    text: str = ""
    states: frozenset[str] = frozenset()  # when set, replaces the view's states
    eligibility: frozenset[str] = frozenset()
    bands: frozenset[str] = frozenset()
    work_modes: frozenset[str] = frozenset()
    employment_types: frozenset[str] = frozenset()
    seniorities: frozenset[str] = frozenset()
    sources: frozenset[str] = frozenset()
    company: str = ""
    location: str = ""
    sort: str = "best"
    descending: bool | None = None  # None means the natural direction of the sort


def clean_query(raw: dict[str, object]) -> WorkQuery:
    """A query from untrusted input (a request or a stored view). Unknown values are dropped,
    text is cut to length, nothing raises."""

    def text(key: str) -> str:
        value = raw.get(key)
        return " ".join(value.split())[:MAX_QUERY_CHARS] if isinstance(value, str) else ""

    def many(key: str, allowed: tuple[str, ...] | None = None) -> frozenset[str]:
        value = raw.get(key)
        items = value if isinstance(value, (list, tuple, set, frozenset)) else []
        picked = {i.strip()[:80] for i in items if isinstance(i, str) and i.strip()}
        if allowed is not None:
            picked &= set(allowed)
        return frozenset(list(sorted(picked))[:20])

    view = raw.get("view")
    sort = raw.get("sort")
    direction = raw.get("descending")
    return WorkQuery(
        view=view if isinstance(view, str) and view in VIEWS else "active",
        text=text("text"),
        states=many("states", tuple(s.value for s in DecisionState)),
        eligibility=many("eligibility", ELIGIBILITY_STATES),
        bands=many("bands", BANDS),
        work_modes=many("work_modes", WORK_MODES),
        employment_types=many("employment_types"),
        seniorities=many("seniorities"),
        sources=many("sources"),
        company=text("company"),
        location=text("location"),
        sort=sort if isinstance(sort, str) and sort in SORTS else "best",
        descending=direction if isinstance(direction, bool) else None,
    )


def query_to_dict(query: WorkQuery) -> dict[str, object]:
    """The stored form of a query (a saved view). Round-trips through clean_query."""
    out: dict[str, object] = {"view": query.view, "sort": query.sort}
    if query.descending is not None:
        out["descending"] = query.descending
    if query.text:
        out["text"] = query.text
    if query.company:
        out["company"] = query.company
    if query.location:
        out["location"] = query.location
    for key, values in (
        ("states", query.states),
        ("eligibility", query.eligibility),
        ("bands", query.bands),
        ("work_modes", query.work_modes),
        ("employment_types", query.employment_types),
        ("seniorities", query.seniorities),
        ("sources", query.sources),
    ):
        if values:
            out[key] = sorted(values)
    return out


def _haystack(row: WorkRow) -> str:
    return " ".join([row.title, row.company, row.location, row.source_name, row.note]).casefold()


def in_view(row: WorkRow, query: WorkQuery) -> bool:
    states = query.states or _VIEW_STATES[query.view]
    return row.state in states


def matches(row: WorkRow, query: WorkQuery) -> bool:
    """Whether a row passes every part of the query. Within one filter any value may match (OR),
    across filters all must (AND). Text must contain every word. A job with no value for a filtered
    field does not match that filter, rather than being treated as a match."""
    if not in_view(row, query):
        return False
    if query.text:
        haystack = _haystack(row)
        if not all(word in haystack for word in query.text.casefold().split()):
            return False
    if query.eligibility and row.eligibility not in query.eligibility:
        return False
    if query.bands and row.band not in query.bands:
        return False
    if query.work_modes and row.work_mode not in query.work_modes:
        return False
    if query.employment_types and row.employment_type not in query.employment_types:
        return False
    if query.seniorities and row.seniority not in query.seniorities:
        return False
    if query.sources and row.source_name not in query.sources:
        return False
    if query.company and query.company.casefold() not in row.company.casefold():
        return False
    return not (query.location and query.location.casefold() not in row.location.casefold())


def _sort_key(row: WorkRow, sort: str) -> tuple[object, ...]:
    if sort == "title":
        return (row.title.casefold(),)
    if sort == "company":
        return (row.company == "", row.company.casefold())
    if sort == "best":
        # Jobs you can take first, then jobs that fit a wanted role, then the stronger evidence, then
        # the newest. A hard blocker is last. Nothing here hides a job.
        return (
            _ELIGIBILITY_RANK.get(row.eligibility or "", 1) == 3,
            {True: 0, None: 1, False: 2}[row.role_match],
            _BAND_RANK.get(row.band or "", 2),
            -row.created_at.timestamp(),
        )
    if sort == "fit":
        return (_BAND_RANK.get(row.band or "", 9),)
    if sort == "eligibility":
        return (_ELIGIBILITY_RANK.get(row.eligibility or "", 9),)
    if sort == "applied":
        return (row.applied_at is None, row.applied_at.timestamp() if row.applied_at else 0.0)
    return (row.created_at.timestamp(),)


# Sorts that read best newest or best first. The others read best A to Z.
_NATURAL_DESCENDING = frozenset({"added", "applied"})


def sort_rows(rows: list[WorkRow], query: WorkQuery) -> list[WorkRow]:
    descending = (
        query.descending if query.descending is not None else query.sort in _NATURAL_DESCENDING
    )
    # Missing values (no band yet, no applied date) stay last in either direction.
    present = [r for r in rows if _has_value(r, query.sort)]
    missing = [r for r in rows if not _has_value(r, query.sort)]
    present.sort(key=lambda r: (_sort_key(r, query.sort), r.id), reverse=descending)
    missing.sort(key=lambda r: (-r.created_at.timestamp(), r.id))
    return present + missing


def _has_value(row: WorkRow, sort: str) -> bool:
    if sort == "fit":
        return row.band is not None
    if sort == "eligibility":
        return row.eligibility is not None
    if sort == "applied":
        return row.applied_at is not None
    return True


def select(rows: list[WorkRow], query: WorkQuery) -> list[WorkRow]:
    return sort_rows([r for r in rows if matches(r, query)], query)


@dataclass
class Facets:
    """Counts for the filter controls, over the rows in the current view (before the filters, so a
    person can see what each filter would add)."""

    views: dict[str, int] = field(default_factory=dict)
    work_modes: dict[str, int] = field(default_factory=dict)
    eligibility: dict[str, int] = field(default_factory=dict)
    bands: dict[str, int] = field(default_factory=dict)
    employment_types: dict[str, int] = field(default_factory=dict)
    seniorities: dict[str, int] = field(default_factory=dict)
    sources: dict[str, int] = field(default_factory=dict)


def _bump(counts: dict[str, int], key: str | None) -> None:
    if key:
        counts[key] = counts.get(key, 0) + 1


def facets(rows: list[WorkRow], query: WorkQuery) -> Facets:
    out = Facets()
    for name in VIEWS:
        out.views[name] = sum(1 for r in rows if r.state in _VIEW_STATES[name])
    for row in (r for r in rows if in_view(r, query)):
        _bump(out.work_modes, row.work_mode)
        _bump(out.eligibility, row.eligibility)
        _bump(out.bands, row.band)
        _bump(out.employment_types, row.employment_type)
        _bump(out.seniorities, row.seniority)
        _bump(out.sources, row.source_name)
    return out
