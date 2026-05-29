"""jiandou serve — 启动 API 服务。"""

import typer

from jiandou.cli.main import app, console

serve_app = typer.Typer(help="启动 API 服务")
app.add_typer(serve_app, name="serve")


@serve_app.command("start")
def serve_start(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="绑定地址"),
    port: int = typer.Option(6701, "--port", "-p", help="端口"),
    reload: bool = typer.Option(False, "--reload", "-r", help="热重载（开发模式）"),
    workers: int = typer.Option(1, "--workers", "-w", help="工作进程数"),
):
    """启动 FastAPI 服务。"""
    import uvicorn

    console.print(f"[bold]Starting JianDou Video server[/bold]")
    console.print(f"  Address:  [cyan]http://{host}:{port}[/cyan]")
    console.print(f"  API Docs: [cyan]http://{host}:{port}/api/docs[/cyan]")
    console.print(f"  ReDoc:    [cyan]http://{host}:{port}/api/redoc[/cyan]")
    console.print()

    if reload:
        uvicorn.run(
            "jiandou.api.app:create_app",
            host=host,
            port=port,
            reload=True,
            reload_dirs=["jiandou"],
            factory=True,
        )
    else:
        uvicorn.run(
            "jiandou.api.app:create_app",
            host=host,
            port=port,
            workers=workers,
            factory=True,
        )
