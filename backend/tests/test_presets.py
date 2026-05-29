"""Tests for parameter presets."""

import pytest
from jiandou.pipeline.presets import (
    PRESETS,
    PresetParams,
    apply_preset,
    get_preset,
    list_presets,
    load_preset_from_yaml,
)
from jiandou.pipeline.task import Task


class TestPresets:
    def test_all_presets_defined(self):
        assert "fast" in PRESETS
        assert "balanced" in PRESETS
        assert "quality" in PRESETS

    def test_get_preset(self):
        fast = get_preset("fast")
        assert fast is not None
        assert fast.width == 512
        assert fast.height == 288
        assert fast.steps == 4
        assert fast.pipeline == "distilled"

    def test_get_preset_nonexistent(self):
        assert get_preset("nonexistent") is None

    def test_list_presets(self):
        presets = list_presets()
        assert "fast" in presets
        assert "balanced" in presets
        assert "quality" in presets

    def test_apply_fast_preset(self):
        task = Task(mode="t2v")
        apply_preset(task, "fast")
        assert task.width == 512
        assert task.height == 288
        assert task.fps == 16
        assert task.steps == 4
        assert task.fp16 is True
        assert task.low_memory is True

    def test_apply_quality_preset(self):
        task = Task(mode="t2v")
        apply_preset(task, "quality")
        assert task.width == 1024
        assert task.steps == 12
        assert task.fp16 is False
        assert task.generate_audio is True

    def test_apply_preset_with_overrides(self):
        task = Task(mode="t2v")
        apply_preset(task, "fast", overrides={"width": 640, "steps": 6})
        assert task.width == 640  # Overridden
        assert task.height == 288  # Preset default
        assert task.steps == 6  # Overridden
        assert task.preset == "fast"

    def test_unknown_preset_keeps_task(self):
        task = Task(mode="t2v", width=999)
        apply_preset(task, "unknown")
        assert task.width == 999  # Unchanged

    def test_load_preset_from_yaml(self, tmp_path):
        yaml_content = """
generation:
  width: 640
  height: 360
  steps: 6
  duration: 3.0
engine:
  pipeline: distilled
  fp16: true
post:
  upscale: model
"""
        yaml_file = tmp_path / "custom.yaml"
        yaml_file.write_text(yaml_content)

        preset = load_preset_from_yaml(str(yaml_file))
        assert preset.width == 640
        assert preset.height == 360
        assert preset.steps == 6
        assert preset.pipeline == "distilled"
        assert preset.upscale == "model"

    def test_preset_params_apply_to(self):
        task = Task(mode="t2v")
        p = PresetParams(
            width=800, height=600, fps=30, steps=10, cfg=4.0,
            duration=8.0, pipeline="one-stage", fp16=False,
            low_memory=False, upscale="piper", upscale_factor=2.0,
            generate_audio=True, enhance=True,
        )
        p.apply_to(task)
        assert task.width == 800
        assert task.fps == 30
        assert task.cfg == 4.0
        assert task.upscale == "piper"
