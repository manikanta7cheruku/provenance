"""Evaluation: metrics, thresholds, comparison with a baseline, and the learned-ranker decision.

Pure rules, no files and no database. The harness in pv_eval produces case results and calls these
functions to turn them into numbers, to decide whether a number is acceptable, and to say what
changed since the last run. Everything here is deterministic, so the same results always give the
same report.

Three ideas run through it:
  - A metric has a direction (higher is better, or lower is better) and a floor or ceiling that a
    release must not cross. A metric with no baseline yet is reported, not judged.
  - A regression is a metric that crossed its limit OR got worse than its baseline by more than a
    tolerance. The deterministic suite has a tolerance of zero: it has no noise, so any change is a
    change someone must look at and accept on purpose.
  - A learned model may replace the deterministic ranker only on a measured win over enough labels
    from enough people (ADR-0054). Until then the answer is no, and it says what is missing.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

HIGHER = "higher"
LOWER = "lower"
FALSE_NEGATIVE_WEIGHT = 3  # telling someone they cannot take a job they could costs more

# What a learned ranker must clear before it may reorder anything (ADR-0054).
RANKER_MIN_LABELS = 1000
RANKER_MIN_PEOPLE = 30
RANKER_MIN_GAIN = 0.05  # pairwise agreement, on labels it was not trained on


@dataclass(frozen=True)
class CaseResult:
    """One case in one suite: what was expected, what happened, and whether that is a pass."""

    suite: str
    case_id: str
    passed: bool
    expected: str
    got: str
    note: str = ""


@dataclass(frozen=True)
class Metric:
    name: str
    value: float
    direction: str  # HIGHER or LOWER
    limit: float  # the floor (HIGHER) or ceiling (LOWER) a release must not cross
    cases: int  # how many cases the value was worked out from
    suite: str = ""
    label: str = ""


@dataclass(frozen=True)
class Change:
    name: str
    label: str
    value: float
    baseline: float | None
    limit: float
    direction: str
    status: str  # ok, regressed, below_limit or new
    delta: float | None


def rate(part: int, whole: int) -> float:
    """part / whole, and 1.0 for an empty whole: no cases means nothing went wrong."""
    return part / whole if whole else 1.0


def precision_recall(true_positive: int, proposed: int, expected: int) -> tuple[float, float]:
    return rate(true_positive, proposed), rate(true_positive, expected)


def weighted_error(
    false_negatives: int, false_positives: int, total: int, weight: int = FALSE_NEGATIVE_WEIGHT
) -> float:
    """Errors out of the total, with a false negative counted `weight` times. 0 is perfect."""
    return (weight * false_negatives + false_positives) / total if total else 0.0


def pairwise_agreement(pairs: Sequence[tuple[float, float]]) -> float:
    """Of pairs (score of the preferred item, score of the other), how many put the preferred first.
    A tie counts as half, so a scorer that cannot tell the two apart gets no credit."""
    if not pairs:
        return 1.0
    credit = sum(1.0 if a > b else 0.5 if a == b else 0.0 for a, b in pairs)
    return credit / len(pairs)


def round_metric(value: float) -> float:
    return round(value, 4)


# ------------------------------------------------------------------ comparing with a baseline


def judge(metric: Metric, baseline: float | None, tolerance: float = 0.0) -> Change:
    """Is this metric acceptable, and how does it compare with its baseline?"""
    value = round_metric(metric.value)
    if metric.direction == HIGHER:
        below = value < metric.limit
        worse = baseline is not None and value < baseline - tolerance
        delta = None if baseline is None else round_metric(value - baseline)
    else:
        below = value > metric.limit
        worse = baseline is not None and value > baseline + tolerance
        delta = None if baseline is None else round_metric(value - baseline)
    if below:
        status = "below_limit"
    elif worse:
        status = "regressed"
    elif baseline is None:
        status = "new"
    else:
        status = "ok"
    return Change(
        name=metric.name,
        label=metric.label or metric.name,
        value=value,
        baseline=baseline,
        limit=metric.limit,
        direction=metric.direction,
        status=status,
        delta=delta,
    )


def compare(
    metrics: Sequence[Metric], baseline: Mapping[str, float], tolerance: float = 0.0
) -> tuple[Change, ...]:
    return tuple(judge(m, baseline.get(m.name), tolerance) for m in metrics)


def passed(changes: Sequence[Change]) -> bool:
    """A run passes when nothing is below its limit or worse than its baseline."""
    return all(c.status in ("ok", "new") for c in changes)


def failing(changes: Sequence[Change]) -> tuple[Change, ...]:
    return tuple(c for c in changes if c.status not in ("ok", "new"))


# ------------------------------------------------------------------ the learned ranker


@dataclass(frozen=True)
class RankerDecision:
    adopt: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def ranker_decision(
    labels: int, people: int, baseline_agreement: float, candidate_agreement: float | None
) -> RankerDecision:
    """May a learned ranker reorder results? Only on a measured win, over enough labels from
    enough people, on labels it was not trained on. Otherwise the answer is no, with the reasons."""
    why: list[str] = []
    if labels < RANKER_MIN_LABELS:
        why.append(
            f"{labels} labels, and {RANKER_MIN_LABELS} are needed before a comparison means anything."
        )
    if people < RANKER_MIN_PEOPLE:
        why.append(
            f"Labels from {people} people, and {RANKER_MIN_PEOPLE} are needed so one person's taste is not learned."
        )
    if candidate_agreement is None:
        why.append("No candidate has been evaluated on held-out labels yet.")
    elif candidate_agreement - baseline_agreement < RANKER_MIN_GAIN:
        gain = candidate_agreement - baseline_agreement
        why.append(
            f"The candidate agrees {gain:+.1%} with people against the rules, and a gain of at least "
            f"{RANKER_MIN_GAIN:.0%} is needed."
        )
    return RankerDecision(adopt=not why, reasons=tuple(why))
