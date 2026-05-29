"""权重文件版本检测 — 从 safetensors 文件头检测模型版本和配置。

支持：
- LTX 2.0 vs 2.3 版本检测
- 从 safetensors metadata 读取 model_version / config
- 多模型共存（distilled/dev/fp8/upscaler）识别
"""

import json
import struct
from pathlib import Path
from typing import Optional


class VersionDetectionError(RuntimeError):
    """版本检测错误。"""


def detect_model_version(checkpoint_path: str) -> str:
    """从 safetensors 文件检测模型版本。

    Args:
        checkpoint_path: .safetensors 文件的路径

    Returns:
        "2.0" 或 "2.3"

    Raises:
        VersionDetectionError: 无法检测版本时抛出
    """
    if not Path(checkpoint_path).exists():
        raise VersionDetectionError(f"Checkpoint not found: {checkpoint_path}")

    try:
        metadata = _read_safetensors_metadata(checkpoint_path)
    except Exception as e:
        raise VersionDetectionError(f"Failed to read safetensors metadata: {e}") from e

    # Direct version field
    if "model_version" in metadata:
        return metadata["model_version"]

    # Config-based detection
    if "__metadata__" in metadata:
        config = metadata["__metadata__"]
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError:
                pass
        if isinstance(config, dict):
            if config.get("model_version"):
                return config["model_version"]
            # LTX 2.3 indicators
            if config.get("_name_or_path", "").startswith("Lightricks/LTX-2.3"):
                return "2.3"
            if config.get("cross_attention_adaln") is True:
                return "2.3"
            if config.get("use_middle_indices_grid") is True:
                return "2.3"

    # Heuristic: check for AV text encoder weights (2.3 only)
    for key in metadata.get("__metadata__", {}):
        if "audio" in str(key).lower():
            return "2.3"

    # Fallback to key name inspection
    for tensor_name in metadata:
        if tensor_name.startswith("__"):
            continue
        if "audio_embeddings_connector" in tensor_name:
            return "2.3"

    return "2.0"


def is_v2_model(checkpoint_path: str) -> bool:
    """是否 LTX 2.3 及以上版本。"""
    version = detect_model_version(checkpoint_path)
    parts = version.split(".")
    if len(parts) >= 2:
        return int(parts[0]) >= 2 and int(parts[1]) >= 3
    return False


def detect_model_type(checkpoint_path: str) -> str:
    """检测模型类型（transformer / text_encoder / upscaler / vae）。

    通过分析 safetensors 中的张量名称模式判断。
    """
    if not Path(checkpoint_path).exists():
        raise VersionDetectionError(f"Checkpoint not found: {checkpoint_path}")

    metadata = _read_safetensors_metadata(checkpoint_path)

    tensor_names = [k for k in metadata if not k.startswith("__")]
    first_keys = tensor_names[:20]

    key_prefixes = {k.split(".")[0] for k in first_keys}

    # VAE has specific prefixes
    if "encoder" in key_prefixes or "decoder" in key_prefixes:
        return "vae"

    # Text encoder has specific prefixes
    if "feature_extractor" in key_prefixes or "embeddings_connector" in key_prefixes:
        return "text_encoder"

    # Upscaler patterns
    if any("upscale" in k.lower() for k in first_keys):
        return "upscaler"

    # Default: transformer (has transformer blocks, attention, etc.)
    return "transformer"


def get_checkpoint_info(checkpoint_path: str) -> dict:
    """获取 checkpoint 的完整信息。"""
    size = Path(checkpoint_path).stat().st_size
    try:
        version = detect_model_version(checkpoint_path)
    except VersionDetectionError:
        version = "unknown"
    try:
        model_type = detect_model_type(checkpoint_path)
    except VersionDetectionError:
        model_type = "unknown"

    metadata = _read_safetensors_metadata(checkpoint_path)
    config = {}
    if "__metadata__" in metadata:
        raw = metadata["__metadata__"]
        if isinstance(raw, str):
            try:
                config = json.loads(raw)
            except json.JSONDecodeError:
                config = {"raw": raw[:500]}
        elif isinstance(raw, dict):
            config = raw

    tensor_count = len([k for k in metadata if not k.startswith("__")])

    return {
        "path": checkpoint_path,
        "size_bytes": size,
        "size_gb": round(size / 1024**3, 2),
        "version": version,
        "model_type": model_type,
        "tensor_count": tensor_count,
        "config": config,
    }


def scan_checkpoints(directory: str) -> list[dict]:
    """扫描目录下所有 safetensors 文件并返回信息。"""
    results = []
    for p in Path(directory).rglob("*.safetensors"):
        try:
            info = get_checkpoint_info(str(p))
            results.append(info)
        except VersionDetectionError:
            results.append({"path": str(p), "error": "detection_failed"})
    return results


# ── internal ──────────────────────────────────────────────────────────

def _read_safetensors_metadata(path: str) -> dict:
    """读取 safetensors 文件的 header（JSON metadata section）。

    Safetensors 格式：[8 bytes header_size (u64 LE)] [header JSON]
    """
    with open(path, "rb") as f:
        header_size_bytes = f.read(8)
        if len(header_size_bytes) < 8:
            raise VersionDetectionError("File too small to be valid safetensors")

        header_size = struct.unpack("<Q", header_size_bytes)[0]
        header_json = f.read(header_size)
        if len(header_json) < header_size:
            raise VersionDetectionError("Truncated safetensors header")

        return json.loads(header_json.decode("utf-8"))


def validate_checkpoint(checkpoint_path: str) -> bool:
    """验证 safetensors 文件完整性（基础结构检查）。"""
    try:
        metadata = _read_safetensors_metadata(checkpoint_path)
        # Must have tensor entries
        tensors = [k for k in metadata if not k.startswith("__")]
        return len(tensors) > 0
    except Exception:
        return False
