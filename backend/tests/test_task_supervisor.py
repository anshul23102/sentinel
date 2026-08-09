"""
Tests for TaskSupervisor and background task lifecycle management.

Issue #61 - Graceful Cancellation and Cleanup for Background Async Tasks
"""

import asyncio
import logging

import pytest

from task_supervisor import TaskSupervisor


# ===========================================================================
# Helpers
# ===========================================================================

async def _fast_task():
    await asyncio.sleep(0.05)


async def _slow_task():
    await asyncio.sleep(10)


async def _failing_task(call_count_ref):
    call_count_ref[0] += 1
    raise ValueError("intentional failure")


async def _task_with_cleanup(cleanup_ref):
    try:
        await asyncio.sleep(10)
    finally:
        cleanup_ref[0] = True


# ===========================================================================
# TaskSupervisor unit tests
# ===========================================================================

class TestTaskSupervisor:
    """Isolated tests for the TaskSupervisor class."""

    @pytest.fixture(autouse=True)
    def _suppress_supervisor_logging(self):
        logging.disable(logging.CRITICAL)
        yield
        logging.disable(logging.NOTSET)

    @pytest.mark.asyncio
    async def test_register_creates_task(self):
        supervisor = TaskSupervisor()
        task = supervisor.register("fast", _fast_task)
        assert task is not None
        assert not task.done()

    @pytest.mark.asyncio
    async def test_register_duplicate_raises(self):
        supervisor = TaskSupervisor()
        supervisor.register("fast", _fast_task)
        with pytest.raises(ValueError, match="already registered"):
            supervisor.register("fast", _fast_task)

    def test_get_task_returns_none_for_unknown(self):
        supervisor = TaskSupervisor()
        assert supervisor.get_task("nonexistent") is None

    @pytest.mark.asyncio
    async def test_is_running_true_when_active(self):
        supervisor = TaskSupervisor()
        supervisor.register("fast", _fast_task)
        assert supervisor.is_running("fast") is True

    @pytest.mark.asyncio
    async def test_is_running_false_when_done(self):
        supervisor = TaskSupervisor()
        supervisor.register("fast", _fast_task)
        await asyncio.sleep(0.2)
        assert supervisor.is_running("fast") is False

    @pytest.mark.asyncio
    async def test_cancel_all_cancels_running_tasks(self):
        supervisor = TaskSupervisor()
        task = supervisor.register("slow", _slow_task)
        await asyncio.sleep(0.1)
        await supervisor.cancel_all()
        assert task is not None
        assert task.done()

    @pytest.mark.asyncio
    async def test_cancel_all_awaits_completion(self):
        supervisor = TaskSupervisor()
        task = supervisor.register("slow", _slow_task)
        await asyncio.sleep(0.1)
        await supervisor.cancel_all()
        assert task.done()

    @pytest.mark.asyncio
    async def test_cancelled_error_not_restarted(self):
        supervisor = TaskSupervisor()
        call_count = [0]

        async def restartable():
            call_count[0] += 1
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                raise

        supervisor.register("restartable", restartable, restart=True)
        await asyncio.sleep(0.1)
        await supervisor.cancel_all()
        await asyncio.sleep(0.1)
        assert call_count[0] == 1, "Cancelled task must not restart"

    @pytest.mark.asyncio
    async def test_cleanup_finally_executes_on_cancel(self):
        supervisor = TaskSupervisor()
        cleanup_called = [False]

        async def task_with_cleanup():
            try:
                await asyncio.sleep(10)
            finally:
                cleanup_called[0] = True

        supervisor.register("cleanup", task_with_cleanup)
        await asyncio.sleep(0.1)
        await supervisor.cancel_all()
        await asyncio.sleep(0.1)
        assert cleanup_called[0] is True

    @pytest.mark.asyncio
    async def test_no_orphan_tasks_after_shutdown(self):
        supervisor = TaskSupervisor()
        task1 = supervisor.register("fast", _fast_task)
        task2 = supervisor.register("slow", _slow_task)

        await asyncio.sleep(0.2)
        await supervisor.cancel_all()

        assert task1.done()
        assert task2.done()
        assert not supervisor.is_running("fast")
        assert not supervisor.is_running("slow")

    @pytest.mark.asyncio
    async def test_completed_non_restartable_tasks_are_removed(self):
        supervisor = TaskSupervisor()
        task = supervisor.register("fast", _fast_task)
        await task
        assert supervisor.get_task("fast") is None

    @pytest.mark.asyncio
    async def test_multiple_tasks_cancelled_independently(self):
        supervisor = TaskSupervisor()
        task1_cancelled = [False]
        task2_done = [False]

        async def task1():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                task1_cancelled[0] = True
                raise

        async def task2():
            await asyncio.sleep(0.05)
            task2_done[0] = True

        task1_obj = supervisor.register("task1", task1)
        task2_obj = supervisor.register("task2", task2)
        await asyncio.sleep(0.1)

        task1_obj.cancel()
        await asyncio.sleep(0.1)

        assert task1_cancelled[0] is True
        assert task2_done[0] is True
        assert task1_obj.done()
        assert task2_obj.done()

    @pytest.mark.asyncio
    async def test_existing_restart_behavior_still_works(self):
        supervisor = TaskSupervisor()
        call_count = [0]

        async def failing():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("fail")
            await asyncio.sleep(10)

        supervisor.register(
            "failing", failing, restart=True, restart_backoff=0.01
        )
        await asyncio.sleep(0.5)
        assert call_count[0] == 3, "Restartable task should have restarted twice"

    @pytest.mark.asyncio
    async def test_cancel_all_with_no_tasks(self):
        supervisor = TaskSupervisor()
        await supervisor.cancel_all()

    @pytest.mark.asyncio
    async def test_cancel_all_handles_task_exceptions(self):
        supervisor = TaskSupervisor()

        async def failing():
            raise ValueError("boom")

        supervisor.register("failing", failing)
        await asyncio.sleep(0.1)
        await supervisor.cancel_all()


# ===========================================================================
# Integration tests for main.py lifespan
# ===========================================================================

class TestMainLifespan:
    """Verify that main.py wires tasks through the supervisor correctly."""

    @pytest.mark.asyncio
    async def test_lifespan_starts_critical_tasks(self):
        from main import lifespan, supervisor

        class FakeApp:
            pass

        await supervisor.cancel_all()

        async with lifespan(FakeApp()):
            assert supervisor.is_running("pipeline")
            assert supervisor.is_running("scan")

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_cancels_tasks(self):
        from main import lifespan, supervisor

        class FakeApp:
            pass

        await supervisor.cancel_all()

        async with lifespan(FakeApp()):
            assert supervisor.is_running("pipeline")
            assert supervisor.is_running("scan")

        assert not supervisor.is_running("pipeline")
        assert not supervisor.is_running("scan")

    @pytest.mark.asyncio
    async def test_health_endpoint_reports_supervisor_state(self):
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            response = client.get("/api/health")
            assert response.status_code == 200
            data = response.json()
            assert "monitoring" in data
            assert "log_pipeline_running" in data["monitoring"]
            assert "anomaly_detector_running" in data["monitoring"]

    @pytest.mark.asyncio
    async def test_all_critical_tasks_are_tracked(self):
        from main import lifespan, supervisor

        class FakeApp:
            pass

        await supervisor.cancel_all()

        async with lifespan(FakeApp()):
            registered = list(supervisor._tasks.keys())
            assert "pipeline" in registered
            assert "scan" in registered
