"""推理会话 — 封装 LTX-2-MLX 模型加载/卸载/推理的生命周期。"""

import gc
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import mlx.core as mx

_LIB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "lib" / "LTX-2-MLX"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from jiandou.storage.config import EngineConfig, GenerationConfig


@dataclass
class SessionConfig:
    """一次推理会话的完整配置。"""
    checkpoint_path: str
    gemma_path: str = ""
    spatial_upscaler_path: str = ""
    temporal_upscaler_path: str = ""
    checkpoint_repo: str = "Lightricks/LTX-2"
    checkpoint_filename: str = "ltx-2.3-22b-distilled-1.1.safetensors"
    gemma_repo: str = "google/gemma-3-12b-it"
    model_version: str = "2.3"
    pipeline: str = "auto"
    fp16: bool = True
    low_memory: bool = False
    use_fp8: bool = False
    prompt: str = ""
    negative_prompt: str = ""
    width: int = 768
    height: int = 512
    num_frames: int = 121
    fps: float = 24.0
    steps: int = 8
    cfg: float = 2.0
    seed: int = -1
    stg_scale: float = 0.0
    image_path: Optional[str] = None
    audio_enabled: bool = False
    audio_prompt: str = ""
    on_progress: Optional[Callable[[int, int, str], None]] = None
    on_step: Optional[Callable[[int, int], None]] = None

    def to_mlx_dtype(self) -> mx.Dtype:
        return mx.float16 if self.fp16 else mx.float32


class SessionError(RuntimeError):
    """推理会话错误。"""


