"""Tests for Task data model."""

import pytest
from jiandou.pipeline.task import Task, TaskMode, TaskStatus


class TestTask:
    def test_create_default_task(self):
        task = Task(mode="t2v", prompt="test")
        assert task.mode == TaskMode.T2V
        assert task.prompt == "test"
        assert task.status == TaskStatus.PENDING
        assert len(task.id) == 36  # UUID format

    def test_task_num_frames(self):
        task = Task(mode="t2v", duration=5.0, fps=24)
        assert task.num_frames == 121  # 5*24 + 1

        task.duration = 3.0
        task.fps = 16
        assert task.num_frames == 49  # 3*16 + 1

    def test_task_terminal_status(self):
        task = Task(mode="t2v")
        assert not task.is_terminal

        task.status = TaskStatus.DONE
        assert task.is_terminal

        task.status = TaskStatus.FAILED
        assert task.is_terminal

        task.status = TaskStatus.CANCELLED
        assert task.is_terminal

    def test_task_to_dict_roundtrip(self):
        task = Task(
            mode="i2v",
            prompt="beautiful sunset",
            width=1024,
            height=576,
            steps=12,
            cfg=3.0,
            seed=42,
            preset="quality",
            fp16=False,
        )
        d = task.to_dict()
        assert d["mode"] == "i2v"
        assert d["width"] == 1024
        assert d["steps"] == 12
        assert d["seed"] == 42

        task2 = Task.from_dict(d)
        assert task2.mode == task.mode
        assert task2.prompt == task.prompt
        assert task2.width == task.width
        assert task2.steps == task.steps
        assert task2.preset == "quality"

    def test_task_elapsed_time(self):
        from datetime import datetime, timedelta

        task = Task(mode="t2v")
        assert task.elapsed_seconds is None

        task.started_at = datetime.now() - timedelta(seconds=10)
        assert task.elapsed_seconds is not None
        assert 9 <= task.elapsed_seconds <= 11

    def test_all_task_modes(self):
        for mode in TaskMode:
            task = Task(mode=mode)
            assert task.mode == mode

    def test_task_priority(self):
        task = Task(mode="t2v", priority=5)
        assert task.priority == 5

        task2 = Task(mode="t2v", priority=0)
        assert task2.priority == 0
