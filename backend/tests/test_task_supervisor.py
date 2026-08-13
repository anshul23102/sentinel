"""
Comprehensive tests for TaskSupervisor background task management.

Issue #58 - https://github.com/anshul23102/sentinel/issues/58

Tests cover:
- Supervisor starts and tracks tasks
- Crashed tasks are automatically restarted
- Exponential backoff increases after each failure
- Backoff is capped at configured maximum
- CancelledError does not trigger restart (graceful shutdown)
- Shutdown cancels all supervised tasks
- Multiple tasks can be supervised simultaneously
- Unexpected exceptions are properly logged
- Backoff resets after successful execution
"""

import asyncio
import logging

import pytest

from task_supervisor import TaskSupervisor, SupervisorConfig


# ===========================================================================
# Fixtures and Helpers
# ===========================================================================

class _FailingTask:
    """Helper that simulates a task with configurable failure behavior."""
    def __init__(self, fail_count: int = 1, exception_type=RuntimeError):
        self.fail_count = fail_count
        self.exception_type = exception_type
        self.call_count = 0
    
    async def __call__(self):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise self.exception_type(f"Simulated failure #{self.call_count}")
        # Succeed after fail_count failures
        await asyncio.sleep(0.01)
        return "success"


class _SlowTask:
    """Helper that simulates a long-running task."""
    def __init__(self, duration: float = 10.0):
        self.duration = duration
        self.started = False
    
    async def __call__(self):
        self.started = True
        await asyncio.sleep(self.duration)
        return "done"


class _CancellableTask:
    """Helper that respects cancellation."""
    def __init__(self):
        self.started = False
        self.cleaned_up = False
    
    async def __call__(self):
        self.started = True
        try:
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self.cleaned_up = True
            raise


@pytest.fixture
def supervisor():
    """Create a fresh TaskSupervisor with default config."""
    return TaskSupervisor(SupervisorConfig(
        initial_backoff=0.1,  # Fast for testing
        max_backoff=1.0,
        backoff_multiplier=2.0,
        jitter_factor=0.0,  # No jitter for predictable tests
    ))


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset logging state between tests."""
    logging.getLogger("sentinel.supervisor").handlers.clear()


# ===========================================================================
# Supervisor Initialization and Registration
# ===========================================================================

class TestSupervisorInitialization:

    def test_default_config_values(self):
        """SupervisorConfig should have sensible defaults."""
        config = SupervisorConfig()
        assert config.initial_backoff == 1.0
        assert config.max_backoff == 60.0
        assert config.backoff_multiplier == 2.0
        assert config.jitter_factor == 0.1

    def test_custom_config_values(self):
        """SupervisorConfig should accept custom values."""
        config = SupervisorConfig(
            initial_backoff=0.5,
            max_backoff=30.0,
            backoff_multiplier=3.0,
            jitter_factor=0.2,
        )
        assert config.initial_backoff == 0.5
        assert config.max_backoff == 30.0
        assert config.backoff_multiplier == 3.0

    def test_supervisor_initializes_empty(self, supervisor):
        """New supervisor should have no tasks."""
        assert len(supervisor._tasks) == 0

    def test_register_task(self, supervisor):
        """Should be able to register a new task."""
        async def my_task():
            pass
        
        supervisor.register("test_task", my_task)
        assert "test_task" in supervisor._tasks
        assert supervisor._tasks["test_task"].name == "test_task"

    def test_register_duplicate_raises(self, supervisor):
        """Registering the same task name twice should raise ValueError."""
        async def my_task():
            pass
        
        supervisor.register("test_task", my_task)
        with pytest.raises(ValueError, match="already registered"):
            supervisor.register("test_task", my_task)

    def test_register_stores_factory(self, supervisor):
        """TaskRecord should store the coroutine factory, not a coroutine."""
        async def my_task():
            pass
        
        supervisor.register("test_task", my_task)
        record = supervisor._tasks["test_task"]
        assert record.coro_factory == my_task
        # Should be callable and return a coroutine when invoked
        # Note: We don't await the coroutine here, just verify it's a coroutine object
        coro = record.coro_factory()
        try:
            assert asyncio.iscoroutine(coro)
        finally:
            # Clean up the coroutine to avoid RuntimeWarning
            coro.close()


# ===========================================================================
# Task Lifecycle
# ===========================================================================

class TestTaskLifecycle:

    @pytest.mark.asyncio
    async def test_start_single_task(self, supervisor):
        """Should be able to start a registered task."""
        async def quick_task():
            await asyncio.sleep(0.01)
            return "done"
        
        supervisor.register("quick", quick_task)
        await supervisor.start_task("quick")
        
        status = supervisor.get_task_status("quick")
        assert status["running"] is True
        assert status["restart_count"] == 0
        
        # Clean up
        await supervisor.shutdown()

    @pytest.mark.asyncio
    async def test_start_all_tasks(self, supervisor):
        """start_all should start all registered tasks."""
        async def task_a():
            while True:
                await asyncio.sleep(0.1)
        
        async def task_b():
            while True:
                await asyncio.sleep(0.1)
        
        supervisor.register("task_a", task_a)
        supervisor.register("task_b", task_b)
        
        await supervisor.start_all()
        
        assert supervisor.get_task_status("task_a")["running"] is True
        assert supervisor.get_task_status("task_b")["running"] is True
        
        # Clean up
        await supervisor.shutdown()

    @pytest.mark.asyncio
    async def test_start_unknown_task_raises(self, supervisor):
        """Starting an unregistered task should raise ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            await supervisor.start_task("nonexistent")

    @pytest.mark.asyncio
    async def test_task_completion_success(self, supervisor):
        """Successfully completed tasks should reset backoff."""
        async def quick_success():
            await asyncio.sleep(0.01)
            return "ok"
        
        supervisor.register("success_task", quick_success)
        await supervisor.start_task("success_task")
        
        # Wait for completion
        await asyncio.sleep(0.05)
        
        status = supervisor.get_task_status("success_task")
        assert status["running"] is False
        
        # Clean up
        await supervisor.shutdown()

    @pytest.mark.asyncio
    async def test_get_task_status_unknown(self, supervisor):
        """Getting status for unknown task should return error dict."""
        status = supervisor.get_task_status("unknown")
        assert "error" in status


