"""Quick audio smoke test — runs Qwen TTS on a short sentence to verify MPS is working."""
import sys
import time
from pathlib import Path

# Load .env before importing pipeline modules
sys.path.insert(0, str(Path(__file__).parent))
from ai_podcast_pipeline.utils import load_optional_env_file
load_optional_env_file(Path(".env"))

import os
print(f"Device  : {os.getenv('QWEN3_TTS_DEVICE', 'not set')}")
print(f"MPS fallback: {os.getenv('PYTORCH_ENABLE_MPS_FALLBACK', 'not set')}")

from ai_podcast_pipeline.audio import synthesize_qwen_clone_mp3

output = Path("output/test_audio.mp3")
output.parent.mkdir(exist_ok=True)

text = "This is a quick test of the Signal audio pipeline. If you can hear this, Qwen is working."

manifest = os.getenv("QWEN_PROFILE_MANIFEST", "")
model   = os.getenv("QWEN_TTS_MODEL", "")
clip_id = os.getenv("QWEN_REF_CLIP_ID") or None

print(f"\nGenerating ~2 sentence clip…")
t0 = time.monotonic()
try:
    synthesize_qwen_clone_mp3(
        profile_manifest_path=Path(manifest),
        model_id=model,
        text=text,
        output_path=output,
        ref_clip_id=clip_id,
        timeout=300,
    )
    elapsed = time.monotonic() - t0
    print(f"✓ Done in {elapsed:.1f}s — output: {output}")
except Exception as e:
    elapsed = time.monotonic() - t0
    print(f"✗ Failed after {elapsed:.1f}s: {e}")
