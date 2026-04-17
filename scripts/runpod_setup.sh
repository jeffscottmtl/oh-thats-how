#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# runpod_setup.sh — First-time setup for The Signal on a RunPod GPU pod
#
# Run this ONCE after uploading the-signal to /workspace/the-signal.
# Installs system packages, Python pipeline deps, and the Qwen3-TTS conda env.
#
# Expected pod config:
#   Template : RunPod PyTorch (Ubuntu 22.04 + CUDA 12.x)
#   GPU       : RTX 5090 (or any CUDA 12 GPU)
#   Volume    : Network volume mounted at /workspace  ← keeps env between sessions
#   Port      : 8765 exposed via HTTP proxy
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SIGNAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo ""
echo "  📡 The Signal — RunPod Setup"
echo "  ────────────────────────────────────"
echo "  Project root : $SIGNAL_DIR"
echo ""

# ── 1. System packages ────────────────────────────────────────────────────────
echo "  [1/4] Installing system packages…"
apt-get update -q
apt-get install -y -q sox ffmpeg git curl lsof

# ── 2. Python pipeline dependencies ──────────────────────────────────────────
echo "  [2/4] Installing Python pipeline dependencies…"
cd "$SIGNAL_DIR"
pip install -e . --quiet

# ── 3. Qwen3-TTS conda environment ───────────────────────────────────────────
echo "  [3/4] Installing Qwen3-TTS environment (~15 min first time)…"
bash "$SIGNAL_DIR/scripts/install_qwen3_tts.sh"

# ── 4. Pre-download the 1.7B model weights to the volume cache ────────────────
echo "  [4/4] Pre-downloading Qwen3-TTS-12Hz-1.7B-Base model weights…"
echo "        (this caches them to the network volume — skip on subsequent runs)"

MAMBA_BIN="$SIGNAL_DIR/.tools/micromamba/bin/micromamba"
export MAMBA_ROOT_PREFIX="$SIGNAL_DIR/.mamba"
export XDG_CACHE_HOME="$SIGNAL_DIR/.cache"

"$MAMBA_BIN" run -n qwen3-tts python - << 'PYEOF'
from huggingface_hub import snapshot_download
import os
print("  Downloading Qwen/Qwen3-TTS-12Hz-1.7B-Base …")
path = snapshot_download("Qwen/Qwen3-TTS-12Hz-1.7B-Base")
print(f"  ✓ Cached at: {path}")
PYEOF

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "  ✓ Setup complete."
echo ""
echo "  Next steps:"
echo "    1. Make sure .env.runpod exists (copy it from your Mac alongside .env)"
echo "    2. Run: bash scripts/runpod_start.sh"
echo "    3. Open the RunPod HTTP proxy URL for port 8765"
echo ""