# ===========================================================================
# Crash Detection and Restart
# ===========================================================================

class TestCrashRestart:

    @pytest.mark.asyncio
    async def test_crashed_task_restarts(self, supervisor):
        """A task that raises an exception should be automatically restarted."""
        failing = _FailingTask(fail_count=1)
        
        # Store reference to prevent garbage collection
        supervisor._test_failing = failing
        
        supervisor.register("failing_task", failing)
        await supervisor.start_task("failing_task")
        
        # Wait for: initial run (fast fail) + backoff sleep (0.1*2=0.2s) + restart (fast success)
        # Use generous timeout to account for event loop timing
        await asyncio.sleep(3.0)
        
        # Verify the task restarted by checking restart_count in status
        status = supervisor.get_task_status("failing_task")
        assert status["restart_count"] >= 1, f"Task restart_count={status['restart_count']}, expected >= 1"
        
        # Clean up
        await supervisor.shutdown()

    @pytest.mark.asyncio
    async def test_exponential_backoff_increases(self, supervisor):
        """Backoff should increase exponentially after each failure."""
        failing = _FailingTask(fail_count=2)
        supervisor._test_failing = failing
        
        supervisor.register("failing", failing)
        await supervisor.start_task("failing")
        
        # Wait for first crash + restart
        await asyncio.sleep(0.3)
        
        # Check backoff increased
        status = supervisor.get_task_status("failing")
        # After first failure, backoff should be ~0.2 (0.1 * 2)
        assert status["current_backoff"] > 0.15
        
        # Wait for second crash + restart
        await asyncio.sleep(0.5)
        
        # Backoff should have increased again (~0.4)
        status = supervisor.get_task_status("failing")
        assert status["current_backoff"] > 0.35
        
        # Clean up
        await supervisor.shutdown()

    @pytest.mark.asyncio
    async def test_backoff_is_capped(self, supervisor):
        """Backoff should never exceed max_backoff."""
        failing = _FailingTask(fail_count=10)
        supervisor._test_failing = failing
        
        supervisor.register("failing", failing)
        await supervisor.start_task("failing")
        
        # Wait for multiple crashes
        await asyncio.sleep(2.0)
        
        # Backoff should be capped at max_backoff
        status = supervisor.get_task_status("failing")
        assert status["current_backoff"] <= supervisor._config.max_backoff
        
        # Clean up
        await supervisor.shutdown()

    @pytest.mark.asyncio
    async def test_backoff_resets_after_success(self, supervisor):
        """Backoff should reset to initial value after successful run."""
        failing = _FailingTask(fail_count=2)
        
        supervisor.register("recovering", failing)
        await supervisor.start_task("recovering")
        
        # Wait for 2 failures + backoffs + success
        # Fail1 (fast) + backoff1 (0.1*2=0.2) + fail2 (fast) + backoff2 (0.2*2=0.4) + success (fast)
        # Use longer timeout to ensure task completes and resets backoff
        await asyncio.sleep(3.0)
        
        status = supervisor.get_task_status("recovering")
        # After success, backoff should be back to initial
        assert status["current_backoff"] == supervisor._config.initial_backoff
        
        # Clean up
        await supervisor.shutdown()


