"""GET / POST /api/v1/models — 模型管理。"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from jiandou.api.deps import get_download_manager, get_model_registry
from jiandou.api.schemas import (
    ErrorResponse,
    ModelDownloadProgressResponse,
    ModelDownloadRequest,
    ModelEntryResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Models"])

import threading

# Track active downloads: name -> progress
_downloads: dict[str, dict] = {}
_cancel_events: dict[str, threading.Event] = {}
_download_slots = threading.Semaphore(3)  # Max 3 concurrent downloads


@router.get("/models", response_model=list[ModelEntryResponse])
async def list_models(registry=Depends(get_model_registry)):
    """获取已下载的模型列表。"""
    entries = registry.list_all()
    return [
        ModelEntryResponse(
            name=e.name,
            repo=e.repo,
            filename=e.filename,
            local_path=e.local_path,
            size_bytes=e.size_bytes,
            version=e.version,
            model_type=e.model_type,
            downloaded=e.downloaded,
            downloaded_at=e.downloaded_at.isoformat() if e.downloaded_at else None,
            sha256=e.sha256,
        )
        for e in entries
    ]


@router.get("/models/available")
async def list_available_models(
    repo: str = "Lightricks/LTX-2",
    dm=Depends(get_download_manager),
):
    """列出 HuggingFace 仓库中可用的模型文件。"""
    files = dm.list_available(repo)
    return {"repo": repo, "files": files}


@router.get("/models/recommended")
async def recommended_models(dm=Depends(get_download_manager)):
    """返回按类别组织的推荐模型，每类列出推荐选项和备选。"""
    from jiandou.hardware.detect import detect_system_info

    sys_info = detect_system_info()
    tier = sys_info.tier
    ram_gb = sys_info.ram_gb

    all_files = set(dm.list_available("Lightricks/LTX-2"))

    def in_repo(name: str) -> bool:
        return name in all_files

    def has_all(names: list[str]) -> bool:
        return all(f in all_files for f in names)

    # Helper: sharded option
    def shard_option(prefix: str, count: int) -> list[str]:
        return [prefix + f"{i:05d}-of-{count:05d}.safetensors" for i in range(1, count + 1)]

    categories: list[dict] = []

    # ── 1. 主模型 (Transformer) ──
    transformer_options: list[dict] = []

    # Distilled single file (recommended for everyone)
    if in_repo("ltx-2-19b-distilled.safetensors"):
        transformer_options.append({
            "label": "蒸馏版 (单文件)",
            "files": ["ltx-2-19b-distilled.safetensors"],
            "recommended": True,
            "desc": "推荐 · 推理步数少速度快，质量接近完整版",
        })
    # Dev single file
    if in_repo("ltx-2-19b-dev.safetensors"):
        transformer_options.append({
            "label": "完整版 (单文件)",
            "files": ["ltx-2-19b-dev.safetensors"],
            "recommended": False,
            "desc": "完整参数模型，质量最高但推理较慢",
        })
    # Sharded version
    sharded = shard_option("transformer/diffusion_pytorch_model-", 8)
    if has_all(sharded):
        transformer_options.append({
            "label": "完整版 (分片, 8 文件)",
            "files": sharded,
            "recommended": False,
            "desc": "与完整版相同参数，分片便于断点续传",
        })
    # Quantized options for low-RAM systems
    if in_repo("ltx-2-19b-distilled-fp8.safetensors") and ram_gb < 32:
        transformer_options.append({
            "label": "蒸馏 FP8 (量化)",
            "files": ["ltx-2-19b-distilled-fp8.safetensors"],
            "recommended": False,
            "desc": "8-bit 量化，内存占用减半，轻微质量损失",
        })
    if in_repo("ltx-2-19b-dev-fp8.safetensors") and ram_gb < 32:
        transformer_options.append({
            "label": "完整版 FP8 (量化)",
            "files": ["ltx-2-19b-dev-fp8.safetensors"],
            "recommended": False,
            "desc": "完整模型 FP8 量化，低内存设备适用",
        })
    if in_repo("ltx-2-19b-dev-fp4.safetensors") and ram_gb < 16:
        transformer_options.append({
            "label": "完整版 FP4 (极致压缩)",
            "files": ["ltx-2-19b-dev-fp4.safetensors"],
            "recommended": False,
            "desc": "4-bit 量化，仅限内存 < 16GB 设备",
        })

    categories.append({
        "id": "transformer",
        "name": "主模型",
        "desc": "视频生成的核心 Transformer，必选一项",
        "required": True,
        "options": transformer_options,
    })

    # ── 2. VAE ──
    vae_options: list[dict] = []
    if in_repo("vae/diffusion_pytorch_model.safetensors"):
        vae_options.append({
            "label": "VAE 编解码器",
            "files": ["vae/diffusion_pytorch_model.safetensors"],
            "recommended": True,
            "desc": "唯一可用版本，将视频压缩到潜空间并还原",
        })
    categories.append({
        "id": "vae",
        "name": "VAE 编解码器",
        "desc": "视频 ↔ 潜空间转换，必选",
        "required": True,
        "options": vae_options,
    })

    # ── 3. 文本编码器 ──
    te_diffusion = shard_option("text_encoder/diffusion_pytorch_model-", 12)
    te_raw = shard_option("text_encoder/model-", 11)

    te_options: list[dict] = []
    if has_all(te_diffusion):
        te_options.append({
            "label": "Diffusion 格式 (12 分片)",
            "files": te_diffusion,
            "recommended": True,
            "desc": "推荐 · Diffusers 标准格式，兼容性最好",
        })
    if has_all(te_raw):
        te_options.append({
            "label": "原生格式 (11 分片)",
            "files": te_raw,
            "recommended": False,
            "desc": "原始模型格式，部分框架需要",
        })

    categories.append({
        "id": "text_encoder",
        "name": "文本编码器",
        "desc": "将提示词转为特征向量，必选一种格式",
        "required": True,
        "options": te_options,
    })

    # ── 4. 音频 ──
    if tier in ("ultra", "high"):
        audio_opts: list[dict] = []
        if in_repo("audio_vae/diffusion_pytorch_model.safetensors"):
            audio_opts.append({
                "label": "音频 VAE",
                "files": ["audio_vae/diffusion_pytorch_model.safetensors"],
                "recommended": True,
                "desc": "推荐 · 音频编解码，用于生成带声音的视频",
            })
        if in_repo("vocoder/diffusion_pytorch_model.safetensors"):
            audio_opts.append({
                "label": "音频解码器",
                "files": ["vocoder/diffusion_pytorch_model.safetensors"],
                "recommended": True,
                "desc": "推荐 · 将音频特征转为可播放的波形",
            })
        categories.append({
            "id": "audio",
            "name": "音频模块",
            "desc": "生成视频配音/配乐，可选但推荐",
            "required": False,
            "options": audio_opts,
        })

    # ── 5. 超分 ──
    if ram_gb >= 16:
        upscale_opts: list[dict] = []
        if in_repo("ltx-2-spatial-upscaler-x2-1.0.safetensors"):
            upscale_opts.append({
                "label": "空间超分 x2",
                "files": ["ltx-2-spatial-upscaler-x2-1.0.safetensors"],
                "recommended": False,
                "desc": "提升输出视频分辨率（512→1024 等）",
            })
        if in_repo("ltx-2-temporal-upscaler-x2-1.0.safetensors"):
            upscale_opts.append({
                "label": "时间超分 x2",
                "files": ["ltx-2-temporal-upscaler-x2-1.0.safetensors"],
                "recommended": False,
                "desc": "提升输出视频帧率（12fps→24fps 等）",
            })
        categories.append({
            "id": "upscaler",
            "name": "超分辨率",
            "desc": "提升画质和流畅度，可选",
            "required": False,
            "options": upscale_opts,
        })

    # ── 6. 辅助模块 ──
    aux_opts: list[dict] = []
    if in_repo("connectors/diffusion_pytorch_model.safetensors"):
        aux_opts.append({
            "label": "多模态连接器",
            "files": ["connectors/diffusion_pytorch_model.safetensors"],
            "recommended": False,
            "desc": "图片-视频特征对齐，i2v 模式需要",
        })
    if in_repo("latent_upsampler/diffusion_pytorch_model.safetensors"):
        aux_opts.append({
            "label": "潜空间上采样器",
            "files": ["latent_upsampler/diffusion_pytorch_model.safetensors"],
            "recommended": False,
            "desc": "潜空间分辨率提升",
        })
    if in_repo("ltx-2-19b-distilled-lora-384.safetensors"):
        aux_opts.append({
            "label": "LoRA 384px 适配器",
            "files": ["ltx-2-19b-distilled-lora-384.safetensors"],
            "recommended": False,
            "desc": "蒸馏版 384px 分辨率微调权重",
        })
    if aux_opts:
        categories.append({
            "id": "auxiliary",
            "name": "辅助模块",
            "desc": "扩展功能，按需选择",
            "required": False,
            "options": aux_opts,
        })

    return {
        "repo": "Lightricks/LTX-2",
        "system": {"chip": sys_info.chip, "ram_gb": ram_gb, "tier": tier},
        "categories": categories,
    }


@router.post("/models/download", status_code=202, responses={400: {"model": ErrorResponse}})
async def trigger_download(
    req: ModelDownloadRequest,
    dm=Depends(get_download_manager),
    registry=Depends(get_model_registry),
):
    """触发模型权重下载（后台线程执行）。"""
    if not req.repo:
        raise HTTPException(status_code=400, detail="repo is required")

    from jiandou.manager.download import ModelDownloadSpec

    filename = req.filename.strip() if req.filename else "*"
    spec = ModelDownloadSpec(repo=req.repo, filename=filename, revision=req.revision)
    name = filename if filename != "*" else req.repo.split("/")[-1]

    if name in _downloads and _downloads[name]["status"] in ("queued", "downloading"):
        return {"message": f"Already downloading {name}", "name": name, "status": "downloading"}

    cancel_evt = threading.Event()
    _cancel_events[name] = cancel_evt
    _downloads[name] = {
        "name": name, "repo": req.repo, "filename": filename,
        "progress": 0, "downloaded": 0, "total": 0,
        "speed_mbps": 0, "eta_seconds": None,
        "status": "queued",
    }

    t = threading.Thread(target=_do_download, args=(spec, name, dm, registry, cancel_evt), daemon=True)
    t.start()
    return {"message": f"Download started for {req.repo}/{filename}", "name": name, "status": "queued"}


@router.delete("/models/download/{name}")
async def cancel_download(name: str):
    """取消/删除一个下载任务。"""
    if name not in _downloads:
        raise HTTPException(status_code=404, detail=f"No download named '{name}'")

    status = _downloads[name].get("status", "")
    if status in ("queued", "downloading"):
        _cancel_events[name].set()
        _downloads[name]["status"] = "cancelled"
        return {"message": f"Cancelled {name}"}
    else:
        # Remove completed/failed entries
        _cancel_events.pop(name, None)
        _downloads.pop(name, None)
        return {"message": f"Removed {name}"}


@router.get("/models/download/progress")
async def get_all_download_progress():
    """查询所有下载进度。"""
    return {"downloads": list(_downloads.values())}


@router.get(
    "/models/download/{name}/progress",
    response_model=ModelDownloadProgressResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_download_progress(name: str, dm=Depends(get_download_manager)):
    """查询单个下载进度。"""
    progress = dm._active.get(name)
    if not progress:
        raise HTTPException(status_code=404, detail=f"No active download for '{name}'")
    return ModelDownloadProgressResponse(
        name=progress.filename, progress=progress.progress,
        downloaded_bytes=progress.downloaded_bytes,
        total_bytes=progress.total_bytes,
        speed_mbps=progress.speed_mbps, eta_seconds=progress.eta_seconds,
    )


# ── internal helpers ──────────────────────────────────────────────────


def _do_download(spec, name: str, dm, registry, cancel_evt: threading.Event):
    """后台下载任务，支持取消和并发限制。"""
    import time as _time

    # Wait for a download slot (max 3 concurrent)
    _downloads[name].update({"status": "queued"})
    acquired = _download_slots.acquire(timeout=600)  # 10 min max wait
    if not acquired:
        _downloads[name].update({"status": "failed", "error": "Download queue timeout"})
        return
    if cancel_evt.is_set():
        _download_slots.release()
        _downloads[name].update({"status": "cancelled"})
        return

    try:
        from jiandou.manager.download import DownloadManager
        total = DownloadManager.get_file_size(spec.repo, spec.filename)
    except Exception:
        total = 0

    _downloads[name].update({"status": "downloading", "total": total, "downloaded": 0})

    stop_monitor = threading.Event()
    monitor = threading.Thread(target=_monitor_progress, args=(name, spec, total, stop_monitor, cancel_evt), daemon=True)
    monitor.start()

    try:
        path = dm._download_sync(spec, on_progress=None, force=False)
        stop_monitor.set()
        monitor.join(timeout=2)

        # Check if cancelled during download
        if cancel_evt.is_set():
            _downloads[name].update({"status": "cancelled", "progress": 0})
            _cancel_events.pop(name, None)
            return

        fn_lower = spec.filename.lower() if spec.filename else ""
        if "text-encoder" in fn_lower or "text_encoder" in fn_lower:
            model_type = "text_encoder"
        elif "upscaler" in fn_lower or "vae" in fn_lower:
            model_type = "vae"
        else:
            model_type = "transformer"

        size_bytes = path.stat().st_size if path.is_file() else sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

        registry.register(
            name=name, repo=spec.repo, filename=spec.filename or "",
            local_path=str(path), size_bytes=size_bytes,
            version="2.3", model_type=model_type,
        )
        _downloads[name].update({
            "status": "done", "progress": 1.0, "downloaded": size_bytes,
            "total": size_bytes, "speed_mbps": 0, "eta_seconds": None, "path": str(path),
        })
        _cancel_events.pop(name, None)
    except Exception as e:
        stop_monitor.set()
        _downloads[name].update({"status": "failed", "error": str(e)})
        _cancel_events.pop(name, None)
    finally:
        _download_slots.release()


def _monitor_progress(name: str, spec, total: int, stop: threading.Event, cancel_evt: threading.Event):
    import os as _os, time as _time

    cache_dir = _os.path.expanduser(_os.environ.get("HF_HUB_CACHE", "~/.cache/huggingface/hub"))
    repo_base = _os.path.join(cache_dir, "models--" + spec.repo.replace("/", "--"))
    snap_dir = _os.path.join(repo_base, "snapshots", spec.revision)
    blobs_dir = _os.path.join(repo_base, "blobs")

    # aria2c writes to snapshots/{revision}/{filename}.part → renames on completion
    target_part = _os.path.join(snap_dir, spec.filename + ".part")
    target_final = _os.path.join(snap_dir, spec.filename)

    prev_size, prev_time = 0, _time.time()

    while not stop.is_set():
        _time.sleep(0.5)
        if cancel_evt.is_set():
            continue

        current_size = 0
        try:
            # Prefer tracking the specific file (aria2c path)
            if _os.path.exists(target_part):
                current_size = _os.path.getsize(target_part)
            elif _os.path.exists(target_final):
                current_size = _os.path.getsize(target_final)
            elif _os.path.isdir(blobs_dir):
                # Fallback: scan blobs/ for hf_hub_download .incomplete files
                for entry in _os.scandir(blobs_dir):
                    if entry.name.endswith(".incomplete") and entry.is_file():
                        current_size += entry.stat().st_size
        except OSError:
            continue

        now = _time.time()
        elapsed, delta = now - prev_time, current_size - prev_size

        if elapsed > 0 and delta >= 0:
            speed = (delta / elapsed) / (1024 * 1024)
            prev_s = _downloads[name].get("speed_mbps", 0) or speed
            smooth_speed = prev_s * 0.6 + speed * 0.4
        else:
            smooth_speed = _downloads[name].get("speed_mbps", 0) or 0

        remaining = total - current_size
        eta = remaining / (smooth_speed * 1024 * 1024) if smooth_speed > 0 and remaining > 0 else None
        progress = current_size / total if total > 0 else 0

        _downloads[name].update({
            "downloaded": current_size, "total": total or current_size,
            "progress": min(progress, 1.0),
            "speed_mbps": round(smooth_speed, 2),
            "eta_seconds": round(eta, 1) if eta else None,
        })
        prev_size, prev_time = current_size, now
