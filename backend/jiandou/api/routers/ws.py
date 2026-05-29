"""WebSocket 端点 — 实时进度推送。

- /ws/queue — 全局队列事件
- /ws/tasks/{task_id} — 单个任务进度推送
"""

import asyncio
import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["WebSocket"])

# Connection registry
_queue_connections: set[WebSocket] = set()
_task_connections: dict[str, set[WebSocket]] = {}


async def broadcast_queue_event(event_type: str, data: dict):
    """向所有队列级 WebSocket 连接广播事件。"""
    dead = set()
    message = json.dumps({"type": event_type, "data": data, "timestamp": time.time()})
    for ws in _queue_connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    _queue_connections.difference_update(dead)


async def broadcast_task_event(task_id: str, event_type: str, data: dict):
    """向特定任务的 WebSocket 连接推送事件。"""
    if task_id not in _task_connections:
        return
    dead = set()
    message = json.dumps({
        "type": event_type,
        "task_id": task_id,
        "data": data,
        "timestamp": time.time(),
    })
    for ws in _task_connections.get(task_id, set()):
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    _task_connections[task_id].difference_update(dead)


@router.websocket("/ws/queue")
async def websocket_queue(ws: WebSocket):
    """全局队列事件 WebSocket。

    推送事件类型：
    - queue.stats — 队列统计变化
    - task.created — 新任务创建
    - task.completed — 任务完成
    """
    await ws.accept()
    _queue_connections.add(ws)
    try:
        while True:
            # Keep alive + receive pings
            data = await asyncio.wait_for(ws.receive_text(), timeout=30)
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except asyncio.TimeoutError:
        pass
    except WebSocketDisconnect:
        pass
    finally:
        _queue_connections.discard(ws)


@router.websocket("/ws/tasks/{task_id}")
async def websocket_task(ws: WebSocket, task_id: str):
    """单个任务 WebSocket — 实时进度推送。

    推送事件类型：
    - task.progress — 进度更新
    - task.status — 状态变化
    - task.preview — 中间帧预览

    Usage (JS):
        const ws = new WebSocket(`ws://host/ws/tasks/${taskId}`)
        ws.onmessage = (e) => { const { type, data } = JSON.parse(e.data) }
    """
    await ws.accept()
    _task_connections.setdefault(task_id, set()).add(ws)

    # Send current task state
    from jiandou.api.deps import get_job_store
    store = get_job_store()
    task = store.get(task_id)
    if task:
        await ws.send_text(json.dumps({
            "type": "task.status",
            "task_id": task_id,
            "data": task.to_dict(),
        }))

    try:
        while True:
            data = await asyncio.wait_for(ws.receive_text(), timeout=30)
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong", "task_id": task_id}))
    except asyncio.TimeoutError:
        pass
    except WebSocketDisconnect:
        pass
    finally:
        if task_id in _task_connections:
            _task_connections[task_id].discard(ws)
            if not _task_connections[task_id]:
                del _task_connections[task_id]
