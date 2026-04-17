#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# runpod_start.sh — Start The Signal web server on RunPod
#
# Differences from launch.command:
#   • Binds to 0.0.0.0 so RunPod's HTTP proxy can reach it
#   • Sources .env.runpod to override Mac-specific settings with CUDA equivalents
#   • No browser open (headless pod)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SIGNAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SIGNAL_DIR"

# ── Robust env loader (handles unquoted values with spaces) ───────────────────
_load_env() {
  local file="$1"
  [ -f "$file" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue       # skip comments
    [[ -z "${line//[[:space:]]/}" ]] && continue       # skip blank lines
    [[ "$line" =~ ^([^=]+)=(.*)$ ]] || continue       # must have =
    local key="${BASH_REMATCH[1]}"
    local value="${BASH_REMATCH[2]}"
    value="${value#\"}" ; value="${value%\"}"          # strip double quotes
    value="${value#\'}" ; value="${value%\'}"          # strip single quotes
    export "$key=$value"
  done < "$file"
}

# ── Load base .env then apply RunPod CUDA overrides ──────────────────────────
_load_env ".env"

if [ ! -f ".env.runpod" ]; then
  echo "  ✗ .env.runpod not found. Copy it from your Mac alongside .env and try again."
  exit 1
fi
_load_env ".env.runpod"

PORT=${SIGNAL_PORT:-8765}

echo ""
echo "  📡 The Signal — RunPod"
echo "  ─────────────────────────────────────────────────────────"
echo "  GPU device  : ${QWEN3_TTS_DEVICE:-cuda}"
echo "  TTS model   : ${QWEN_TTS_MODEL}"
echo "  Port        : $PORT (accessible via RunPod HTTP proxy)"
echo "  Press Ctrl+C to stop."
echo ""

export PYTHONPATH="$SIGNAL_DIR:${PYTHONPATH:-}"

python -m uvicorn web.server:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --log-level warning

echo ""
echo "  Server stopped."
