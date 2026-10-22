import pytest

from pv_domain.states import (
    RunState,
    StepState,
    TaskState,
    UiState,
    ui_state_for_run,
    ui_state_for_step,
    ui_state_for_task,
    workflow_label,
)

EXPECTED_UI_STATES = [
    "queued",
    "processing",
    "waiting_for_you",
    "retrying",
    "completed",
    "retry_available",
    "permanently_failed",
    "cancelled",
]


def test_ui_state_list_is_the_agreed_vocabulary() -> None:
    # The frontend union is compared with this class by `npm run check:states`.
    assert [state.value for state in UiState] == EXPECTED_UI_STATES


@pytest.mark.parametrize("state", list(TaskState))
def test_every_task_state_has_a_ui_state(state: TaskState) -> None:
    assert isinstance(ui_state_for_task(state), UiState)


@pytest.mark.parametrize("state", list(StepState))
def test_every_step_state_has_a_ui_state(state: StepState) -> None:
    assert isinstance(ui_state_for_step(state), UiState)


@pytest.mark.parametrize("state", list(RunState))
@pytest.mark.parametrize("can_retry", [True, False])
def test_every_run_state_has_a_ui_state(state: RunState, can_retry: bool) -> None:
    assert isinstance(ui_state_for_run(state, can_retry=can_retry), UiState)


def test_failed_run_is_retry_available_only_when_a_retry_can_help() -> None:
    assert ui_state_for_run(RunState.FAILED, can_retry=True) is UiState.RETRY_AVAILABLE
    assert ui_state_for_run(RunState.FAILED, can_retry=False) is UiState.PERMANENTLY_FAILED


def test_dead_letter_is_permanently_failed_for_users() -> None:
    assert ui_state_for_task(TaskState.DEAD_LETTER) is UiState.PERMANENTLY_FAILED
    assert ui_state_for_task(TaskState.RETRY_SCHEDULED) is UiState.RETRYING


def test_waiting_for_user_input_is_its_own_state() -> None:
    assert ui_state_for_run(RunState.NEEDS_USER_INPUT, can_retry=False) is UiState.WAITING_FOR_YOU


def test_workflow_labels() -> None:
    assert workflow_label("job_analysis") == "Job analysis"
    assert workflow_label("something_new") == "Something new"
