"""GET / DELETE / POST /api/v1/tasks — 任务管理。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from jiandou.api.deps import get_job_store
from jiandou.api.schemas import (
    ErrorResponse,
    TaskListResponse,
    TaskResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Tasks"])


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    status: str = Query("", description="按状态过滤"),
    mode: str = Query("", description="按模式过滤"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    job_store=Depends(get_job_store),
):
    """获取任务列表，支持分页和过滤。"""
    tasks = job_store.list(
        status=status if status else None,
        mode=mode if mode else None,
        offset=offset,
        limit=limit,
        order_desc=True,
    )
    total = job_store.count(status=status if status else None)
    return TaskListResponse(
        tasks=[TaskResponse.from_task(t) for t in tasks],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse, responses={404: {"model": ErrorResponse}})
async def get_task(task_id: str, job_store=Depends(get_job_store)):
    """获取单个任务的详细信息。"""
    task = job_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return TaskResponse.from_task(task)


@router.delete("/tasks/{task_id}", response_model=dict, responses={404: {"model": ErrorResponse}})
async def delete_task(task_id: str, job_store=Depends(get_job_store)):
    """取消或删除任务。"""
    task = job_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    job_store.delete(task_id)
    return {"message": f"Task {task_id} deleted"}


@router.post("/tasks/{task_id}/retry", response_model=TaskResponse, responses={404: {"model": ErrorResponse}})
async def retry_task(
    task_id: str,
    job_store=Depends(get_job_store),
):
    """重试失败的任务。"""
    task = job_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status.value not in ("failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Can only retry failed/cancelled tasks, not {task.status.value}")

    from jiandou.pipeline.task import TaskStatus

    # Reset task
    task.status = TaskStatus.PENDING
    task.progress = 0.0
    task.current_step = 0
    task.error_message = None
    task.started_at = None
    task.completed_at = None
    job_store.save(task)

    # Re-enqueue
    from jiandou.api.deps import get_task_queue

    queue = get_task_queue()
    await queue.enqueue(task)

    return TaskResponse.from_task(task)


@router.get("/tasks/{task_id}/output")
async def download_output(task_id: str, job_store=Depends(get_job_store)):
    """下载任务输出视频。"""
    task = job_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    if not task.output_path:
        raise HTTPException(status_code=404, detail="Output not yet available")

    import os
    if not os.path.exists(task.output_path):
        raise HTTPException(status_code=404, detail="Output file not found on disk")

    return FileResponse(
        task.output_path,
        media_type="video/mp4",
        filename=f"{task_id}.mp4",
    )
