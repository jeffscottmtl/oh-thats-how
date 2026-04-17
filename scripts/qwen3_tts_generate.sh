#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.qwen3-tts"
MAMBA_BIN="$ROOT_DIR/.tools/micromamba/bin/micromamba"

export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$ROOT_DIR/.mamba}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$ROOT_DIR/.cache}"
export MAMBA_PKGS_DIRS="${MAMBA_PKGS_DIRS:-$XDG_CACHE_HOME/mamba/pkgs}"

mkdir -p "$XDG_CACHE_HOME/mamba/proc" "$MAMBA_PKGS_DIRS"

if [[ ! -x "$MAMBA_BIN" ]]; then
  echo "micromamba not found at $MAMBA_BIN" >&2
  echo "Run ./scripts/install_qwen3_tts.sh first." >&2
  exit 1
fi

exec "$MAMBA_BIN" run -n qwen3-tts \
  python "$ROOT_DIR/scripts/qwen3_tts_generate.py" \
  --env-file "$ENV_FILE" \
  "$@"
