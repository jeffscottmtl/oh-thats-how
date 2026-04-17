#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="$ROOT_DIR/.tools/micromamba"
MAMBA_BIN="$TOOLS_DIR/bin/micromamba"
REPO_DIR="$ROOT_DIR/third_party/Qwen3-TTS"

export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$ROOT_DIR/.mamba}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$ROOT_DIR/.cache}"
export MAMBA_PKGS_DIRS="${MAMBA_PKGS_DIRS:-$XDG_CACHE_HOME/mamba/pkgs}"

mkdir -p "$TOOLS_DIR" "$XDG_CACHE_HOME/mamba/proc" "$MAMBA_PKGS_DIRS" "$ROOT_DIR/third_party"

if [[ ! -x "$MAMBA_BIN" ]]; then
  case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) MICRO_URL="https://micro.mamba.pm/api/micromamba/osx-arm64/latest" ;;
    Darwin-x86_64) MICRO_URL="https://micro.mamba.pm/api/micromamba/osx-64/latest" ;;
    Linux-x86_64) MICRO_URL="https://micro.mamba.pm/api/micromamba/linux-64/latest" ;;
    Linux-aarch64) MICRO_URL="https://micro.mamba.pm/api/micromamba/linux-aarch64/latest" ;;
    *)
      echo "Unsupported platform for automatic micromamba download: $(uname -s)-$(uname -m)" >&2
      exit 1
      ;;
  esac
  curl -Ls "$MICRO_URL" | tar -xvj -C "$TOOLS_DIR"
fi

if [[ ! -d "$REPO_DIR/.git" ]]; then
  git clone https://github.com/QwenLM/Qwen3-TTS.git "$REPO_DIR"
fi

"$MAMBA_BIN" create -y -n qwen3-tts python=3.12 pip
"$MAMBA_BIN" install -y -n qwen3-tts -c conda-forge sox
"$MAMBA_BIN" run -n qwen3-tts pip install -e "$REPO_DIR"

echo "Qwen3-TTS is installed in env: $MAMBA_ROOT_PREFIX/envs/qwen3-tts"
echo "Next:"
echo "  1) cp .env.qwen3-tts.example .env.qwen3-tts"
echo "  2) ./scripts/qwen3_tts_demo.sh"
