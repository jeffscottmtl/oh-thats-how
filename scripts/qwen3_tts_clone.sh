#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# QWEN_TOOLS_ROOT can point to a different Signal install that has the
# micromamba environment already set up (e.g. "the-signal").
# Falls back to ROOT_DIR (this project) if not set.
TOOLS_ROOT="${QWEN_TOOLS_ROOT:-$ROOT_DIR}"

ENV_FILE="$ROOT_DIR/.env.qwen3-tts"
MAMBA_BIN="$TOOLS_ROOT/.tools/micromamba/bin/micromamba"

export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$TOOLS_ROOT/.mamba}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$TOOLS_ROOT/.cache}"
export MAMBA_PKGS_DIRS="${MAMBA_PKGS_DIRS:-$XDG_CACHE_HOME/mamba/pkgs}"

mkdir -p "$XDG_CACHE_HOME/mamba/proc" "$MAMBA_PKGS_DIRS"

if [[ ! -x "$MAMBA_BIN" ]]; then
  echo "micromamba not found at $MAMBA_BIN" >&2
  if [[ -z "${QWEN_TOOLS_ROOT:-}" ]]; then
    echo "Tip: set QWEN_TOOLS_ROOT to the Signal install that has micromamba, e.g.:" >&2
    echo "  export QWEN_TOOLS_ROOT=\"/Users/$USER/Downloads/the-signal\"" >&2
    echo "  or add QWEN_TOOLS_ROOT=... to your .env file" >&2
  fi
  exit 1
fi

exec "$MAMBA_BIN" run -n qwen3-tts \
  python "$ROOT_DIR/scripts/qwen3_tts_clone.py" \
  --env-file "$ENV_FILE" \
  "$@"
