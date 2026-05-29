"""CLI 入口 — Typer app 定义和全局选项。"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="jiandou",
    help="JianDou-video — AI 视频生成平台",
    no_args_is_help=True,
)

console = Console()


@app.callback()
def main(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="配置文件路径 (YAML)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="详细输出"
    ),
):
    """JianDou-video: 基于 MLX 的 AI 视频生成工具。"""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose


# Import commands to register them
from jiandou.cli.commands import generate, download, serve, queue, info  # noqa: E402
