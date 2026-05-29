"""硬件层级参数自动调整。

根据 SystemInfo.tier 自动适配生成参数（分辨率、步数、精度等）。
"""

from dataclasses import dataclass
from typing import Optional

from jiandou.hardware.detect import SystemInfo, detect_system_info

# Tier-specific parameter presets
# Values are multipliers applied to the base "balanced" config

TIER_PARAMS = {
    "low": {
        "max_resolution": (512, 288),
        "max_frames": 49,
        "default_steps": 4,
        "fp16": True,
        "low_memory": True,
        "pipeline": "distilled",
        "max_duration": 3.0,
        "max_workers": 1,
    },
    "medium": {
        "max_resolution": (768, 512),
        "max_frames": 121,
        "default_steps": 8,
        "fp16": True,
        "low_memory": False,
        "pipeline": "auto",
        "max_duration": 5.0,
        "max_workers": 1,
    },
    "high": {
        "max_resolution": (1024, 576),
        "max_frames": 193,
        "default_steps": 12,
        "fp16": False,
        "low_memory": False,
        "pipeline": "auto",
        "max_duration": 10.0,
        "max_workers": 2,
    },
    "ultra": {
        "max_resolution": (1280, 720),
        "max_frames": 241,
        "default_steps": 16,
        "fp16": False,
        "low_memory": False,
        "pipeline": "two-stage",
        "max_duration": 15.0,
        "max_workers": 3,
    },
}


@dataclass
class TierAdjustedParams:
    """经过硬件层级调整的生成参数。"""

    width: int
    height: int
    num_frames: int
    steps: int
    fp16: bool
    low_memory: bool
    pipeline: str
    max_duration: float
    max_workers: int


class HardwareTier:
    """硬件层级参数调整器。"""

    def __init__(self, info: Optional[SystemInfo] = None):
        self.info = info or detect_system_info()
        self._params = TIER_PARAMS.get(self.info.tier, TIER_PARAMS["medium"])

    @property
    def tier(self) -> str:
        return self.info.tier

    def clamp_resolution(self, width: int, height: int) -> tuple[int, int]:
        """将分辨率限制在硬件支持的最大值内。"""
        max_w, max_h = self._params["max_resolution"]
        return min(width, max_w), min(height, max_h)

    def clamp_frames(self, num_frames: int) -> int:
        """将帧数限制在硬件支持的最大值内。"""
        return min(num_frames, self._params["max_frames"])

    def clamp_duration(self, duration: float) -> float:
        """将时长限制在硬件支持的最大值内。"""
        return min(duration, self._params["max_duration"])

    def recommended_steps(self, requested: Optional[int] = None) -> int:
        """返回推荐的推理步数。"""
        if requested is not None:
            return min(requested, self._params["default_steps"] * 2)
        return self._params["default_steps"]

    def should_use_fp16(self) -> bool:
        return self._params["fp16"]

    def should_use_low_memory(self) -> bool:
        return self._params["low_memory"]

    def recommended_pipeline(self, requested: str = "auto") -> str:
        """推荐 pipeline 类型，不能超过硬件能力。"""
        if requested != "auto":
            # Don't override explicit user choice
            return requested
        return self._params["pipeline"]

    def max_workers(self) -> int:
        return self._params["max_workers"]

    def adjust(
        self,
        width: int = 768,
        height: int = 512,
        num_frames: int = 121,
        steps: int = 8,
        duration: float = 5.0,
        fp16: bool = True,
        low_memory: bool = False,
        pipeline: str = "auto",
    ) -> TierAdjustedParams:
        """一站式调整所有参数到硬件能力范围内。"""
        w, h = self.clamp_resolution(width, height)
        return TierAdjustedParams(
            width=w,
            height=h,
            num_frames=self.clamp_frames(num_frames),
            steps=self.recommended_steps(steps),
            fp16=fp16 if not fp16 else self.should_use_fp16(),
            low_memory=low_memory or self.should_use_low_memory(),
            pipeline=self.recommended_pipeline(pipeline),
            max_duration=self.clamp_duration(duration),
            max_workers=self.max_workers(),
        )

    def get_summary(self) -> str:
        """获取可读的硬件层级摘要。"""
        lines = [
            f"Tier: {self.tier.upper()}",
            f"  Chip:        {self.info.chip}",
            f"  RAM:         {self.info.ram_gb} GB (free: {self.info.ram_free_gb} GB)",
            f"  GPU Cores:   {self.info.gpu_cores}",
            f"  Max Res:     {self._params['max_resolution'][0]}x{self._params['max_resolution'][1]}",
            f"  Max Frames:  {self._params['max_frames']}",
            f"  Max Workers: {self._params['max_workers']}",
            f"  Pipeline:    {self._params['pipeline']}",
            f"  FP16:        {self._params['fp16']}",
        ]
        return "\n".join(lines)
