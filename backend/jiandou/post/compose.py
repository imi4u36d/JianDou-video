"""音视频合成 — ffmpeg 驱动的音视频合成。

支持：
- 纯视频编码 (MLX array → mp4)
- 音频 + 视频合成
- 帧序列 → 视频
- 视频 → GIF/WebM 转换
"""

import asyncio
import os
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Optional


class OutputFormat(StrEnum):
    MP4 = "mp4"
    GIF = "gif"
    WEBM = "webm"
    MOV = "mov"


class VideoComposer:
    """音视频合成器 — 将 MLX 生成的 array 编码为视频文件。"""

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg = ffmpeg_path or "ffmpeg"

    async def compose(
        self,
        video_path: str,
        output_path: str,
        audio_path: Optional[str] = None,
        fps: int = 24,
        format: OutputFormat = OutputFormat.MP4,
        crf: int = 18,
        preset: str = "medium",
    ) -> str:
        """合成视频和音频。

        Args:
            video_path: 视频文件路径 (mp4/raw)
            audio_path: 音频文件路径 (wav/mp3) 或 None
            output_path: 输出路径
            fps: 帧率
            format: 输出格式
            crf: 质量 (0-51, lower=better)
            preset: 编码预设 (fast/medium/slow)

        Returns:
            output_path
        """
        if format == OutputFormat.GIF:
            return await self._to_gif(video_path, output_path, fps)
        if format == OutputFormat.WEBM:
            return await self._to_webm(video_path, output_path)

        return await self._to_mp4(video_path, output_path, audio_path, fps, crf, preset)

    async def frames_to_video(
        self,
        frames_dir: str,
        output_path: str,
        fps: int = 24,
        pattern: str = "frame_%05d.png",
    ) -> str:
        """将帧图像序列编码为视频。"""
        from jiandou.utils.ffmpeg import run_ffmpeg

        args = [
            "-framerate", str(fps),
            "-i", os.path.join(frames_dir, pattern),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "18",
            "-preset", "medium",
            output_path,
        ]
        await run_ffmpeg(args, timeout=600)
        return output_path

    async def extract_audio(
        self,
        video_path: str,
        output_path: str,
        format: str = "wav",
    ) -> str:
        """从视频中提取音轨。"""
        from jiandou.utils.ffmpeg import run_ffmpeg

        args = [
            "-i", video_path,
            "-vn",  # No video
            "-acodec", "pcm_s16le" if format == "wav" else "libmp3lame",
            output_path,
        ]
        await run_ffmpeg(args, timeout=60)
        return output_path

    # ── internal ──────────────────────────────────────────────────────

    async def _to_mp4(
        self, video_path: str, output_path: str,
        audio_path: Optional[str], fps: int, crf: int, preset: str,
    ) -> str:
        from jiandou.utils.ffmpeg import run_ffmpeg

        args = ["-i", video_path]
        if audio_path:
            args.extend(["-i", audio_path])

        args.extend([
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", str(crf),
            "-preset", preset,
            "-r", str(fps),
        ])

        if audio_path:
            args.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])

        args.append(output_path)
        await run_ffmpeg(args, timeout=600)
        return output_path

    async def _to_gif(self, video_path: str, output_path: str, fps: int = 10) -> str:
        from jiandou.utils.ffmpeg import run_ffmpeg

        palette = tempfile.mktemp(suffix=".png")
        args_palette = [
            "-i", video_path,
            "-vf", f"fps={fps},scale=480:-1:flags=lanczos,palettegen",
            "-y", palette,
        ]
        await run_ffmpeg(args_palette, timeout=60)

        args_gif = [
            "-i", video_path,
            "-i", palette,
            "-lavfi", f"fps={fps},scale=480:-1:flags=lanczos [x]; [x][1:v] paletteuse",
            "-y", output_path,
        ]
        await run_ffmpeg(args_gif, timeout=120)
        os.unlink(palette)
        return output_path

    async def _to_webm(self, video_path: str, output_path: str) -> str:
        from jiandou.utils.ffmpeg import run_ffmpeg

        args = [
            "-i", video_path,
            "-c:v", "libvpx-vp9",
            "-crf", "30",
            "-b:v", "0",
            "-c:a", "libopus",
            output_path,
        ]
        await run_ffmpeg(args, timeout=600)
        return output_path


def get_video_info(path: Path) -> dict:
    """获取视频文件信息。"""
    import json
    import subprocess

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", str(path),
            ],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            video_stream = next(
                (s for s in data.get("streams", []) if s["codec_type"] == "video"),
                {},
            )
            return {
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "fps": eval(video_stream.get("r_frame_rate", "0/1")),
                "duration": float(data.get("format", {}).get("duration", 0)),
                "codec": video_stream.get("codec_name", "unknown"),
                "size_bytes": int(data.get("format", {}).get("size", 0)),
            }
    except Exception:
        pass

    return {"width": 0, "height": 0, "fps": 0, "duration": 0, "codec": "unknown", "size_bytes": 0}
