"""参数预设系统 — Fast / Balanced / Quality 三层预设。

支持：
- 预设定义（分辨率/步数/帧率/超分）
- 预设合并（用户覆盖参数 + 预设默认值）
- 从 YAML 文件加载自定义预设
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from jiandou.pipeline.task import PresetName, Task


@dataclass
class PresetParams:
    """单个预设的参数集。"""

    width: int
    height: int
    fps: int
    steps: int
    cfg: float
    duration: float
    pipeline: str
    fp16: bool
    low_memory: bool
    upscale: str
    upscale_factor: float
    generate_audio: bool
    enhance: bool

    def apply_to(self, task: Task):
        """将预设参数应用到 Task 对象。"""
        task.width = self.width
        task.height = self.height
        task.fps = self.fps
        task.steps = self.steps
        task.cfg = self.cfg
        task.duration = self.duration
        task.pipeline = self.pipeline
        task.fp16 = self.fp16
        task.low_memory = self.low_memory
        task.upscale = self.upscale
        task.upscale_factor = self.upscale_factor
        task.generate_audio = self.generate_audio


# ── built-in presets ──────────────────────────────────────────────────

PRESETS: dict[str, PresetParams] = {
    "fast": PresetParams(
        width=512,
        height=288,
        fps=16,
        steps=4,
        cfg=1.0,
        duration=3.0,
        pipeline="distilled",
        fp16=True,
        low_memory=True,
        upscale="none",
        upscale_factor=1.0,
        generate_audio=False,
        enhance=False,
    ),
    "balanced": PresetParams(
        width=768,
        height=512,
        fps=24,
        steps=8,
        cfg=2.0,
        duration=5.0,
        pipeline="auto",
        fp16=True,
        low_memory=False,
        upscale="none",
        upscale_factor=2.0,
        generate_audio=False,
        enhance=False,
    ),
    "quality": PresetParams(
        width=1024,
        height=576,
        fps=24,
        steps=12,
        cfg=3.0,
        duration=5.0,
        pipeline="two-stage",
        fp16=False,
        low_memory=False,
        upscale="both",
        upscale_factor=2.0,
        generate_audio=True,
        enhance=True,
    ),
}


def get_preset(name: str) -> Optional[PresetParams]:
    """获取内置预设。"""
    return PRESETS.get(name)


def list_presets() -> list[str]:
    """列出所有可用预设名称。"""
    return list(PRESETS.keys())


def apply_preset(task: Task, preset_name: str, overrides: Optional[dict] = None) -> Task:
    """将预设应用到 Task，并通过 overrides 覆盖。

    Args:
        task: 待配置的 Task
        preset_name: 预设名称 (fast/balanced/quality)
        overrides: 手动覆盖参数 dict

    Returns:
        配置后的 Task（原地修改）
    """
    preset = get_preset(preset_name)
    if preset is None:
        # Unknown preset — keep task as-is
        return task

    # Apply preset defaults
    preset.apply_to(task)
    task.preset = preset_name

    # Apply user overrides
    if overrides:
        for key, value in overrides.items():
            if hasattr(task, key):
                setattr(task, key, value)

    return task


def load_preset_from_yaml(path: str) -> PresetParams:
    """从 YAML 文件加载预设参数。"""
    with open(path) as f:
        data = yaml.safe_load(f) or {}

    gen = data.get("generation", {})
    engine = data.get("engine", {})
    post = data.get("post", {})

    return PresetParams(
        width=gen.get("width", 768),
        height=gen.get("height", 512),
        fps=gen.get("fps", 24),
        steps=gen.get("steps", 8),
        cfg=gen.get("cfg", 2.0),
        duration=gen.get("duration", 5.0),
        pipeline=engine.get("pipeline", "auto"),
        fp16=engine.get("fp16", True),
        low_memory=engine.get("low_memory", False),
        upscale=post.get("upscale", "none"),
        upscale_factor=post.get("upscale_factor", 2.0),
        generate_audio=post.get("generate_audio", False),
        enhance=post.get("enhance", False),
    )


def merge_with_hardware_tier(task: Task, tier_info) -> Task:
    """根据硬件层级限制参数。"""
    from jiandou.hardware.tier import HardwareTier

    tier = HardwareTier(tier_info) if not isinstance(tier_info, HardwareTier) else tier_info
    adjusted = tier.adjust(
        width=task.width,
        height=task.height,
        num_frames=task.num_frames,
        steps=task.steps,
        duration=task.duration,
        fp16=task.fp16,
        low_memory=task.low_memory,
        pipeline=task.pipeline,
    )
    task.width = adjusted.width
    task.height = adjusted.height
    task.fp16 = adjusted.fp16
    task.low_memory = adjusted.low_memory
    task.pipeline = adjusted.pipeline
    task.steps = adjusted.steps
    task.duration = adjusted.max_duration
    return task
