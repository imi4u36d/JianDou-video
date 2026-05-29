"""Simple parallel model downloader via hf download with hf_transfer."""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
os.environ["NO_PROXY"] = "localhost,127.0.0.1,.local"
os.environ.pop("HF_ENDPOINT", None)

ENV = os.environ.copy()
ENV["HF_XET_HIGH_PERFORMANCE"] = "1"


def dl_file(repo, filename, label):
    print(f"[start] {label}")
    t0 = time.time()
    result = subprocess.run(
        ["hf", "download", repo, filename, "--quiet"],
        env=ENV, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"download failed: {result.stderr.strip()}")
    dt = time.time() - t0
    path = Path(result.stdout.strip())
    gb = path.stat().st_size / 1024**3 if path.is_file() else 0
    print(f"[done]  {label} ({gb:.1f} GB in {dt:.0f}s, {gb * 1024 / dt:.1f} MB/s)")
    return path


def dl_snapshot(repo, patterns, label):
    print(f"[start] {label}")
    t0 = time.time()
    cmd = ["hf", "download", repo, "--quiet"]
    for p in patterns:
        cmd.extend(["--include", p])
    result = subprocess.run(cmd, env=ENV, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"download failed: {result.stderr.strip()}")
    dt = time.time() - t0
    path = Path(result.stdout.strip())
    gb = sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1024**3 if path.is_dir() else 0
    print(f"[done]  {label} ({gb:.1f} GB in {dt:.0f}s)")
    return path


print("=" * 60)
print("JianDou-video Model Downloader")
print("hf download with hf_transfer")
print("=" * 60)

print("\n[1/2] Main model (~40GB)")
try:
    dl_file("Lightricks/LTX-2", "ltx-2-19b-distilled.safetensors", "Main model (~40GB)")
except Exception as e:
    print(f"[FAIL] Main model: {e}")

print("\n[2/2] Text encoder (12 shards, ~48GB)")
try:
    dl_snapshot(
        "Lightricks/LTX-2",
        ["text_encoder/diffusion_pytorch_model-*.safetensors"],
        "Text encoder (12 shards)",
    )
except Exception as e:
    print(f"[FAIL] Text encoder: {e}")

print("\nDone!")
