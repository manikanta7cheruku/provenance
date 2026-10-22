"""The worker loop.

One worker runs one task at a time. To go faster, run more workers: SKIP LOCKED lets
them share the queue without stepping on each other.

Shutdown: SIGTERM or SIGINT sets a flag. The worker finishes the task in hand, stops
claiming, removes its heartbeat row and exits. If it is killed harder than that (SIGKILL,
power loss) the task's lease simply expires and another worker takes over.
"""

import logging
import os
import signal
import socket
import tempfile
import threading
import time
import uuid
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from pv_config import Settings, get_settings
from pv_domain.redaction import error_summary
from pv_domain.retry import backoff_seconds
from pv_domain.states import RunState
from pv_mail import Mailer, build_mailer
from pv_persistence import queue, workers
from pv_persistence.engine import create_db_engine
from pv_persistence.runs import set_run_state
from pv_persistence.tenancy import tenant_session
from pv_worker.contract import Handler, TaskContext, TaskFailure
from pv_worker.handlers import build_registry
from pv_worker.logging_config import configure_logging

logger = logging.getLogger("pv_worker")

ALIVE_FILE = Path(tempfile.gettempdir()) / "pv_worker_alive"
MAINTENANCE_INTERVAL_SECONDS = 600.0
MAX_IDLE_BACKOFF_SECONDS = 30.0


class Worker:
    def __init__(
        self,
        engine: Engine,
        settings: Settings,
        registry: dict[str, Handler],
        *,
        mailer: Mailer,
        worker_id: str | None = None,
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._registry = registry
        self._mailer = mailer
        self.hostname = socket.gethostname()
        self.worker_id = worker_id or f"{self.hostname}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.tasks_processed = 0

    def run_once(self) -> bool:
        """Claim and run at most one task. Returns True if a task was handled."""
        task = queue.claim_next(
            self._engine,
            worker_id=self.worker_id,
            lease_seconds=self._settings.worker_lease_seconds,
            task_types=sorted(self._registry),
        )
        if task is None:
            return False
        started = time.perf_counter()
        context = TaskContext(
            task_id=task.id,
            task_type=task.task_type,
            args=_as_dict(task.payload.get("args")),
            secret=_as_dict(task.payload.get("secret")),
            attempt=task.attempts,
            max_attempts=task.max_attempts,
            owner_user_id=task.owner_user_id,
            run_id=task.run_id,
            settings=self._settings,
            engine=self._engine,
            mailer=self._mailer,
            extend_lease=lambda: queue.extend_lease(
                self._engine, task.id, self.worker_id, self._settings.worker_lease_seconds
            ),
        )
        outcome: str
        error: str | None = None
        try:
            self._registry[task.task_type](context)
        except TaskFailure as exc:
            error = error_summary("TaskFailure", str(exc))
            outcome = self._record_failure(task, retryable=exc.retryable, error=error)
        except Exception as exc:
            # A bug or an unexpected outage. Treated as retryable, bounded by max_attempts.
            error = error_summary(type(exc).__name__, str(exc))
            outcome = self._record_failure(task, retryable=True, error=error)
        else:
            done = queue.complete(self._engine, task.id, self.worker_id)
            outcome = "succeeded" if done else "lease_lost"
        self.tasks_processed += 1
        logger.info(
            "task_finished",
            extra={
                "task_id": str(task.id),
                "task_type": task.task_type,
                "run_id": str(task.run_id) if task.run_id else None,
                "attempt": task.attempts,
                "outcome": outcome,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "error": error,
            },
        )
        return True

    def _record_failure(self, task: queue.ClaimedTask, *, retryable: bool, error: str) -> str:
        outcome = queue.fail(
            self._engine,
            task,
            self.worker_id,
            retryable=retryable,
            error=error,
            delay_seconds=backoff_seconds(task.attempts),
        )
        if outcome == "dead_letter" and task.run_id and task.owner_user_id:
            self._fail_run(task)
        return outcome

    def _fail_run(self, task: queue.ClaimedTask) -> None:
        """A dead-lettered task ends its workflow run so the user is not left waiting."""
        if task.owner_user_id is None or task.run_id is None:
            return
        try:
            with tenant_session(self._engine, task.owner_user_id) as db:
                set_run_state(
                    db,
                    task.run_id,
                    RunState.FAILED,
                    can_retry=False,
                    error_class="INTERNAL_ERROR",
                    error_type="TaskFailure",
                    error_message="The background task failed permanently.",
                )
        except SQLAlchemyError:
            logger.warning("run_update_failed", exc_info=True, extra={"run_id": str(task.run_id)})

    def heartbeat(self) -> None:
        workers.heartbeat(
            self._engine,
            worker_id=self.worker_id,
            hostname=self.hostname,
            tasks_processed=self.tasks_processed,
        )
        ALIVE_FILE.touch()

    def run_forever(self, stop: threading.Event) -> None:
        beat = threading.Thread(target=self._heartbeat_loop, args=(stop,), daemon=True)
        beat.start()
        logger.info(
            "worker_started",
            extra={"worker_id": self.worker_id, "types": sorted(self._registry)},
        )
        last_maintenance = time.monotonic()
        failures = 0
        while not stop.is_set():
            try:
                worked = self.run_once()
                failures = 0
                if time.monotonic() - last_maintenance > MAINTENANCE_INTERVAL_SECONDS:
                    queue.purge_finished(
                        self._engine, older_than_days=self._settings.task_retention_days
                    )
                    last_maintenance = time.monotonic()
            except SQLAlchemyError:
                # Database restart or network blip. Back off and keep the process alive.
                failures += 1
                logger.error("worker_database_error", exc_info=True)
                pause = self._settings.worker_poll_interval_seconds * 5 * failures
                stop.wait(min(MAX_IDLE_BACKOFF_SECONDS, pause))
                continue
            if not worked:
                stop.wait(self._settings.worker_poll_interval_seconds)
        try:
            workers.forget(self._engine, self.worker_id)
        except SQLAlchemyError:
            logger.warning("worker_forget_failed", exc_info=True)
        logger.info("worker_stopped", extra={"worker_id": self.worker_id})

    def _heartbeat_loop(self, stop: threading.Event) -> None:
        while not stop.is_set():
            try:
                self.heartbeat()
            except (SQLAlchemyError, OSError):
                logger.warning("heartbeat_failed", exc_info=True)
            stop.wait(self._settings.worker_heartbeat_seconds)


def _as_dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_db_engine(settings.database_url.get_secret_value())
    worker = Worker(engine, settings, build_registry(), mailer=build_mailer(settings))
    stop = threading.Event()

    def _request_stop(signum: int, _frame: object) -> None:
        logger.info("shutdown_requested", extra={"signal": signum})
        stop.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    worker.run_forever(stop)
    engine.dispose()
    return 0
