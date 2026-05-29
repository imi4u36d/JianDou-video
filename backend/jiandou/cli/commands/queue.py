"""jiandou queue — 任务队列管理。"""

import typer
from rich.table import Table

from jiandou.cli.main import app, console

queue_app = typer.Typer(help="任务队列管理")
app.add_typer(queue_app, name="queue")


@queue_app.command("list")
def queue_list(
    status: str = typer.Option("", "--status", "-s", help="按状态过滤 (pending/running/done/failed)"),
    limit: int = typer.Option(20, "--limit", "-n", help="最大显示数"),
):
    """列出任务队列。"""
    from jiandou.storage.job_store import JobStore

    store = JobStore()
    tasks = store.list(
        status=status if status else None,
        limit=limit,
        order_desc=True,
    )

    if not tasks:
        console.print("[yellow]No tasks found.[/yellow]")
        return

    table = Table(title=f"Tasks ({len(tasks)})")
    table.add_column("ID", style="cyan")
    table.add_column("Mode")
    table.add_column("Status")
    table.add_column("Prompt")
    table.add_column("Progress")
    table.add_column("Created")

    for t in tasks:
        status_style = {
            "done": "green", "failed": "red", "running": "blue",
            "pending": "yellow", "cancelled": "dim",
        }.get(t.status.value, "white")

        table.add_row(
            t.id[:8],
            t.mode.value,
            f"[{status_style}]{t.status.value}[/{status_style}]",
            t.prompt[:40] + "..." if len(t.prompt) > 40 else t.prompt,
            f"{t.progress * 100:.0f}%" if t.progress > 0 else "-",
            t.created_at.strftime("%H:%M:%S"),
        )

    console.print(table)
    console.print(f"Total: {store.count()}")


@queue_app.command("clear")
def queue_clear(
    status: str = typer.Option("", "--status", "-s", help="只清除特定状态的任务"),
    hours: int = typer.Option(168, "--hours", "-h", help="清除超过 N 小时前的已完成任务"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
):
    """清理任务记录。"""
    from jiandou.storage.job_store import JobStore

    store = JobStore()

    if status:
        tasks = store.list(status=status, limit=1000)
        count = len(tasks)
        if count == 0:
            console.print("[yellow]No matching tasks.[/yellow]")
            return
        if not yes:
            typer.confirm(f"Delete {count} tasks with status '{status}'?", abort=True)
        for t in tasks:
            store.delete(t.id)
        console.print(f"[green]Deleted {count} tasks.[/green]")
    else:
        count = store.cleanup_stale(hours)
        console.print(f"[green]Cleaned up {count} stale tasks (>{hours}h).[/green]")


@queue_app.command("show")
def queue_show(
    task_id: str = typer.Argument(..., help="Task ID"),
):
    """显示单个任务详情。"""
    from jiandou.storage.job_store import JobStore

    store = JobStore()
    task = store.get(task_id)

    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        return

    d = task.to_dict()
    console.print(f"[bold]Task {task.id}[/bold]")
    console.print(f"  Mode:    {task.mode.value}")
    console.print(f"  Status:  {task.status.value}")
    console.print(f"  Prompt:  {task.prompt}")
    if task.negative_prompt:
        console.print(f"  Negative:{task.negative_prompt}")
    console.print(f"  Size:    {task.width}x{task.height}, {task.fps}fps, {task.duration}s")
    console.print(f"  Steps:   {task.steps}, CFG: {task.cfg}, Seed: {task.seed}")
    console.print(f"  Pipeline:{task.pipeline}, FP16: {task.fp16}, LowMem: {task.low_memory}")
    console.print(f"  Progress:{task.current_step}/{task.total_steps} ({task.progress * 100:.0f}%)")
    if task.output_path:
        console.print(f"  Output:  {task.output_path}")
    if task.error_message:
        console.print(f"  [red]Error: {task.error_message}[/red]")
    console.print(f"  Created: {task.created_at}")
    if task.started_at:
        console.print(f"  Started: {task.started_at}")
    if task.completed_at:
        elapsed = (task.completed_at - task.started_at).total_seconds() if task.started_at else 0
        console.print(f"  Done:    {task.completed_at} ({elapsed:.1f}s)")