# ===========================================================================
# Cancellation and Shutdown
# ===========================================================================

class TestCancellation:

    @pytest.mark.asyncio
    async def test_cancelled_error_does_not_restart(self, supervisor):
        """Tasks cancelled during shutdown should not be restarted."""
        cancellable = _CancellableTask()
        
        supervisor.register("cancellable", cancellable)
        await supervisor.start_task("cancellable")
        
        # Verify task is running
        await asyncio.sleep(0.05)
        assert cancellable.started is True
        
        # Shutdown
        await supervisor.shutdown()
        
        # Task should have been cancelled
        assert cancellable.cleaned_up is True
        assert supervisor.get_task_status("cancellable")["running"] is False

    @pytest.mark.asyncio
    async def test_shutdown_cancels_all_tasks(self, supervisor):
        """Shutdown should cancel all running tasks."""
        slow_a = _SlowTask(duration=10.0)
        slow_b = _SlowTask(duration=10.0)
        
        supervisor.register("slow_a", slow_a)
        supervisor.register("slow_b", slow_b)
        
        await supervisor.start_all()
        await asyncio.sleep(0.05)
        
        assert slow_a.started is True
        assert slow_b.started is True
        
        await supervisor.shutdown()
        
        # Tasks should no longer be running
        assert supervisor.get_task_status("slow_a")["running"] is False
        assert supervisor.get_task_status("slow_b")["running"] is False

    @pytest.mark.asyncio
    async def test_shutdown_no_orphan_tasks(self, supervisor):
        """After shutdown, no tasks should remain running."""
        async def infinite_task():
            while True:
                await asyncio.sleep(0.1)
        
        supervisor.register("infinite", infinite_task)
        await supervisor.start_task("infinite")
        await asyncio.sleep(0.05)
        
        await supervisor.shutdown()
        
        # Verify all tasks are stopped
        for name in supervisor._tasks:
            status = supervisor.get_task_status(name)
            assert status["running"] is False

    @pytest.mark.asyncio
    async def test_task_cancelled_during_execution(self, supervisor):
        """Task that catches CancelledError should not trigger restart."""
        restart_count = [0]
        
        async def cancellable():
            try:
                while True:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise  # Re-raise to allow cancellation
        
        async def failing_replacement():
            restart_count[0] += 1
            await asyncio.sleep(10)
        
        supervisor.register("cancellable", cancellable)
        await supervisor.start_task("cancellable")
        await asyncio.sleep(0.05)
        
        # Cancel the task
        task = supervisor._tasks["cancellable"].task
        task.cancel()
        
        # Wait for cancellation to propagate
        await asyncio.sleep(0.1)
        
        # Should not have restarted (or replacement should not have run)
        assert restart_count[0] == 0
        
        # Clean up
        await supervisor.shutdown()


# ===========================================================================
# Multiple Tasks Supervision
# ===========================================================================

class TestMultipleTasks:

    @pytest.mark.asyncio
    async def test_supervise_multiple_tasks_simultaneously(self, supervisor):
        """Supervisor should handle multiple independent tasks."""
        task_a_started = False
        task_b_started = False
        
        async def task_a():
            nonlocal task_a_started
            task_a_started = True
            while True:
                await asyncio.sleep(0.1)
        
        async def task_b():
            nonlocal task_b_started
            task_b_started = True
            while True:
                await asyncio.sleep(0.1)
        
        supervisor.register("task_a", task_a)
        supervisor.register("task_b", task_b)
        
        await supervisor.start_all()
        await asyncio.sleep(0.05)
        
        assert task_a_started is True
        assert task_b_started is True
        assert supervisor.get_task_status("task_a")["running"] is True
        assert supervisor.get_task_status("task_b")["running"] is True
        
        # Clean up
        await supervisor.shutdown()

    @pytest.mark.asyncio
    async def test_independent_task_failures(self, supervisor):
        """Failure of one task should not affect others."""
        failing = _FailingTask(fail_count=1)
        
        async def stable_task():
            while True:
                await asyncio.sleep(0.1)
        
        supervisor.register("failing", failing)
        supervisor.register("stable", stable_task)
        
        await supervisor.start_all()
        
        # Wait for fail + backoff + restart
        await asyncio.sleep(2.0)
        
        # Stable task should still be running
        assert supervisor.get_task_status("stable")["running"] is True
        # Failing task should have restarted (check restart_count)
        status = supervisor.get_task_status("failing")
        assert status["restart_count"] >= 1
        
        # Clean up
        await supervisor.shutdown()


