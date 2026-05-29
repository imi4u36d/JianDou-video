"""Tests for ProgressTracker."""

import time
import pytest
from jiandou.pipeline.progress import ProgressTracker, ProgressPhase, StepProgress


class TestProgressTracker:
    def test_initial_state(self):
        tracker = ProgressTracker(total_steps=8)
        assert tracker.current_step == 0
        assert tracker.total_steps == 8
        assert tracker.phase == ProgressPhase.QUEUED

    def test_set_phase(self):
        tracker = ProgressTracker(total_steps=8)
        tracker.set_phase(ProgressPhase.DENOISING, total_steps=10)
        assert tracker.phase == ProgressPhase.DENOISING
        assert tracker.total_steps == 10
        assert tracker.current_step == 0

    def test_step_progresses(self):
        tracker = ProgressTracker(total_steps=8)
        tracker.set_phase(ProgressPhase.DENOISING, total_steps=8)
        for i in range(1, 5):
            tracker.step(i)
        assert tracker.current_step == 4

    def test_compute_progress(self):
        tracker = ProgressTracker(total_steps=8)
        tracker.set_phase(ProgressPhase.DENOISING, total_steps=8)
        tracker.step(4)
        progress = tracker.compute_progress()
        # Loading (10%) + Encoding (10%) + Denoising (50% * 4/8)
        expected = 0.10 + 0.10 + 0.50 * (4 / 8)
        assert abs(progress - expected) < 0.01

    def test_compute_progress_done(self):
        tracker = ProgressTracker(total_steps=8)
        tracker.set_phase(ProgressPhase.DONE)
        assert tracker.compute_progress() == 1.0

    def test_compute_eta(self):
        tracker = ProgressTracker(total_steps=8)
        tracker.set_phase(ProgressPhase.DENOISING, total_steps=8)
        tracker.step(1)
        time.sleep(0.02)
        tracker.step(2)
        eta = tracker.compute_eta()
        assert eta is not None
        assert eta >= 0

    def test_snapshot(self):
        tracker = ProgressTracker(total_steps=8)
        tracker.set_phase(ProgressPhase.LOADING)
        tracker.step(1)
        snap = tracker.snapshot()
        assert isinstance(snap, StepProgress)
        assert snap.phase == ProgressPhase.LOADING
        assert snap.total_steps == 8
        assert snap.progress >= 0

    def test_listener_callback(self):
        events = []

        def listener(snap: StepProgress):
            events.append(snap.phase)

        tracker = ProgressTracker(total_steps=8, on_update=listener)
        tracker.set_phase(ProgressPhase.LOADING)
        tracker.set_phase(ProgressPhase.DENOISING)
        tracker.step(1)

        assert ProgressPhase.LOADING in events
        assert ProgressPhase.DENOISING in events

    def test_add_remove_listener(self):
        tracker = ProgressTracker(total_steps=8)
        events = []

        def listener(snap):
            events.append(snap)

        tracker.add_listener(listener)
        tracker.step(1)
        assert len(events) == 1

        tracker.remove_listener(listener)
        tracker.step(2)
        assert len(events) == 1  # No new events

    def test_set_preview_none(self):
        tracker = ProgressTracker(total_steps=8)
        result = tracker.set_preview(None)
        assert result is None
