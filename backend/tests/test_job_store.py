"""Tests for SQLite JobStore."""

import tempfile
from pathlib import Path

import pytest
from jiandou.storage.job_store import JobStore
from jiandou.pipeline.task import Task, TaskStatus


class TestJobStore:
    @pytest.fixture
    def store(self):
        """Create a JobStore backed by a temp file for true isolation."""
        tmp = tempfile.mktemp(suffix=".db")
        s = JobStore(tmp)
        yield s
        # Cleanup
        try:
            Path(tmp).unlink(missing_ok=True)
        except Exception:
            pass

    def test_save_and_get(self, store):
        task = Task(mode="t2v", prompt="test")
        store.save(task)

        loaded = store.get(task.id)
        assert loaded is not None
        assert loaded.id == task.id
        assert loaded.prompt == "test"
        assert loaded.mode.value == "t2v"

    def test_list_empty(self, store):
        tasks = store.list()
        assert len(tasks) == 0

    def test_list_with_tasks(self, store):
        for i in range(5):
            task = Task(mode="t2v", prompt=f"test-{i}")
            store.save(task)

        tasks = store.list(limit=10)
        assert len(tasks) == 5

    def test_list_with_filter(self, store):
        t1 = Task(mode="t2v", prompt="test-1")
        t1.status = TaskStatus.DONE
        store.save(t1)

        t2 = Task(mode="t2v", prompt="test-2")
        t2.status = TaskStatus.FAILED
        store.save(t2)

        done_tasks = store.list(status="done")
        assert len(done_tasks) == 1
        assert done_tasks[0].prompt == "test-1"

        failed_tasks = store.list(status="failed")
        assert len(failed_tasks) == 1

    def test_update_progress(self, store):
        task = Task(mode="t2v", steps=8)
        store.save(task)

        store.update_progress(task.id, 0.5, 4, 8, 30.0)
        loaded = store.get(task.id)
        assert loaded.progress == 0.5
        assert loaded.current_step == 4
        assert loaded.total_steps == 8
        assert loaded.eta_seconds == 30.0

    def test_update_status(self, store):
        task = Task(mode="t2v")
        store.save(task)

        store.update_status(task.id, TaskStatus.RUNNING)
        loaded = store.get(task.id)
        assert loaded.status == TaskStatus.RUNNING
        assert loaded.started_at is not None

        store.update_status(task.id, TaskStatus.DONE)
        loaded = store.get(task.id)
        assert loaded.status == TaskStatus.DONE

    def test_update_status_with_string(self, store):
        task = Task(mode="t2v")
        store.save(task)
        store.update_status(task.id, "done")
        loaded = store.get(task.id)
        assert loaded.status == TaskStatus.DONE

    def test_delete(self, store):
        task = Task(mode="t2v")
        store.save(task)
        assert store.delete(task.id) is True
        assert store.get(task.id) is None
        assert store.delete("nonexistent") is False

    def test_count(self, store):
        assert store.count() == 0
        for _ in range(3):
            store.save(Task(mode="t2v"))
        assert store.count() == 3

        store.update_status(store.list()[0].id, TaskStatus.DONE)
        assert store.count(status="done") == 1

    def test_cleanup_stale(self, store):
        task = Task(mode="t2v")
        task.status = TaskStatus.DONE
        store.save(task)
        store.update_status(task.id, TaskStatus.DONE)

        # Cleanup with 0 hours (immediately)
        count = store.cleanup_stale(0)
        assert count == 1
        assert store.get(task.id) is None

    def test_get_next_pending(self, store):
        t1 = Task(mode="t2v", priority=0)
        t2 = Task(mode="t2v", priority=10)
        store.save(t1)
        store.save(t2)

        next_task = store.get_next_pending()
        assert next_task is not None
        assert next_task.priority == 10  # Higher priority first

    def test_persistence(self, store):
        task = Task(mode="t2v", prompt="persistence test")
        store.save(task)

        # Simulate re-opening
        store2 = JobStore(str(store.db_path))
        loaded = store2.get(task.id)
        assert loaded is not None
        assert loaded.prompt == "persistence test"