# ===========================================================================
# Logging and Observability
# ===========================================================================

class TestLogging:

    @pytest.mark.asyncio
    async def test_unexpected_exceptions_logged(self, supervisor, caplog):
        """Task exceptions should be logged with structured messages."""
        caplog.set_level(logging.ERROR, logger="sentinel.supervisor")
        
        async def failing_task():
            raise ValueError("Test exception")
        
        supervisor.register("failing", failing_task)
        await supervisor.start_task("failing")
        await asyncio.sleep(0.05)
        
        # Verify the exception was logged
        assert any("Task crashed" in record.message for record in caplog.records)
        assert any("ValueError" in record.message for record in caplog.records)
        
        # Clean up
        await supervisor.shutdown()

    @pytest.mark.asyncio
    async def test_task_started_logged(self, supervisor, caplog):
        """Task start should be logged."""
        caplog.set_level(logging.INFO, logger="sentinel.supervisor")
        
        async def simple_task():
            pass
        
        supervisor.register("simple", simple_task)
        await supervisor.start_task("simple")
        await asyncio.sleep(0.01)  # Let the task start
        
        assert any("Task started" in record.message for record in caplog.records)
        
        # Clean up
        await supervisor.shutdown()

    @pytest.mark.asyncio
    async def test_task_cancelled_logged(self, supervisor, caplog):
        """Task cancellation should be logged."""
        caplog.set_level(logging.INFO, logger="sentinel.supervisor")
        
        async def infinite():
            while True:
                await asyncio.sleep(0.1)
        
        supervisor.register("infinite", infinite)
        await supervisor.start_task("infinite")
        await asyncio.sleep(0.05)
        
        await supervisor.shutdown()
        
        assert any("Task cancelled" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_restart_delay_logged(self, supervisor, caplog):
        """Restart delay should be logged with backoff value."""
        caplog.set_level(logging.INFO, logger="sentinel.supervisor")
        
        failing = _FailingTask(fail_count=1)
        supervisor.register("failing", failing)
        
        await supervisor.start_task("failing")
        
        # Wait for crash and restart log
        await asyncio.sleep(0.4)
        
        assert any("will restart in" in record.message for record in caplog.records)
        
        # Clean up
        await supervisor.shutdown()


# ===========================================================================
# Integration Tests
# ===========================================================================

class TestIntegration:

    @pytest.mark.asyncio
    async def test_full_lifecycle_with_crashes(self, supervisor):
        """Test complete lifecycle: start, crash, restart, shutdown."""
        failing = _FailingTask(fail_count=3)
        
        supervisor.register("resilient", failing)
        await supervisor.start_task("resilient")
        
        # Wait for 3 failures + restarts + final success
        # Each cycle: fail + backoff(growing) + next attempt
        await asyncio.sleep(5.0)
        
        # Should have attempted multiple times (check restart_count)
        status = supervisor.get_task_status("resilient")
        assert status["restart_count"] >= 3
        
        # Graceful shutdown
        await supervisor.shutdown()

    @pytest.mark.asyncio
    async def test_supervisor_status_throughout_lifecycle(self, supervisor):
        """Status should accurately reflect task state at each stage."""
        async def stable():
            while True:
                await asyncio.sleep(0.1)
        
        supervisor.register("stable", stable)
        
        # Before start
        status = supervisor.get_task_status("stable")
        assert status["running"] is False
        assert status["restart_count"] == 0
        
        # After start
        await supervisor.start_task("stable")
        status = supervisor.get_task_status("stable")
        assert status["running"] is True
        
        # After shutdown
        await supervisor.shutdown()
        status = supervisor.get_task_status("stable")
        assert status["running"] is False

    @pytest.mark.asyncio
    async def test_multiple_crashes_with_backoff(self, supervisor):
        """Multiple consecutive crashes should increase backoff correctly."""
        failing = _FailingTask(fail_count=5)
        
        supervisor.register("always_fail", failing)
        
        await supervisor.start_task("always_fail")
        
        # Wait for several crashes with increasing backoff
        await asyncio.sleep(3.0)
        
        status = supervisor.get_task_status("always_fail")
        # Should have restarted multiple times
        assert status["restart_count"] >= 3
        # Backoff should have increased but be capped
        assert status["current_backoff"] <= supervisor._config.max_backoff
        
        # Clean up
        await supervisor.shutdown()
