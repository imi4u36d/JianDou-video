"""HuggingFace model download via CLI with hf_transfer acceleration."""

import asyncio
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import huggingface_hub


@dataclass
class DownloadProgress:
    filename: str
    downloaded_bytes: int = 0
    total_bytes: int = 0
    progress: float = 0.0
    speed_mbps: float = 0.0
    eta_seconds: Optional[float] = None


@dataclass
class ModelDownloadSpec:
    repo: str
    filename: str
    revision: str = "main"
    allow_patterns: list[str] = field(default_factory=list)


class DownloadManager:
    def __init__(
        self,
        max_concurrent: int = 2,
        cache_dir: Optional[str] = None,
        hf_endpoint: Optional[str] = None,
    ):
        self.max_concurrent = max_concurrent
        self.hf_endpoint = hf_endpoint

        if hf_endpoint and "HF_ENDPOINT" not in os.environ:
            os.environ["HF_ENDPOINT"] = hf_endpoint

        if cache_dir:
            os.environ["HF_HUB_CACHE"] = cache_dir

        self._pool = ThreadPoolExecutor(max_workers=max_concurrent)
        self._active: dict[str, DownloadProgress] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def download(
        self,
        spec: ModelDownloadSpec,
        on_progress: Optional[Callable[[DownloadProgress], None]] = None,
        force: bool = False,
    ) -> Path:
        async with self._semaphore:
            return await asyncio.get_event_loop().run_in_executor(
                self._pool,
                self._download_sync,
                spec,
                on_progress,
                force,
            )

    def _download_sync(
        self,
        spec: ModelDownloadSpec,
        on_progress: Optional[Callable[[DownloadProgress], None]] = None,
        force: bool = False,
    ) -> Path:
        cmd = ["hf", "download", spec.repo, "--revision", spec.revision, "--quiet"]

        if spec.filename == "*" or spec.allow_patterns:
            for pattern in (spec.allow_patterns or ["*"]):
                cmd.extend(["--include", pattern])
        else:
            cmd.append(spec.filename)

        if force:
            cmd.append("--force-download")

        env = os.environ.copy()
        env["HF_XET_HIGH_PERFORMANCE"] = "1"

        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"hf download failed (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )

        # Last non-empty line is the path to the downloaded file/directory
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        if not lines:
            raise RuntimeError("hf download produced no output path")
        return Path(lines[-1])

    async def download_with_progress(
        self,
        spec: ModelDownloadSpec,
        on_progress: Optional[Callable[[DownloadProgress], None]] = None,
    ) -> Path:
        self._active[spec.filename] = DownloadProgress(
            filename=spec.filename,
        )
        path = await self.download(spec, on_progress)
        self._active.pop(spec.filename, None)
        return path

    @staticmethod
    def list_available(repo: str, revision: str = "main") -> list[str]:
        try:
            files = huggingface_hub.list_repo_files(repo, revision=revision)
            return [f for f in files if f.endswith(".safetensors")]
        except Exception:
            return []

    @staticmethod
    def get_file_size(repo: str, filename: str, revision: str = "main") -> int:
        try:
            info = huggingface_hub.get_paths_info(repo, filename, revision=revision)
            return info[0].size if info else 0
        except Exception:
            return 0

    @staticmethod
    def get_default_weights() -> list[ModelDownloadSpec]:
        return [
            ModelDownloadSpec(
                repo="Lightricks/LTX-2",
                filename="ltx-2-19b-distilled.safetensors",
            ),
            ModelDownloadSpec(
                repo="Lightricks/LTX-2",
                filename="text_encoder/diffusion_pytorch_model-00001-of-00012.safetensors",
            ),
            ModelDownloadSpec(
                repo="google/gemma-3-12b-it",
                filename="*",
                allow_patterns=["*.safetensors", "tokenizer.model", "*.json"],
            ),
        ]

