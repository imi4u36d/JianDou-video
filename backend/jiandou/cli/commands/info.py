"""jiandou info — 系统信息。"""

import platform

import typer
from rich.panel import Panel
from rich.table import Table

from jiandou.cli.main import app, console

info_app = typer.Typer(help="系统信息")
app.add_typer(info_app, name="info")


@info_app.command("system")
def info_system():
    """显示系统硬件信息。"""
    from jiandou.hardware.detect import detect_system_info
    from jiandou.hardware.tier import HardwareTier

    info = detect_system_info()
    tier = HardwareTier(info)

    table = Table(title="System Information", show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Platform", platform.platform())
    table.add_row("Python", platform.python_version())
    table.add_row("Chip", info.chip)
    table.add_row("CPU Cores", str(info.cpu_cores))
    table.add_row("GPU Cores", str(info.gpu_cores))
    table.add_row("RAM", f"{info.ram_gb} GB (free: {info.ram_free_gb} GB)")
    table.add_row("Tier", f"[bold]{info.tier.upper()}[/bold]")
    table.add_row("Max Resolution", f"{info.max_resolution[0]}x{info.max_resolution[1]}")
    table.add_row("Max Frames", str(info.max_frames))
    table.add_row("FP16", str(info.supports_fp16))
    table.add_row("ffmpeg", str(info.ffmpeg_available))
    table.add_row("macOS", info.macos_version)
    table.add_row("MLX", info.mlx_version)

    console.print(table)
    console.print()
    console.print(Panel(tier.get_summary(), title="Hardware Tier Details"))


@info_app.command("models")
def info_models():
    """显示已注册的模型列表。"""
    from jiandou.manager.registry import ModelRegistry

    registry = ModelRegistry()
    models = registry.list_all()

    if not models:
        console.print("[yellow]No models registered.[/yellow]")
        return

    table = Table(title="Registered Models")
    table.add_column("Name", style="cyan")
    table.add_column("Version")
    table.add_column("Type")
    table.add_column("Size")
    table.add_column("Path")

    for m in models:
        size_gb = m.size_bytes / 1024**3 if m.size_bytes else 0
        table.add_row(
            m.name,
            m.version,
            m.model_type,
            f"{size_gb:.1f} GB",
            m.local_path,
        )

    console.print(table)


@info_app.command("checkpoints")
def info_checkpoints(
    directory: str = typer.Argument(".", help="扫描目录"),
):
    """扫描目录下的 checkpoint 文件信息。"""
    from jiandou.manager.versions import scan_checkpoints

    results = scan_checkpoints(directory)

    if not results:
        console.print("[yellow]No safetensors files found.[/yellow]")
        return

    table = Table(title=f"Checkpoints in {directory}")
    table.add_column("File")
    table.add_column("Version")
    table.add_column("Type")
    table.add_column("Size")
    table.add_column("Tensors")

    for r in results:
        if "error" in r:
            table.add_row(r["path"], "[red]error[/red]", "", "", "")
        else:
            table.add_row(
                r["path"],
                r.get("version", "?"),
                r.get("model_type", "?"),
                f"{r.get('size_gb', 0)} GB",
                str(r.get("tensor_count", 0)),
            )

    console.print(table)
