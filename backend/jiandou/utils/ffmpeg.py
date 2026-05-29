"""ffmpeg 调用封装 — 异步视频/音频处理。"""

import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def ffmpeg_available() -> bool:
    """Check if ffmpeg is available on the system."""
    return shutil.which("ffmpeg") is not None


async def run_ffmpeg(args: list[str], timeout: Optional[float] = None) -> tuple[int, str, str]:
    """Run ffmpeg asynchronously and return (returncode, stdout, stderr)."""
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg not found")

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    return proc.returncode or 0, stdout.decode(), stderr.decode()


def get_video_info(path: Path) -> dict:
    """Get video file info (resolution, duration, codec)."""
    if not shutil.which("ffprobe"):
        return {"width": 0, "height": 0, "fps": 0, "duration": 0, "codec": "unknown", "size_bytes": 0}

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            video_stream = next(
                (s for s in data.get("streams", []) if s["codec_type"] == "video"),
                {},
            )
            fps_str = video_stream.get("r_frame_rate", "0/1")
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 0

            return {
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "fps": fps,
                "duration": float(data.get("format", {}).get("duration", 0)),
                "codec": video_stream.get("codec_name", "unknown"),
                "size_bytes": int(data.get("format", {}).get("size", 0)),
            }
    except Exception:
        pass

    return {"width": 0, "height": 0, "fps": 0, "duration": 0, "codec": "unknown", "size_bytes": 0}


def video_to_frames(
    input_path: Path,
    output_dir: Path,
    fps: Optional[int] = None,
) -> list[Path]:
    """Extract frames from video as PNG images."""
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["ffmpeg", "-y", "-i", str(input_path)]
    if fps:
        cmd.extend(["-r", str(fps)])
    cmd.append(str(output_dir / "frame_%05d.png"))

    subprocess.run(cmd, capture_output=True, check=True)
    return sorted(output_dir.glob("frame_*.png"))


def frames_to_video(
    frames_dir: Path,
    output_path: Path,
    fps: int = 24,
) -> Path:
    """Combine PNG frame sequence into MP4 video."""
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%05d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def compose_video_audio(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
) -> Path:
    """Combine video and audio tracks."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path
