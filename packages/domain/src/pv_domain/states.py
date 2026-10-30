"""The shared state vocabulary.

Three layers, one direction of translation:
  TaskState / RunState  what the machinery records (backend only)
  UiState               what the user is shown (backend computes it, frontend renders it)

The frontend never invents a state. `npm run check:states` (apps/web) parses the UiState
class below and fails CI if the TypeScript union differs. Keep the members as simple
`NAME = "value"` lines so that script can read them.
"""

from enum import StrEnum


class TaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRY_SCHEDULED = "retry_scheduled"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class RunState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    NEEDS_USER_INPUT = "needs_user_input"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


# What the user sees for an uploaded resume. The browser adds Idle and Uploading itself.
class ResumeUiState(StrEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    NEEDS_CORRECTION = "needs_correction"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class UiState(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    WAITING_FOR_YOU = "waiting_for_you"
    RETRYING = "retrying"
    COMPLETED = "completed"
    RETRY_AVAILABLE = "retry_available"
    PERMANENTLY_FAILED = "permanently_failed"
    CANCELLED = "cancelled"


_TASK_TO_UI = {
    TaskState.QUEUED: UiState.QUEUED,
    TaskState.RUNNING: UiState.PROCESSING,
    TaskState.SUCCEEDED: UiState.COMPLETED,
    TaskState.RETRY_SCHEDULED: UiState.RETRYING,
    TaskState.DEAD_LETTER: UiState.PERMANENTLY_FAILED,
    TaskState.CANCELLED: UiState.CANCELLED,
}

_RUN_TO_UI = {
    RunState.QUEUED: UiState.QUEUED,
    RunState.RUNNING: UiState.PROCESSING,
    RunState.NEEDS_USER_INPUT: UiState.WAITING_FOR_YOU,
    RunState.RETRYING: UiState.RETRYING,
    RunState.SUCCEEDED: UiState.COMPLETED,
    RunState.CANCELLED: UiState.CANCELLED,
}

_STEP_TO_UI = {
    StepState.PENDING: UiState.QUEUED,
    StepState.RUNNING: UiState.PROCESSING,
    StepState.SUCCEEDED: UiState.COMPLETED,
    StepState.FAILED: UiState.PERMANENTLY_FAILED,
    StepState.SKIPPED: UiState.CANCELLED,
}


def ui_state_for_task(state: TaskState) -> UiState:
    return _TASK_TO_UI[state]


def ui_state_for_run(state: RunState, *, can_retry: bool) -> UiState:
    """A failed run is 'retry available' only when a retry can actually help."""
    if state is RunState.FAILED:
        return UiState.RETRY_AVAILABLE if can_retry else UiState.PERMANENTLY_FAILED
    return _RUN_TO_UI[state]


def ui_state_for_step(state: StepState) -> UiState:
    return _STEP_TO_UI[state]


WORKFLOW_LABELS = {
    "demo": "Demo run",
    "resume_parse": "Resume parsing",
    "job_analysis": "Job analysis",
}


def workflow_label(workflow_type: str) -> str:
    return WORKFLOW_LABELS.get(workflow_type, workflow_type.replace("_", " ").capitalize())
