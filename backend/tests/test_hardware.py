"""Tests for hardware detection."""

import pytest
from jiandou.hardware.detect import (
    SystemInfo,
    detect_system_info,
    meets_minimum,
    recommended_workers,
)
from jiandou.hardware.tier import HardwareTier, TierAdjustedParams


class TestHardwareDetection:
    def test_detect_system_info(self):
        info = detect_system_info()
        assert isinstance(info, SystemInfo)
        assert info.chip != "Unknown"
        assert info.ram_gb > 0
        assert info.cpu_cores > 0
        assert info.tier in ("low", "medium", "high", "ultra")
        assert isinstance(info.ffmpeg_available, bool)
        assert info.macos_version != ""

    def test_meets_minimum(self):
        assert meets_minimum() is True  # On Apple Silicon with 16GB+

    def test_recommended_workers(self):
        workers = recommended_workers()
        assert workers >= 1
        assert workers <= 4

    def test_system_info_fields(self):
        info = detect_system_info()
        assert isinstance(info.ram_gb, int)
        assert isinstance(info.gpu_cores, int)
        assert len(info.max_resolution) == 2
        assert info.max_frames >= 49


class TestHardwareTier:
    @pytest.fixture
    def system_info(self):
        return detect_system_info()

    def test_tier_creation(self, system_info):
        tier = HardwareTier(system_info)
        assert tier.tier in ("low", "medium", "high", "ultra")

    def test_clamp_resolution(self, system_info):
        tier = HardwareTier(system_info)
        w, h = tier.clamp_resolution(9999, 9999)
        assert w <= 1280
        assert h <= 720

    def test_clamp_frames(self, system_info):
        tier = HardwareTier(system_info)
        assert tier.clamp_frames(9999) <= 241

    def test_recommended_steps(self, system_info):
        tier = HardwareTier(system_info)
        steps = tier.recommended_steps()
        assert steps >= 4
        assert steps <= 16

    def test_adjust(self, system_info):
        tier = HardwareTier(system_info)
        adjusted = tier.adjust(
            width=2048, height=1024,
            num_frames=999,
            steps=50,
            duration=99.0,
        )
        assert isinstance(adjusted, TierAdjustedParams)
        assert adjusted.width <= 1280
        assert adjusted.height <= 720
        assert adjusted.num_frames <= 241

    def test_get_summary(self, system_info):
        tier = HardwareTier(system_info)
        summary = tier.get_summary()
        assert "Tier:" in summary
        assert system_info.chip in summary
