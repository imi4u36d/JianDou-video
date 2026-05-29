"""jiandou download — 下载模型权重。"""

import asyncio
from pathlib import Path
from typing import Optional

import typer

from jiandou.cli.main import app, console

download_app = typer.Typer(help="下载模型权重")
app.add_typer(download_app, name="download")


@download_app.command("list")
def download_list(
    repo: str = typer.Option("Lightricks/LTX-2", "--repo", "-r", help="HuggingFace 仓库"),
):
    """列出可下载的模型文件。"""
    from jiandou.manager.download import DownloadManager

    dm = DownloadManager()
    files = dm.list_available(repo)

    if not files:
        console.print(f"[yellow]No safetensors files found in {repo}[/yellow]")
        return

    console.print(f"[bold]Available files in {repo}:[/bold]")
    for f in sorted(files):
        try:
            size = dm.get_file_size(repo, f)
            size_gb = size / 1024**3 if size else 0
            console.print(f"  {f} ({size_gb:.1f} GB)")
        except Exception:
            console.print(f"  {f}")


@download_app.command("pull")
def download_pull(
    repo: str = typer.Argument(..., help="HuggingFace repo, e.g. Lightricks/LTX-2"),
    filename: Optional[str] = typer.Option(None, "--file", "-f", help="指定文件（默认下载全部）"),
    cache_dir: Optional[Path] = typer.Option(None, "--cache-dir", help="下载目录"),
    revision: str = typer.Option("main", "--revision", help="分支/标签"),
    force: bool = typer.Option(False, "--force", help="强制重新下载"),
):
    """下载模型权重文件。"""
    from jiandou.manager.download import DownloadManager, ModelDownloadSpec

    dm = DownloadManager(cache_dir=str(cache_dir) if cache_dir else None)

    if filename:
        specs = [ModelDownloadSpec(repo=repo, filename=filename, revision=revision)]
    else:
        files = dm.list_available(repo, revision)
        if not files:
            console.print(f"[yellow]No files found in {repo}[/yellow]")
            return
        safetensor_files = [f for f in files if f.endswith(".safetensors")]
        specs = [
            ModelDownloadSpec(repo=repo, filename=f, revision=revision)
            for f in safetensor_files
        ]

    console.print(f"[bold]Downloading from {repo}[/bold]")
    console.print(f"  Files: {len(specs)}")
    console.print(f"  Cache: {dm._pool._max_workers} concurrent downloads")

    async def _download_all():
        for spec in specs:
            console.print(f"\n[bold]→ {spec.filename}[/bold]")

            try:
                path = await dm.download(spec, force=force)
                size_mb = Path(path).stat().st_size / 1024**2 if Path(path).exists() else 0

                from jiandou.manager.registry import ModelRegistry
                from jiandou.manager.versions import detect_model_version, detect_model_type

                registry = ModelRegistry()
                version = "unknown"
                model_type = "unknown"
                try:
                    version = detect_model_version(str(path))
                    model_type = detect_model_type(str(path))
                except Exception:
                    pass

                registry.register(
                    name=spec.filename.replace(".safetensors", ""),
                    repo=spec.repo,
                    filename=spec.filename,
                    local_path=str(path),
                    size_bytes=Path(path).stat().st_size,
                    version=version,
                    model_type=model_type,
                )

                console.print(f"  [green]✓[/green] {path} ({size_mb:.0f} MB, v{version}, {model_type})")
            except Exception as e:
                console.print(f"  [red]✗ failed: {e}[/red]")

    asyncio.run(_download_all())
    console.print("\n[green]Done![/green]")
