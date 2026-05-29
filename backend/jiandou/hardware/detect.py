"""Apple Silicon 硬件检测。

检测芯片型号、内存容量、GPU 核心数，并提供硬件层级自动判断。
"""

import os
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class SystemInfo:
    """系统硬件信息。"""

    chip: str = "Unknown"
    cpu_cores: int = 0
    gpu_cores: int = 0
    ram_gb: int = 0
    ram_free_gb: int = 0
    tier: str = "medium"  # low | medium | high | ultra
    max_resolution: tuple = (768, 512)
    max_frames: int = 121
    supports_fp16: bool = True
    supports_audio: bool = True
    ffmpeg_available: bool = False
    macos_version: str = ""
    mlx_version: str = ""


def detect_system_info() -> SystemInfo:
    """检测当前系统的硬件信息。"""
    info = SystemInfo()

    # Chip detection
    info.chip = _detect_chip()

    # CPU cores
    info.cpu_cores = os.cpu_count() or 0

    # RAM
    info.ram_gb = _detect_ram_gb()
    info.ram_free_gb = _detect_free_ram_gb()

    # GPU cores (from chip name)
    info.gpu_cores = _detect_gpu_cores(info.chip)

    # Tier
    info.tier = _determine_tier(info)

    # ffmpeg
    info.ffmpeg_available = _check_ffmpeg()

    # macOS version
    info.macos_version = _detect_macos_version()

    # MLX version
    info.mlx_version = _detect_mlx_version()

    # Capability tuning
    info.supports_fp16 = info.chip != "M1"  # M1 FP16 问题较多
    info.supports_audio = info.ram_gb >= 32  # Audio generation needs more RAM

    # Auto-adjust based on tier
    info.max_resolution = _tier_max_resolution(info.tier)
    info.max_frames = _tier_max_frames(info.tier)

    return info


# ── internal detectors ────────────────────────────────────────────────


def _detect_chip() -> str:
    """检测 Apple Silicon 芯片型号。"""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            brand = result.stdout.strip()
            # e.g. "Apple M4 Max" -> extract chip model
            if "Apple" in brand:
                return brand.replace("Apple ", "")
    except Exception:
        pass

    # Fallback to uname
    try:
        result = subprocess.run(
            ["uname", "-m"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            arch = result.stdout.strip()
            if arch == "arm64":
                return "Apple Silicon"
    except Exception:
        pass

    return "Unknown"


def _detect_gpu_cores(chip: str) -> int:
    """根据芯片名称推测 GPU 核心数。"""
    # Ordered longest-first so "M1 Max" matches before "M1"
    gpu_map = [
        ("M5 Ultra", 80), ("M4 Ultra", 80), ("M3 Ultra", 80), ("M2 Ultra", 76), ("M1 Ultra", 64),
        ("M5 Max", 40), ("M4 Max", 40), ("M3 Max", 40), ("M2 Max", 38), ("M1 Max", 32),
        ("M5 Pro", 20), ("M4 Pro", 20), ("M3 Pro", 18), ("M2 Pro", 19), ("M1 Pro", 16),
        ("M5", 10), ("M4", 10), ("M3", 10), ("M2", 10), ("M1", 7),
    ]
    for key, count in gpu_map:
        if key in chip:
            return count
    return 0


def _detect_ram_gb() -> int:
    """检测总内存（GB）。"""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return int(int(result.stdout.strip()) / 1024**3)
    except Exception:
        pass
    return 0


def _detect_free_ram_gb() -> int:
    """检测可用内存（GB），使用 vm_stat。"""
    try:
        result = subprocess.run(
            ["vm_stat"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            page_size = 16384  # Apple Silicon 默认 16KB pages
            for line in result.stdout.splitlines():
                if "Pages free" in line:
                    free_pages = int(line.split(":")[-1].strip().rstrip("."))
                    return (free_pages * page_size) // 1024**3
    except Exception:
        pass
    return 0


def _determine_tier(info: SystemInfo) -> str:
    """根据硬件自动确定层级。"""
    ram = info.ram_gb
    gpu = info.gpu_cores
    chip_family = info.chip

    # Ultra chips -> always ultra
    if "Ultra" in chip_family:
        return "ultra"

    # Max chips with 96GB+ RAM -> ultra
    if "Max" in chip_family and ram >= 96:
        return "ultra"

    # Max chips with 48GB+ RAM -> high
    if "Max" in chip_family and ram >= 48:
        return "high"

    # Max chips with less RAM -> medium
    if "Max" in chip_family:
        return "medium"

    # Pro chips with 48GB+ -> high
    if "Pro" in chip_family and ram >= 48:
        return "high"

    # Pro with 24GB+ -> medium
    if "Pro" in chip_family and ram >= 24:
        return "medium"

    # Base M3/M4/M5 with 24GB+ -> medium
    if ram >= 24:
        return "medium"

    # Everything else -> low
    if ram < 16:
        return "low"

    return "medium"


def _tier_max_resolution(tier: str) -> tuple:
    """根据层级返回最大分辨率。"""
    return {
        "low": (512, 288),
        "medium": (768, 512),
        "high": (1024, 576),
        "ultra": (1280, 720),
    }.get(tier, (768, 512))


def _tier_max_frames(tier: str) -> int:
    """根据层级返回最大帧数。"""
    return {
        "low": 49,
        "medium": 121,
        "high": 193,
        "ultra": 241,
    }.get(tier, 121)


def _check_ffmpeg() -> bool:
    """检查 ffmpeg 是否可用。"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def _detect_macos_version() -> str:
    """检测 macOS 版本。"""
    try:
        result = subprocess.run(
            ["sw_vers", "-productVersion"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _detect_mlx_version() -> str:
    """检测 MLX 版本。"""
    try:
        from importlib.metadata import version
        return version("mlx")
    except Exception:
        try:
            import mlx.core
            return getattr(mlx.core, "__version__", "unknown")
        except ImportError:
            return "not installed"


# ── quick checks ──────────────────────────────────────────────────────


def meets_minimum() -> bool:
    """检查是否满足最低要求（macOS 14+, Apple Silicon, 16GB+）。"""
    info = detect_system_info()
    return (
        info.ram_gb >= 16
        and info.chip != "Unknown"
        and info.macos_version >= "14.0"
    )


def recommended_workers(info: Optional[SystemInfo] = None) -> int:
    """根据硬件推荐并发 worker 数。"""
    if info is None:
        info = detect_system_info()
    # Each worker needs ~30GB for full model + ~25GB for Gemma
    # Conservative: max_workers = ram_gb // 55
    max_by_ram = max(1, info.ram_gb // 55)
    # Also limit by GPU cores
    max_by_gpu = max(1, info.gpu_cores // 16)
    return min(max_by_ram, max_by_gpu)
