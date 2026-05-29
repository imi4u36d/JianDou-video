"""媒体文件工具。"""

from pathlib import Path


def get_media_info(path: Path) -> dict:
    """Get media file info (resolution, duration, codec).

    Not yet implemented — engine pending.
    """
    raise NotImplementedError


def validate_video(path: Path) -> bool:
    """Check if a video file is valid and playable.

    Not yet implemented — engine pending.
    """
    raise NotImplementedError


def generate_preview(video_path: Path, output_path: Path, time: float = 1.0) -> Path:
    """Extract a preview frame from a video.

    Not yet implemented — engine pending.
    """
    raise NotImplementedError
