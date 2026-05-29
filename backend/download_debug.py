"""Debug download connectivity via hf download."""
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

ENV = os.environ.copy()
ENV["HF_XET_HIGH_PERFORMANCE"] = "1"

from huggingface_hub import list_repo_files

# Test 1: list repo files
print("=== Test 1: list_repo_files ===")
try:
    files = list_repo_files("Lightricks/LTX-2")
    print(f"OK: {len(files)} files found")
except Exception as e:
    print(f"FAIL: {e}")

# Test 2: direct HTTP HEAD to a small file via mirror
print("\n=== Test 2: HTTP HEAD to small file (mirror) ===")
url = "https://hf-mirror.com/Lightricks/LTX-2/resolve/main/.gitattributes"
try:
    req = urllib.request.Request(url, method="HEAD")
    r = urllib.request.urlopen(req, timeout=10)
    print(f"Status: {r.status}")
    print(f"URL: {r.url[:100]}...")
except Exception as e:
    print(f"FAIL: {e}")

# Test 3: HTTP HEAD to safetensors via mirror
print("\n=== Test 3: HTTP HEAD to safetensors (mirror) ===")
url = "https://hf-mirror.com/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled.safetensors"
try:
    req = urllib.request.Request(url, method="HEAD")
    r = urllib.request.urlopen(req, timeout=10)
    print(f"Status: {r.status}")
    print(f"URL: {r.url[:120]}...")
except Exception as e:
    print(f"FAIL: {e}")

# Test 4: HTTP HEAD via official huggingface.co
print("\n=== Test 4: HTTP HEAD via official HF ===")
url = "https://huggingface.co/Lightricks/LTX-2/resolve/main/.gitattributes"
try:
    req = urllib.request.Request(url, method="HEAD")
    r = urllib.request.urlopen(req, timeout=10)
    print(f"Status: {r.status}")
except Exception as e:
    print(f"FAIL: {e}")

# Test 5: hf download small file via mirror
print("\n=== Test 5: hf download small file via mirror ===")
try:
    result = subprocess.run(
        ["hf", "download", "Lightricks/LTX-2", ".gitattributes", "--quiet"],
        env=ENV, capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"OK: {result.stdout.strip()}")
    else:
        print(f"FAIL: {result.stderr.strip()}")
except Exception as e:
    print(f"FAIL: {type(e).__name__}: {e}")

# Test 6: hf download via official HF
print("\n=== Test 6: hf download via official HF ===")
try:
    env_no_mirror = {k: v for k, v in ENV.items() if k != "HF_ENDPOINT"}
    result = subprocess.run(
        ["hf", "download", "Lightricks/LTX-2", ".gitattributes", "--quiet"],
        env=env_no_mirror, capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"OK: {result.stdout.strip()}")
    else:
        print(f"FAIL: {result.stderr.strip()}")
except Exception as e:
    print(f"FAIL: {type(e).__name__}: {e}")
