#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.qwen3-tts"
MAMBA_BIN="$ROOT_DIR/.tools/micromamba/bin/micromamba"

export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$ROOT_DIR/.mamba}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$ROOT_DIR/.cache}"
export MAMBA_PKGS_DIRS="${MAMBA_PKGS_DIRS:-$XDG_CACHE_HOME/mamba/pkgs}"

mkdir -p "$XDG_CACHE_HOME/mamba/proc" "$MAMBA_PKGS_DIRS"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ ! -x "$MAMBA_BIN" ]]; then
  echo "micromamba not found at $MAMBA_BIN" >&2
  echo "Run ./scripts/install_qwen3_tts.sh first." >&2
  exit 1
fi

MODEL_ID="${QWEN3_TTS_MODEL:-Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice}"
DEVICE="${QWEN3_TTS_DEVICE:-cpu}"
DTYPE="${QWEN3_TTS_DTYPE:-float32}"
IP="${QWEN3_TTS_IP:-127.0.0.1}"
PORT="${QWEN3_TTS_PORT:-8000}"

exec "$MAMBA_BIN" run -n qwen3-tts \
  qwen-tts-demo "$MODEL_ID" \
  --device "$DEVICE" \
  --dtype "$DTYPE" \
  --no-flash-attn \
  --ip "$IP" \
  --port "$PORT" \
  "$@"
