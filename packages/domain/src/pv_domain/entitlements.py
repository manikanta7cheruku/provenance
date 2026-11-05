"""Plans, entitlements and quotas, as rules.

The chain is Plan, Entitlements, Quota policy, Usage ledger, Rate limiter (ADR-0010). No code path
asks "is this user on the Pro plan". Code asks "may this person do this now?", and the answer comes
from the limits their plan carries and what the ledger says they have used.

  - A **billable unit** is one thing that costs real money to do: a discovery run, a job analysis, an
    analysis of an address the person supplied, a generation of material (tailoring suggestions,
    application drafts, preparation material). Trust features are never metered: reading what the
    evidence shows for a job you already analysed is free on every plan.
  - A **plan** is data (a row, not an `if`): a limit per unit per calendar month and a few structural
    limits (how many resumes, how many PDFs kept per resume). `None` means no limit.
  - The **ledger** has one row per billable event with a key. The same key in the same month is the
    same event, so analysing the same job twice in a month is one unit, and a retried request is never
    charged twice.
  - A **rate limit** (requests per hour, to stop abuse) is a different thing and lives elsewhere
    (ADR-0009). Quotas are about cost, rate limits are about safety.

The numbers below are provisional starting points. The business model says limits are set from
measured cost, and no cost has been measured on a real cohort yet (carryover C-131). They are data, so
changing them changes no code.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

UNIT_DISCOVERY = "discovery_run"
UNIT_ANALYSIS = "job_analysis"
UNIT_URL = "url_analysis"
UNIT_MATERIAL = "material_generation"

UNITS = (UNIT_DISCOVERY, UNIT_ANALYSIS, UNIT_URL, UNIT_MATERIAL)

UNIT_LABELS: dict[str, tuple[str, str]] = {
    UNIT_DISCOVERY: ("Job searches by sentence", "searches"),
    UNIT_ANALYSIS: ("Job evidence checks", "checks"),
    UNIT_URL: ("Jobs read from an address", "jobs"),
    UNIT_MATERIAL: ("Pieces of written material", "pieces"),
}

UNIT_HELP: dict[str, str] = {
    UNIT_DISCOVERY: "Each time you describe a search in a sentence and we turn it into a plan.",
    UNIT_ANALYSIS: "Checking a job against your evidence. Checking the same job again in the same month is free.",
    UNIT_URL: "Reading a job from an address you give us.",
    UNIT_MATERIAL: "Resume tailoring suggestions, application drafts, and interview preparation material.",
}

FREE = "free"
STARTER = "starter"
PRO = "pro"
DEFAULT_PLAN = FREE


@dataclass(frozen=True)
class PlanLimits:
    id: str
    label: str
    # Per calendar month. None means no limit.
    units: dict[str, int | None]
    resumes: int
    exports_per_resume: int


# Starting points, to be replaced by numbers from measured cost. Seeded into the plans table by
# migration 0020 and read from there at run time.
SEED_PLANS: tuple[PlanLimits, ...] = (
    PlanLimits(
        FREE,
        "Free",
        {UNIT_DISCOVERY: 20, UNIT_ANALYSIS: 30, UNIT_URL: 15, UNIT_MATERIAL: 20},
        resumes=1,
        exports_per_resume=5,
    ),
    PlanLimits(
        STARTER,
        "Starter",
        {UNIT_DISCOVERY: 100, UNIT_ANALYSIS: 150, UNIT_URL: 75, UNIT_MATERIAL: 100},
        resumes=3,
        exports_per_resume=20,
    ),
    PlanLimits(
        PRO,
        "Pro",
        {UNIT_DISCOVERY: 500, UNIT_ANALYSIS: 800, UNIT_URL: 300, UNIT_MATERIAL: 500},
        resumes=10,
        exports_per_resume=50,
    ),
)


def limits_from_row(plan_id: str, label: str, data: dict[str, object]) -> PlanLimits:
    """A plan from its stored data. Anything missing or odd is treated as the strictest reading, so a
    bad row can never grant more than was written: a missing unit limit is zero."""
    raw_units = data.get("units")
    units: dict[str, int | None] = {}
    for unit in UNITS:
        # A unit that is not there at all is zero. Only an explicit null means no limit.
        if not isinstance(raw_units, dict) or unit not in raw_units:
            units[unit] = 0
            continue
        value = raw_units[unit]
        units[unit] = (
            None if value is None else value if isinstance(value, int) and value >= 0 else 0
        )
    resumes = data.get("resumes")
    exports = data.get("exports_per_resume")
    return PlanLimits(
        plan_id,
        label,
        units,
        resumes=resumes if isinstance(resumes, int) and resumes >= 0 else 0,
        exports_per_resume=exports if isinstance(exports, int) and exports >= 0 else 0,
    )


def limits_as_data(plan: PlanLimits) -> dict[str, object]:
    return {
        "units": dict(plan.units),
        "resumes": plan.resumes,
        "exports_per_resume": plan.exports_per_resume,
    }


# ---------------------------------------------------------------- the period


def period_start(now: datetime) -> date:
    """The first day of the calendar month, in UTC. Usage is counted from here."""
    utc = now.astimezone(UTC)
    return date(utc.year, utc.month, 1)


def next_reset(now: datetime) -> datetime:
    """When the month rolls over and usage starts again, in UTC."""
    start = period_start(now)
    following = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return datetime(following.year, following.month, 1, tzinfo=UTC)


# ---------------------------------------------------------------- the decision


@dataclass(frozen=True)
class Decision:
    allowed: bool
    used: int
    limit: int | None

    @property
    def remaining(self) -> int | None:
        return None if self.limit is None else max(0, self.limit - self.used)


def decide(limit: int | None, used: int, amount: int = 1) -> Decision:
    """May `amount` more be used, given what has been used? No limit always allows."""
    if limit is None:
        return Decision(True, used, None)
    return Decision(used + amount <= limit, used, limit)


def meter_state(limit: int | None, used: int) -> str:
    """ "ok", "near" (80 percent or more) or "reached", for the usage display."""
    if limit is None:
        return "ok"
    if limit == 0 or used >= limit:
        return "reached"
    return "near" if used * 5 >= limit * 4 else "ok"


def percent(limit: int | None, used: int) -> int:
    if limit is None or limit == 0:
        return 0 if limit is None else 100
    return min(100, round(100 * used / limit))


def quota_message(unit: str, plan_label: str, used: int, limit: int, resets: datetime) -> str:
    """One plain sentence: what was used, what the plan allows, and when it starts again."""
    label, noun = UNIT_LABELS[unit]
    when = f"{resets:%d %B}".lstrip("0")
    if limit == 0:
        return f"The {plan_label} plan does not include {label.lower()}. See your plan for what it does include."
    return (
        f"You have used {used} of the {limit} {noun} the {plan_label} plan includes this month. "
        f"It starts again on {when}. Nothing was changed."
    )


def resume_limit_message(plan_label: str, limit: int) -> str:
    noun = "resume" if limit == 1 else "resumes"
    return f"The {plan_label} plan keeps {limit} {noun}. Delete one first to start another."
