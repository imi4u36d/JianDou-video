"""jiandou generate — 命令行视频生成。"""

from pathlib import Path
from typing import Optional

import typer

from jiandou.cli.main import app, console

generate_app = typer.Typer(help="创建生成任务")
app.add_typer(generate_app, name="generate")


# Shared options
def _common_options(
    duration: float = 5.0, width: int = 768, height: int = 512,
    fps: int = 24, steps: int = 8, cfg: float = 2.0,
    seed: int = -1, preset: str = "balanced",
    pipeline: str = "auto", fp16: bool = True, low_memory: bool = False,
    upscale: str = "none", output: Optional[str] = None,
):
    """Shared options helper — not used directly, just grouping."""
    pass


@generate_app.command("t2v")
def generate_t2v(
    prompt: str = typer.Argument(..., help="文本提示词"),
    negative: Optional[str] = typer.Option(None, "--negative", "-n", help="负面提示词"),
    duration: float = typer.Option(5.0, "--duration", "-d", help="视频时长（秒）", min=1, max=30),
    width: int = typer.Option(768, "--width", "-W", help="视频宽度", min=256, max=2048),
    height: int = typer.Option(512, "--height", "-H", help="视频高度", min=128, max=1280),
    fps: int = typer.Option(24, "--fps", help="帧率", min=8, max=60),
    steps: int = typer.Option(8, "--steps", "-s", help="推理步数", min=1, max=50),
    cfg: float = typer.Option(2.0, "--cfg", "-c", help="CFG scale", min=0.0, max=20.0),
    seed: int = typer.Option(-1, "--seed", help="随机种子，-1 随机"),
    preset: str = typer.Option("balanced", "--preset", "-p", help="参数预设 (fast/balanced/quality)"),
    pipeline: str = typer.Option("auto", "--pipeline", help="推理流水线 (auto/distilled/one-stage/two-stage)"),
    fp16: bool = typer.Option(True, "--fp16/--fp32", help="FP16 精度"),
    low_memory: bool = typer.Option(False, "--low-memory", help="低内存模式"),
    upscale: str = typer.Option("none", "--upscale", help="超分 (none/piper/model/both)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出路径"),
    submit: bool = typer.Option(False, "--submit", help="提交到本地 API 服务"),
):
    """文本到视频 (T2V) 生成。"""
    _do_generate(
        mode="t2v", prompt=prompt, negative_prompt=negative or "",
        duration=duration, width=width, height=height, fps=fps,
        steps=steps, cfg=cfg, seed=seed, preset=preset,
        pipeline=pipeline, fp16=fp16, low_memory=low_memory,
        upscale=upscale, output=output, submit=submit,
    )


@generate_app.command("i2v")
def generate_i2v(
    image: Path = typer.Argument(..., help="输入图片路径"),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="文本提示词"),
    duration: float = typer.Option(5.0, "--duration", "-d", help="视频时长（秒）"),
    width: int = typer.Option(768, "--width", "-W", help="宽度"),
    height: int = typer.Option(512, "--height", "-H", help="高度"),
    steps: int = typer.Option(8, "--steps", "-s", help="推理步数"),
    seed: int = typer.Option(-1, "--seed", help="随机种子"),
    preset: str = typer.Option("balanced", "--preset", help="参数预设"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出路径"),
    submit: bool = typer.Option(False, "--submit", help="提交到本地 API 服务"),
):
    """图片到视频 (I2V) 生成。"""
    if not image.exists():
        console.print(f"[red]Image not found: {image}[/red]")
        raise typer.Exit(1)

    _do_generate(
        mode="i2v", prompt=prompt or "", image_path=str(image),
        duration=duration, width=width, height=height, fps=24,
        steps=steps, cfg=2.0, seed=seed, preset=preset,
        pipeline="auto", fp16=True, low_memory=False,
        upscale="none", output=output, submit=submit,
    )


def _do_generate(
    mode: str, prompt: str, negative_prompt: str = "",
    image_path: Optional[str] = None,
    duration: float = 5.0, width: int = 768, height: int = 512,
    fps: int = 24, steps: int = 8, cfg: float = 2.0,
    seed: int = -1, preset: str = "balanced",
    pipeline: str = "auto", fp16: bool = True, low_memory: bool = False,
    upscale: str = "none", output: Optional[Path] = None,
    submit: bool = False,
):
    """统一生成入口。"""

    if submit:
        # Submit to local API
        _submit_to_api(
            mode=mode, prompt=prompt, negative_prompt=negative_prompt,
            image_path=image_path, duration=duration, width=width, height=height,
            fps=fps, steps=steps, cfg=cfg, seed=seed, preset=preset,
            pipeline=pipeline, fp16=fp16, low_memory=low_memory,
            upscale=upscale,
        )
        return

    # Direct execution via TaskRunner (when API not running)
    from jiandou.pipeline.task import Task, TaskMode
    from jiandou.pipeline.presets import apply_preset
    from jiandou.storage.job_store import JobStore

    task = Task(
        mode=TaskMode(mode),
        prompt=prompt,
        negative_prompt=negative_prompt,
        image_path=image_path,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        steps=steps,
        cfg=cfg,
        seed=seed,
        preset=preset,
        pipeline=pipeline,
        fp16=fp16,
        low_memory=low_memory,
        upscale=upscale,
    )
    apply_preset(task, preset)

    console.print(f"[bold]{mode.upper()}[/bold]: {task.prompt}")
    console.print(
        f"  Resolution: {task.width}x{task.height}, {task.duration}s, "
        f"{task.fps}fps, {task.steps} steps"
    )
    console.print(f"  Pipeline: {task.pipeline}, Preset: {task.preset}")
    console.print(f"  Task ID: {task.id[:8]}")

    # Persist
    store = JobStore()
    store.save(task)

    # Run with progress display
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        p_task = progress.add_task("Generating...", total=task.steps)

        task.status = "running"
        store.update_status(task.id, "running")

        try:
            from jiandou.pipeline.runner import TaskRunner

            runner = TaskRunner(task)

            def on_progress(step: int, total: int, stage: str = ""):
                progress.update(p_task, completed=step, total=total)

            runner.tracker.add_listener(
                lambda snap: progress.update(
                    p_task,
                    completed=snap.current_step,
                    total=task.steps,
                    description=f"[{snap.phase.value}]",
                )
            )

            # Execute
            result_task = runner.run()
            progress.update(p_task, completed=task.steps)
            store.save(result_task)

            if result_task.status.value == "done":
                console.print(f"[green]Done![/green]")
                if result_task.output_path:
                    console.print(f"  Output: {result_task.output_path}")
            else:
                console.print(f"[red]Failed: {result_task.error_message}[/red]")

        except KeyboardInterrupt:
            task.status = "cancelled"
            store.update_status(task.id, "cancelled")
            console.print("[yellow]Cancelled.[/yellow]")
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            store.save(task)
            console.print(f"[red]Error: {e}[/red]")


def _submit_to_api(**kwargs):
    """通过 HTTP 提交任务到本地 API。"""
    import json
    import urllib.request

    api_url = "http://127.0.0.1:8000/api/v1/generate"
    data = json.dumps(kwargs).encode()

    try:
        req = urllib.request.Request(api_url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            console.print(f"[green]Submitted![/green] Task ID: {result['id'][:8]}")
            console.print(f"  Track: jiandou queue show {result['id']}")
            console.print(f"  API:    http://127.0.0.1:8000/api/v1/tasks/{result['id']}")
    except urllib.error.URLError:
        console.print("[red]API server not running. Start with: jiandou serve start[/red]")
        console.print("[yellow]Tip: omit --submit to run directly without API.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
