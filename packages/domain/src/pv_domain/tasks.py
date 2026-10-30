"""Names of background task types and the rules that depend on them."""

TASK_SEND_EMAIL = "send_email"
TASK_DEMO = "system.demo"
TASK_PARSE_RESUME = "parse_resume"

# These carry a one-time secret (a link token) that is erased when the task finishes
# or dead-letters, so replaying them is impossible. The user must ask for a new link.
NON_REQUEUEABLE = frozenset({TASK_SEND_EMAIL})
