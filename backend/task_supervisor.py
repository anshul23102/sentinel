"""
TaskSupervisor — centralized lifecycle management for background asyncio tasks.

Tracks, cancels, and optionally restarts long-running background tasks so that
the application can shut down cleanly without orphaned tasks or leaked resources.
"""

import asyncio
import logging
from typing import Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class TaskSupervisor:
    """Central registry for long-running background tasks.

    Usage::

        supervisor = TaskSupervisor()

        # Start a task (with optional auto-restart)
        supervisor.register("pipeline", log_pipeline, restart=True)

        # On shutdown
        await supervisor.cancel_all()
    """

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._shutting_down = False

    def register(
        self,
        name: str,
        coro_factory: Callable[[], Coroutine],
        restart: bool = False,
        restart_backoff: float = 1.0,
    ) -> asyncio.Task:
        """Start and track a background task.

        Args:
            name: Unique name for the task (used in logs and lookups).
            coro_factory: A callable that returns a fresh coroutine object.
                Called each time the task starts or restarts.
            restart: If True, automatically restart after unexpected failure
                or normal completion (with exponential backoff).
                Cancelled tasks are never restarted.
            restart_backoff: Initial backoff in seconds.

        Returns:
            The created :class:`asyncio.Task`.
        """
        if name in self._tasks:
            raise ValueError(f"Task '{name}' is already registered")

        task = asyncio.create_task(
            self._wrap(name, coro_factory, restart, restart_backoff),
            name=name,
        )
        self._tasks[name] = task
        logger.info("[supervisor] Registered task '%s' (restart=%s)", name, restart)
        return task

    async def _wrap(
        self,
        name: str,
        coro_factory: Callable[[], Coroutine],
        restart: bool,
        restart_backoff: float,
    ) -> None:
        """Execute *coro_factory* with restart and cancellation semantics."""
        backoff = restart_backoff

        try:
            while True:
                try:
                    await coro_factory()
                except asyncio.CancelledError:
                    logger.info(
                        "[supervisor] Task '%s' cancelled, cleaning up", name
                    )
                    raise
                except Exception as exc:
                    logger.error(
                        "[supervisor] Task '%s' failed: %s",
                        name,
                        exc,
                        exc_info=True,
                    )
                    if restart and not self._shutting_down:
                        logger.info(
                            "[supervisor] Task '%s' restarting in %.1fs",
                            name,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 60.0)
                        continue
                    raise
                else:
                    if restart and not self._shutting_down:
                        logger.info(
                            "[supervisor] Task '%s' exited normally, restarting in %.1fs",
                            name,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 60.0)
                        continue
                    break
        finally:
            # Remove completed / cancelled tasks from the registry so we don't
            # leak references for fire-and-forget tasks (e.g. per-anomaly AI
            # analysis). Restartable tasks that are about to loop again stay
            # registered because this finally block only runs when _wrap() is
            # actually exiting.
            self._tasks.pop(name, None)

    async def cancel_all(self) -> None:
        """Cancel every tracked task and await its completion.

        ``asyncio.gather(..., return_exceptions=True)`` ensures one misbehaving
        task does not prevent the others from being awaited.
        """
        async with self._lock:
            self._shutting_down = True
            tasks = list(self._tasks.values())

        if not tasks:
            logger.info("[supervisor] cancel_all called with no tasks")
            return

        logger.info("[supervisor] Cancelling %d task(s)...", len(tasks))
        for task in tasks:
            if not task.done():
                task.cancel()

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for task, result in zip(tasks, results):
            if isinstance(result, asyncio.CancelledError):
                logger.info("[supervisor] Task '%s' cancelled", task.get_name())
            elif isinstance(result, BaseException):
                logger.error(
                    "[supervisor] Task '%s' raised during shutdown: %s",
                    task.get_name(),
                    result,
                )

        pending = [t for t in tasks if not t.done()]
        if pending:
            logger.warning(
                "[supervisor] %d task(s) still pending after cancel_all",
                len(pending),
            )
        else:
            logger.info("[supervisor] All tasks cancelled and completed")

        self._tasks.clear()

    def get_task(self, name: str) -> Optional[asyncio.Task]:
        """Return the tracked task by name, or ``None``."""
        return self._tasks.get(name)

    def is_running(self, name: str) -> bool:
        """True if the named task exists and has not yet finished."""
        task = self._tasks.get(name)
        return task is not None and not task.done()
