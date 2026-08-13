"""
Production-quality background task supervisor with automatic restart capability.

Issue #58 - https://github.com/anshul23102/sentinel/issues/58

Provides:
- Named task registration and management
- Automatic restart on unhandled exceptions
- Exponential backoff with configurable limits
- Structured logging instead of print statements
- Graceful shutdown with proper cancellation handling
- Thread-safe state management for async context
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("sentinel.supervisor")


@dataclass
class SupervisorConfig:
    """Configuration for task restart behavior."""
    initial_backoff: float = 1.0       # Initial delay before restart (seconds)
    max_backoff: float = 60.0          # Maximum backoff cap (seconds)
    backoff_multiplier: float = 2.0    # Exponential growth factor
    jitter_factor: float = 0.1         # Random jitter to prevent thundering herd (10%)


@dataclass
class TaskRecord:
    """Tracks state for a supervised task."""
    name: str
    coro_factory: Callable[[], Awaitable[Any]]
    task: asyncio.Task | None = None
    backoff: float = field(default_factory=lambda: SupervisorConfig().initial_backoff)
    restart_count: int = 0
    last_started: datetime | None = None
    last_crashed: datetime | None = None
    _shutting_down: bool = False


class TaskSupervisor:
    """
    Supervises long-running background tasks with automatic restart on failure.
    
    Usage:
        config = SupervisorConfig(initial_backoff=1.0, max_backoff=60.0)
        supervisor = TaskSupervisor(config)
        
        # Register tasks
        supervisor.register("log_pipeline", log_pipeline)
        supervisor.register("periodic_scan", periodic_scan)
        
        # Start all tasks
        await supervisor.start_all()
        
        # On shutdown
        await supervisor.shutdown()
    """

    def __init__(self, config: SupervisorConfig | None = None):
        self._config = config or SupervisorConfig()
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = asyncio.Lock()

    def register(self, name: str, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        """
        Register a task for supervision.
        
        Args:
            name: Unique identifier for the task
            coro_factory: Zero-argument callable that returns a new coroutine.
                         Must be a factory to allow creating fresh coroutines on restart.
        """
        if name in self._tasks:
            raise ValueError(f"Task '{name}' is already registered")
        
        self._tasks[name] = TaskRecord(
            name=name,
            coro_factory=coro_factory,
        )
        logger.info("Registered supervised task: %s", name)

    async def start_all(self) -> None:
        """Start all registered tasks concurrently."""
        async with self._lock:
            for name in self._tasks:
                if not self._tasks[name]._shutting_down:
                    await self._start_task_internal(name)

    async def start_task(self, name: str) -> None:
        """Start a specific registered task."""
        if name not in self._tasks:
            raise ValueError(f"Task '{name}' is not registered")
        
        async with self._lock:
            await self._start_task_internal(name)

    async def _start_task_internal(self, name: str) -> None:
        """Internal task start (must be called with lock held)."""
        record = self._tasks[name]
        
        if record.task is not None and not record.task.done():
            logger.warning("Task '%s' is already running", name)
            return
        
        # Keep a strong reference to the factory
        coro_factory = record.coro_factory
        
        # Create wrapped coroutine that handles restart with backoff
        async def wrapped_task():
            while True:
                try:
                    record.last_started = datetime.now(timezone.utc)
                    logger.info(
                        "Task started: %s (attempt #%d)",
                        name, record.restart_count + 1
                    )
                    await coro_factory()
                    # Task completed successfully
                    logger.info("Task completed normally: %s", name)
                    record.backoff = self._config.initial_backoff  # Reset backoff
                    break
                except asyncio.CancelledError:
                    logger.info("Task cancelled: %s", name)
                    raise
                except Exception as exc:
                    # Task crashed
                    record.last_crashed = datetime.now(timezone.utc)
                    record.restart_count += 1
                    logger.error(
                        "Task crashed: %s | Exception: %s: %s | Restart count: %d",
                        name, type(exc).__name__, exc, record.restart_count
                    )
                    
                    if record._shutting_down:
                        logger.info("Task not restarting due to shutdown: %s", name)
                        raise
                    
                    # Calculate backoff with jitter
                    delay = min(
                        record.backoff * self._config.backoff_multiplier,
                        self._config.max_backoff
                    )
                    jitter = delay * self._config.jitter_factor * random.random()
                    delay = delay + jitter
                    
                    logger.info(
                        "Task '%s' will restart in %.2fs (backoff: %.2fs)",
                        name, delay, delay
                    )
                    
                    record.backoff = delay
                    await asyncio.sleep(delay)
                    
                    if record._shutting_down:
                        logger.info("Task not restarting due to shutdown: %s", name)
                        raise asyncio.CancelledError()
                    
                    # Loop continues to restart
                    continue
        
        record.task = asyncio.create_task(wrapped_task(), name=f"supervised:{name}")
        record._crashed = False
        # Store strong reference to prevent garbage collection during backoff
        self._tasks[name] = record

    async def shutdown(self) -> None:
        """
        Gracefully shut down all supervised tasks.
        
        - Cancels all running tasks
        - Awaits their completion
        - Handles CancelledError correctly
        - Ensures no orphan tasks remain
        """
        logger.info("Supervisor shutdown initiated")
        
        async with self._lock:
            # Signal shutdown to all tasks
            for record in self._tasks.values():
                record._shutting_down = True
            
            # Collect tasks to cancel
            tasks_to_cancel = []
            for name, record in self._tasks.items():
                if record.task is not None and not record.task.done():
                    tasks_to_cancel.append(record.task)
                    logger.info("Cancelling task: %s", name)
                    record.task.cancel()
        
        # Await all cancellations
        if tasks_to_cancel:
            logger.info("Waiting for %d tasks to cancel...", len(tasks_to_cancel))
            await asyncio.gather(
                *tasks_to_cancel,
                return_exceptions=True,
            )
        
        # Verify no orphan tasks remain
        async with self._lock:
            for name, record in self._tasks.items():
                if record.task is not None and not record.task.done():
                    logger.warning(
                        "Orphan task detected: %s",
                        name
                    )
        
        logger.info("Supervisor shutdown complete")

    def get_task_status(self, name: str) -> dict[str, Any]:
        """Get current status of a supervised task."""
        if name not in self._tasks:
            return {"error": f"Task '{name}' not found"}
        
        record = self._tasks[name]
        is_running = (
            record.task is not None 
            and not record.task.done()
        )
        
        return {
            "name": name,
            "running": is_running,
            "restart_count": record.restart_count,
            "current_backoff": record.backoff,
            "last_started": record.last_started.isoformat() if record.last_started else None,
            "last_crashed": record.last_crashed.isoformat() if record.last_crashed else None,
        }

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all supervised tasks."""
        return {
            name: self.get_task_status(name) 
            for name in self._tasks
        }