class InferenceSession:
    """管理一次完整的模型推理生命周期。"""

    def __init__(self, config: SessionConfig):
        self.config = config
        self._ledger = None
        self._transformer = None
        self._pipeline_instance = None
        self._pipe_config = None
        self._loaded = False
        self._start_time: Optional[float] = None
        self._text_encoder = None  # may be V1 (VideoGemmaTextEncoderModel) or V2 (AV)
        self._is_v2_checkpoint = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        if self._loaded:
            return
        self._start_time = time.time()
        try:
            self._ensure_downloaded()
            from LTX_2_MLX.utils.model_ledger import create_model_ledger
            self._ledger = create_model_ledger(
                checkpoint_path=self.config.checkpoint_path,
                gemma_path=self.config.gemma_path or None,
                spatial_upscaler_path=self.config.spatial_upscaler_path or None,
                temporal_upscaler_path=self.config.temporal_upscaler_path or None,
                use_fp16=self.config.fp16,
                use_fp8=self.config.use_fp8,
            )
            self._transformer = self._ledger.transformer()
            self._loaded = True
        except Exception as e:
            raise SessionError(f"Failed to load model: {e}") from e

    def _ensure_downloaded(self) -> None:
        from jiandou.manager.download import DownloadManager, ModelDownloadSpec
        config = self.config
        dm = DownloadManager()
        need_download = []
        cp = Path(config.checkpoint_path) if config.checkpoint_path else None
        if not cp or not cp.exists():
            need_download.append(ModelDownloadSpec(
                repo=config.checkpoint_repo, filename=config.checkpoint_filename,
            ))
        gp = Path(config.gemma_path) if config.gemma_path else None
        if gp and not gp.exists():
            need_download.append(ModelDownloadSpec(
                repo=config.gemma_repo, filename="*",
                allow_patterns=["*.safetensors", "tokenizer.model", "*.json"],
            ))
        if not need_download:
            return
        print(f"Auto-downloading {len(need_download)} model(s)...")
        for spec in need_download:
            path = dm._download_sync(spec)
            if spec.filename != "*":
                if not config.checkpoint_path or not Path(config.checkpoint_path).exists():
                    config.checkpoint_path = str(path)
            else:
                if not config.gemma_path or not Path(config.gemma_path).exists():
                    config.gemma_path = str(path)
        print("Download complete.")

    def run(self) -> tuple:
        if not self._loaded:
            self.load()
        config = self.config
        try:
            pipeline = self._resolve_pipeline()
            encoding, text_mask = self._encode_prompt()
            images = self._resolve_images()
            callback = self._make_callback()

            is_one_stage = config.pipeline in ("one-stage", "two-stage") or (
                config.pipeline == "auto" and config.steps > 8)

            if is_one_stage:
                if config.negative_prompt:
                    neg_encoding, neg_mask = self._encode_prompt(config.negative_prompt)
                else:
                    neg_encoding, neg_mask = None, None
                result = pipeline(
                    encoding, neg_encoding or encoding,
                    self._pipe_config,
                    images=images,
                    callback=callback,
                )
            else:
                result = pipeline(
                    encoding, text_mask,
                    self._pipe_config,
                    images=images,
                    callback=callback,
                )
            return result
        except Exception as e:
            raise SessionError(f"Inference failed: {e}") from e

    def unload(self) -> None:
        if self._ledger is not None:
            self._ledger.clear_all_models()
            self._ledger = None
        self._transformer = None
        self._pipeline_instance = None
        self._text_encoder = None
        self._loaded = False
        gc.collect()

    def __enter__(self):
        self.load()
        return self

    def __exit__(self, *args):
        self.unload()

    def _resolve_pipeline(self):
        self._ensure_loaded()
        pipeline_name = self.config.pipeline
        if pipeline_name == "auto":
            pipeline_name = "distilled" if self.config.steps <= 8 else "one-stage"

        if pipeline_name == "distilled":
            from LTX_2_MLX.pipelines.distilled import (
                DistilledConfig, create_distilled_pipeline,
            )
            decoder = self._ledger.video_decoder()
            spatial_upscaler = None
            if self._ledger.spatial_upscaler_path:
                spatial_upscaler = self._ledger.spatial_upscaler()
            self._pipeline_instance = create_distilled_pipeline(
                transformer=self._transformer,
                video_encoder=self._ledger.video_encoder(),
                video_decoder=decoder,
                spatial_upscaler=spatial_upscaler,
            )
            self._pipe_config = DistilledConfig(
                height=self.config.height, width=self.config.width,
                num_frames=self.config.num_frames, fps=self.config.fps,
                seed=self.config.seed,
                dtype=self.config.to_mlx_dtype(),
            )
        elif pipeline_name in ("one-stage", "two-stage"):
            from LTX_2_MLX.pipelines.one_stage import (
                OneStageCFGConfig, create_one_stage_pipeline,
            )
            decoder = self._ledger.video_decoder()
            self._pipeline_instance = create_one_stage_pipeline(
                transformer=self._transformer,
                video_encoder=self._ledger.video_encoder(),
                video_decoder=decoder,
            )
            self._pipe_config = OneStageCFGConfig(
                height=self.config.height, width=self.config.width,
                num_frames=self.config.num_frames, fps=self.config.fps,
                seed=self.config.seed,
                cfg_scale=self.config.cfg,
                num_inference_steps=self.config.steps,
                dtype=self.config.to_mlx_dtype(),
            )
        else:
            from LTX_2_MLX.pipelines.text_to_video import (
                GenerationConfig, create_pipeline,
            )
            self._pipeline_instance = create_pipeline(
                transformer=self._transformer, decoder=self._ledger.video_decoder(),
                cfg_scale=self.config.cfg,
            )
            self._pipe_config = GenerationConfig(
                height=self.config.height, width=self.config.width,
                num_frames=self.config.num_frames, fps=self.config.fps,
                seed=self.config.seed,
            )
        return self._pipeline_instance

    def _detect_checkpoint_version(self) -> bool:
        """Detect if the checkpoint is V2 (has video_aggregate_embed keys)."""
        import safetensors
        try:
            with safetensors.safe_open(self.config.checkpoint_path, framework="pt") as f:
                return "text_embedding_projection.video_aggregate_embed.weight" in f.keys()
        except Exception:
            return False

    def _load_text_encoder(self):
        """Load text encoder, auto-detecting V1 vs V2 checkpoint format."""
        if self._text_encoder is not None:
            return self._text_encoder

        self._is_v2_checkpoint = self._detect_checkpoint_version()

        if self._is_v2_checkpoint:
            print("[JianDou] Detected V2 checkpoint, loading AV text encoder...")
            from LTX_2_MLX.model.text_encoder.encoder import (
                create_av_text_encoder_v2_from_checkpoint,
                load_av_text_encoder_v2_weights,
            )
            self._text_encoder = create_av_text_encoder_v2_from_checkpoint(
                self.config.checkpoint_path,
            )
            load_av_text_encoder_v2_weights(self._text_encoder, self.config.checkpoint_path)
        else:
            print("[JianDou] Using V1 text encoder...")
            self._text_encoder = self._ledger.text_encoder()

        return self._text_encoder

    def _encode_prompt(self, prompt: str = ""):
        self._ensure_loaded()
        prompt = prompt or self.config.prompt
        if not prompt:
            return None, None

        gemma_path = self._ledger.gemma_path
        if not gemma_path or not os.path.isdir(gemma_path):
            print("[JianDou] Gemma path not found, using zero encoding")
            return self._zero_encoding()

        try:
            from transformers import AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(
                gemma_path, local_files_only=True,
            )
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            tokenizer.padding_side = "left"

            encoding = tokenizer(
                prompt, return_tensors="np", padding="max_length",
                truncation=True, max_length=1024,
            )
            input_ids = mx.array(encoding["input_ids"])
            attention_mask = mx.array(encoding["attention_mask"])
            num_tokens = int(attention_mask.sum())
            print(f"[JianDou] Tokenized: {num_tokens}/1024 tokens")

            # Ensure text encoder is loaded (auto-detects V1/V2 checkpoint)
            text_encoder = self._load_text_encoder()

            # Run Gemma forward pass to get all hidden states
            gemma = self._ledger.gemma()
            last_hidden, all_hidden_states = gemma(
                input_ids, attention_mask=attention_mask,
                output_hidden_states=True,
            )
            mx.eval(last_hidden)

            # Encode through text encoder
            output = text_encoder.encode_from_hidden_states(
                all_hidden_states, attention_mask,
            )

            # Extract video encoding (V1 returns VideoGemmaEncoderOutput,
            # V2 returns AudioVideoGemmaEncoderOutput; both have .video_encoding)
            embedding = output.video_encoding
            mask = output.attention_mask
            mx.eval(embedding)

            print(f"[JianDou] Text encoding: {embedding.shape}")
            return embedding, mask
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[JianDou] Encoding failed ({e}), using zero encoding")
            return self._zero_encoding()

    def _zero_encoding(self):
        # V2 checkpoints expect 4096-dim encoding; V1 expects 3840
        dim = 4096 if self._is_v2_checkpoint else 3840
        max_length = 256
        encoding = mx.zeros((1, max_length, dim), dtype=mx.float16 if self.config.fp16 else mx.float32)
        mask = mx.ones((1, max_length))
        return encoding, mask

    def _resolve_images(self):
        if not self.config.image_path:
            return None
        from LTX_2_MLX.pipelines.common import load_image_tensor
        return [load_image_tensor(
            self.config.image_path, self.config.height,
            self.config.width, self.config.to_mlx_dtype(),
        )]

    def _make_callback(self):
        if self.config.on_step is None and self.config.on_progress is None:
            return None
        def callback(*args):
            # LTX-2-MLX pipelines use two callback signatures:
            #   2-arg: callback(step, total)
            #   3-arg: callback(stage, step, total)
            if len(args) == 3 and isinstance(args[0], str):
                stage, step, total = args
            else:
                step, total = args[0], args[1]
                stage = ""
            if self.config.on_step:
                self.config.on_step(step, total)
            if self.config.on_progress:
                self.config.on_progress(step, total, stage)
        return callback

    def _ensure_loaded(self):
        if not self._loaded:
            raise SessionError("Model not loaded. Call load() or use as context manager.")


def create_session_from_preset(
    checkpoint_path: str, gemma_path: str,
    gen: GenerationConfig, engine: EngineConfig, **overrides,
) -> SessionConfig:
    import random
    return SessionConfig(
        checkpoint_path=checkpoint_path, gemma_path=gemma_path,
        model_version=engine.model_version, pipeline=engine.pipeline,
        fp16=engine.fp16, low_memory=engine.low_memory,
        width=overrides.get("width", gen.width),
        height=overrides.get("height", gen.height),
        fps=overrides.get("fps", gen.fps),
        steps=overrides.get("steps", gen.steps),
        cfg=overrides.get("cfg", gen.cfg),
        seed=overrides.get("seed", gen.seed) if gen.seed >= 0 else random.randint(0, 2**31 - 1),
        num_frames=int(gen.duration * gen.fps + 1),
    )
