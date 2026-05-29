"""视频增强 — 色彩校正、降噪、锐化。

提供基础的视频后处理增强：
- 对比度/亮度调整
- 色彩饱和度
- 锐化
- 时域降噪（简单帧平均）

所有操作都在 MLX 数组或 numpy 上进行。
"""

from dataclasses import dataclass, field


@dataclass
class EnhanceConfig:
    """视频增强配置。"""

    contrast: float = 1.0  # 对比度倍数 (0.5-2.0)
    brightness: float = 0.0  # 亮度偏移 (-50 to 50)
    saturation: float = 1.0  # 饱和度倍数 (0-2.0)
    sharpen: float = 0.0  # 锐化强度 (0-1.0)
    denoise: float = 0.0  # 时域降噪强度 (0-1.0)

    def __post_init__(self):
        # Clamp to reasonable ranges
        self.contrast = max(0.5, min(2.0, self.contrast))
        self.brightness = max(-50, min(50, self.brightness))
        self.saturation = max(0.0, min(2.0, self.saturation))
        self.sharpen = max(0.0, min(1.0, self.sharpen))
        self.denoise = max(0.0, min(1.0, self.denoise))


class VideoEnhancer:
    """视频增强处理器。

    Usage:
        enhancer = VideoEnhancer(config)
        enhanced = enhancer.enhance(video_array)
    """

    def __init__(self, config: EnhanceConfig = EnhanceConfig()):
        self.config = config

    def enhance(self, video: "mx.array") -> "mx.array":
        """对视频数组进行增强处理。

        Args:
            video: MLX array (T, H, W, C) or numpy array

        Returns:
            Enhanced array (same shape/dtype)
        """
        result = video

        # Convert to numpy for processing
        try:
            import numpy as np
            if hasattr(result, "tolist"):
                result = np.array(result)
            result = result.astype(np.float32)

            if self.config.contrast != 1.0 or self.config.brightness != 0.0:
                result = self._adjust_contrast_brightness(result)

            if self.config.saturation != 1.0:
                result = self._adjust_saturation(result)

            if self.config.sharpen > 0.0:
                result = self._sharpen(result)

            if self.config.denoise > 0.0:
                result = self._denoise_temporal(result)

            # Clamp to valid range
            result = np.clip(result, 0, 255).astype(np.uint8)

            # Convert back to MLX if needed
            try:
                import mlx.core as mx
                return mx.array(result)
            except ImportError:
                return result

        except Exception:
            return video

    def _adjust_contrast_brightness(self, video: "np.ndarray") -> "np.ndarray":
        """对比度和亮度调整。"""
        import numpy as np

        # contrast: multiply around 128 mid-point
        mid = 128.0
        result = (video - mid) * self.config.contrast + mid + self.config.brightness
        return result.astype(video.dtype)

    def _adjust_saturation(self, video: "np.ndarray") -> "np.ndarray":
        """饱和度调整 (RGB)。"""
        import numpy as np

        if video.shape[-1] < 3:
            return video

        # Convert RGB to grayscale luminance
        rgb = video[..., :3]
        # Rec.601 luminance
        gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        gray = np.expand_dims(gray, axis=-1)

        # Blend between gray and original color
        result_rgb = gray + self.config.saturation * (rgb - gray)
        result = np.copy(video)
        result[..., :3] = result_rgb
        return result.astype(video.dtype)

    def _sharpen(self, video: "np.ndarray") -> "np.ndarray":
        """拉普拉斯锐化。"""
        import numpy as np
        from scipy.ndimage import laplace

        if self.config.sharpen <= 0:
            return video

        T, H, W, C = video.shape
        result = np.copy(video)

        for c in range(min(C, 3)):  # Only sharpen color channels
            for t in range(T):
                frame = video[t, :, :, c].astype(np.float64)
                laplacian = laplace(frame)
                result[t, :, :, c] = frame - self.config.sharpen * laplacian

        return result.astype(video.dtype)

    def _denoise_temporal(self, video: "np.ndarray") -> "np.ndarray":
        """时域降噪 — 加权相邻帧平均。"""
        import numpy as np

        if self.config.denoise <= 0 or video.shape[0] < 3:
            return video

        T = video.shape[0]
        result = np.copy(video).astype(np.float64)
        weight = self.config.denoise * 0.5  # Max blend 50%

        for t in range(T):
            neighbors = []
            if t > 0:
                neighbors.append(video[t - 1])
            if t < T - 1:
                neighbors.append(video[t + 1])

            if neighbors:
                neighbor_avg = sum(neighbors) / len(neighbors)
                result[t] = (1 - weight) * video[t] + weight * neighbor_avg

        return result.astype(video.dtype)
