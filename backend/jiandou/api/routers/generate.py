"""POST /api/v1/generate — 创建生成任务。"""

from fastapi import APIRouter, Depends, HTTPException

from jiandou.api.deps import get_job_store, get_task_queue
from jiandou.api.schemas import GenerateRequest, TaskResponse
from jiandou.pipeline.task import Task

router = APIRouter(prefix="/api/v1", tags=["Generate"])


@router.post("/generate", response_model=TaskResponse, status_code=201)
async def create_generation(
    req: GenerateRequest,
    job_store=Depends(get_job_store),
    task_queue=Depends(get_task_queue),
):
    """创建视频生成任务。

    返回创建的 Task 对象，包含 task_id 用于后续查询和 WebSocket 订阅。
    """
    task = Task(
        mode=req.mode,
        prompt=req.prompt,
        negative_prompt=req.negative_prompt,
        image_path=req.image_path,
        audio_path=req.audio_path,
        priority=req.priority,
        duration=req.duration,
        width=req.width,
        height=req.height,
        fps=req.fps,
        steps=req.steps,
        cfg=req.cfg,
        seed=req.seed,
        preset=req.preset,
        model_version=req.model_version,
        pipeline=req.pipeline,
        fp16=req.fp16,
        low_memory=req.low_memory,
        upscale=req.upscale,
        upscale_factor=req.upscale_factor,
        generate_audio=req.generate_audio,
        audio_prompt=req.audio_prompt,
    )

    # Apply preset
    from jiandou.pipeline.presets import apply_preset

    apply_preset(task, req.preset)

    # Persist
    job_store.save(task)

    # Enqueue
    try:
        await task_queue.enqueue(task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue task: {e}")

    return TaskResponse.from_task(task)
