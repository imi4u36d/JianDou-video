"""常驻子进程管理 — 可选的 Warm Helper 模式。

常驻模式下，模型权重保持在子进程内存中，job 通过 stdin/stdout 通信。
支持 idle timeout 自动退出和内存监控。
"""

import asyncio
import json
import os
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ResidentConfig:
    """常驻模式配置。"""

    enabled: bool = False
    idle_timeout: float = 300.0  # 空闲超时（秒）
    max_memory_gb: float = 50.0  # 最大内存使用（GB），超限自动退出
    checkpoint_path: str = ""
    gemma_path: str = ""
    fp16: bool = True
    low_memory: bool = False


class ResidentHelper:
    """常驻子进程管理。

    Usage:
        helper = ResidentHelper(config)
        await helper.start()
        result = await helper.submit(job_data)
        await helper.stop()
    """

    def __init__(self, config: ResidentConfig):
        self.config = config
        self._process: Optional[asyncio.subprocess.Process] = None
        self._last_activity: float = 0.0
        self._monitor_task: Optional[asyncio.Task] = None
        self._pending: dict[str, asyncio.Future] = {}

    async def start(self) -> None:
        """启动常驻子进程并加载模型。"""
        if self._process is not None:
            return

        self._process = await asyncio.create_subprocess_exec(
            "python3",
            "-m",
            "jiandou.engine.resident_worker",
            "--checkpoint",
            self.config.checkpoint_path,
            "--gemma-path",
            self.config.gemma_path,
            "--fp16" if self.config.fp16 else "--fp32",
            "--low-memory" if self.config.low_memory else "",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._last_activity = time.time()
        self._monitor_task = asyncio.create_task(self._monitor())

    async def stop(self) -> None:
        """停止常驻子进程。"""
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        if self._process:
            self._process.stdin.write(b'{"action":"shutdown"}\n')
            try:
                await asyncio.wait_for(self._process.stdin.drain(), timeout=5)
            except asyncio.TimeoutError:
                pass
            self._process.terminate()
            await self._process.wait()
            self._process = None

    async def submit(self, job_id: str, params: dict) -> dict:
        """提交一个推理任务到常驻进程。"""
        if self._process is None:
            raise RuntimeError("Resident helper not started")

        self._last_activity = time.time()
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[job_id] = future

        request = json.dumps({"action": "generate", "job_id": job_id, **params})
        self._process.stdin.write((request + "\n").encode())
        await self._process.stdin.drain()

        return await future

    async def _monitor(self) -> None:
        """监控进程状态、idle timeout 和 stdout 响应。"""
        while self._process and self._process.returncode is None:
            # Idle timeout check
            if time.time() - self._last_activity > self.config.idle_timeout:
                await self.stop()
                return

            # Read stdout line
            try:
                line = await asyncio.wait_for(
                    self._process.stdout.readline(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            if not line:
                break

            try:
                msg = json.loads(line.decode())
                job_id = msg.get("job_id")
                if job_id and job_id in self._pending:
                    self._pending[job_id].set_result(msg)
                    del self._pending[job_id]
            except json.JSONDecodeError:
                pass

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.returncode is None


def resident_worker_main():
    """子进程入口 — 加载模型并监听 stdin 执行推理。

    通过命令行参数启动：python -m jiandou.engine.resident_worker [options]
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--gemma-path", default="")
    parser.add_argument("--fp16", action="store_true", default=True)
    parser.add_argument("--fp32", dest="fp16", action="store_false")
    parser.add_argument("--low-memory", action="store_true")
    args = parser.parse_args()

    # Load model once at startup
    from jiandou.engine.session import InferenceSession, SessionConfig

    session = InferenceSession(
        SessionConfig(
            checkpoint_path=args.checkpoint,
            gemma_path=args.gemma_path,
            fp16=args.fp16,
            low_memory=args.low_memory,
        )
    )
    session.load()
    sys.stderr.write("RESIDENT_READY\n")
    sys.stderr.flush()

    # Event loop
    for line in sys.stdin:
        try:
            msg = json.loads(line.strip())
        except json.JSONDecodeError:
            continue

        action = msg.get("action")
        if action == "shutdown":
            break
        elif action == "generate":
            job_id = msg.get("job_id", "unknown")
            try:
                result = session.run()
                response = {
                    "job_id": job_id,
                    "status": "done",
                    "result_shape": str(result[0].shape) if result[0] is not None else "None",
                }
            except Exception as e:
                response = {"job_id": job_id, "status": "failed", "error": str(e)}
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

    session.unload()
