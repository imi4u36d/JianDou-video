"""GET /api/v1/system — 系统信息和配置。"""

from fastapi import APIRouter, Depends

from jiandou.api.deps import get_config
from jiandou.api.schemas import (
    ConfigResponse,
    ConfigUpdateRequest,
    SystemInfoResponse,
)

router = APIRouter(prefix="/api/v1", tags=["System"])


@router.get("/system/info", response_model=SystemInfoResponse)
async def get_system_info():
    """获取系统硬件信息。"""
    from jiandou.hardware.detect import detect_system_info

    info = detect_system_info()
    return SystemInfoResponse(
        chip=info.chip,
        cpu_cores=info.cpu_cores,
        gpu_cores=info.gpu_cores,
        ram_gb=info.ram_gb,
        ram_free_gb=info.ram_free_gb,
        tier=info.tier,
        max_resolution=list(info.max_resolution),
        max_frames=info.max_frames,
        supports_fp16=info.supports_fp16,
        supports_audio=info.supports_audio,
        ffmpeg_available=info.ffmpeg_available,
        macos_version=info.macos_version,
        mlx_version=info.mlx_version,
    )


@router.get("/system/config", response_model=ConfigResponse)
async def get_system_config(config=Depends(get_config)):
    """获取当前系统配置。"""
    return ConfigResponse(
        server={
            "host": config.server.host,
            "port": config.server.port,
            "cors_origins": config.server.cors_origins,
        },
        engine={
            "model_version": config.engine.model_version,
            "pipeline": config.engine.pipeline,
            "fp16": config.engine.fp16,
            "low_memory": config.engine.low_memory,
        },
        queue={
            "max_workers": config.queue.max_workers,
            "task_timeout": config.queue.task_timeout,
            "resident_mode": config.queue.resident_mode,
        },
        generation={
            "duration": config.generation.duration,
            "width": config.generation.width,
            "height": config.generation.height,
            "fps": config.generation.fps,
            "steps": config.generation.steps,
        },
        post={
            "upscale": config.post.upscale,
            "upscale_factor": config.post.upscale_factor,
            "generate_audio": config.post.generate_audio,
        },
    )


@router.patch("/system/config", response_model=ConfigResponse)
async def update_system_config(req: ConfigUpdateRequest):
    """更新系统配置（内存中，不持久化）。"""
    from jiandou.api.deps import get_config

    config = get_config()
    if req.server:
        for k, v in req.server.items():
            if hasattr(config.server, k):
                setattr(config.server, k, v)
    if req.engine:
        for k, v in req.engine.items():
            if hasattr(config.engine, k):
                setattr(config.engine, k, v)
    if req.queue:
        for k, v in req.queue.items():
            if hasattr(config.queue, k):
                setattr(config.queue, k, v)
    if req.generation:
        for k, v in req.generation.items():
            if hasattr(config.generation, k):
                setattr(config.generation, k, v)
    if req.post:
        for k, v in req.post.items():
            if hasattr(config.post, k):
                setattr(config.post, k, v)

    # Return updated config
    return await get_system_config(config)
