"""用户配置管理 — YAML + pydantic-settings，环境变量覆盖。"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 6701
    cors_origins: list[str] = ["*"]
    static_dir: str = "../frontend/dist"


class EngineConfig(BaseSettings):
    model_version: str = "2.3"
    pipeline: str = "auto"
    fp16: bool = True
    low_memory: bool = False


class QueueConfig(BaseSettings):
    max_workers: int = 1
    task_timeout: int = 3600
    idle_timeout: int = 300
    resident_mode: bool = False


class GenerationConfig(BaseSettings):
    duration: float = 5.0
    width: int = 768
    height: int = 512
    fps: int = 24
    steps: int = 8
    cfg: float = 2.0
    seed: int = -1
    preset: str = "balanced"


class PostConfig(BaseSettings):
    upscale: str = "none"
    upscale_factor: float = 2.0
    generate_audio: bool = False
    enhance: bool = False


class ModelsConfig(BaseSettings):
    cache_dir: str = "~/.jiandou/models/video"
    registries: list[dict] = []
    hf_endpoint: str = "https://hf-mirror.com"
    hf_max_concurrent: int = 6


class PathsConfig(BaseSettings):
    outputs: str = "./outputs"
    logs: str = "./logs"


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JIAN_DOU_",
        env_nested_delimiter="__",
        yaml_file=None,
        extra="ignore",
    )

    server: ServerConfig = Field(default_factory=ServerConfig)
    engine: EngineConfig = Field(default_factory=EngineConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    post: PostConfig = Field(default_factory=PostConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML files with env override.

    Priority: env vars > config_path > presets/default.yaml > defaults
    """
    config_dir = Path(__file__).parent.parent.parent.parent.parent / "config"
    if not config_dir.exists():
        config_dir = Path("config")

    merged: dict = {}

    # 1. Load default.yaml
    default_path = config_dir / "default.yaml"
    if default_path.exists():
        with open(default_path) as f:
            merged.update(yaml.safe_load(f) or {})

    # 2. Load preset overlay (generation.preset field may point to a preset file)
    preset = merged.get("generation", {}).get("preset", "balanced")
    preset_path = config_dir / "presets" / f"{preset}.yaml"
    if preset_path.exists():
        with open(preset_path) as f:
            preset_data = yaml.safe_load(f) or {}
            _deep_merge(merged, preset_data)

    # 3. Load explicit config file
    if config_path:
        with open(config_path) as f:
            explicit_data = yaml.safe_load(f) or {}
            _deep_merge(merged, explicit_data)

    # 4. Build pydantic model (env vars will be applied by pydantic-settings)
    return AppConfig(**merged)


def _deep_merge(base: dict, overlay: dict) -> None:
    """Merge overlay into base in-place, recursively."""
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
