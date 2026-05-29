"""Simple download test via hf download with hf_transfer."""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

ENV = os.environ.copy()
ENV["HF_XET_HIGH_PERFORMANCE"] = "1"


def download_with_retry(repo, filename, max_retries=5):
    for attempt in range(max_retries):
        try:
            print(f"\n[{attempt + 1}/{max_retries}] Downloading {filename}...")
            result = subprocess.run(
                ["hf", "download", repo, filename, "--quiet"],
                env=ENV, capture_output=True, text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip())
            path = Path(result.stdout.strip())
            size_gb = path.stat().st_size / 1024**3 if path.is_file() else 0
            print(f"[OK] {filename} -> {size_gb:.2f} GB")
            return path
        except Exception as e:
            print(f"[FAIL] attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


if __name__ == "__main__":
    print("=== Test: downloading tokenizer (small file) ===")
    download_with_retry("Lightricks/LTX-2", "tokenizer/tokenizer_config.json")
    print("\nTest passed! Network is working.\n")

    print("=== Downloading text encoder shard 1/12 ===")
    download_with_retry(
        "Lightricks/LTX-2",
        "text_encoder/diffusion_pytorch_model-00001-of-00012.safetensors",
    )
