#!/usr/bin/env bash
set -euo pipefail

OPENAI_API_KEY="$(security find-generic-password -a "$USER" -s the-signal-openai-api-key -w)"
ELEVENLABS_API_KEY="$(security find-generic-password -a "$USER" -s the-signal-elevenlabs-api-key -w)"
ELEVENLABS_VOICE_ID="$(security find-generic-password -a "$USER" -s the-signal-elevenlabs-voice-id -w)"

export OPENAI_API_KEY
export ELEVENLABS_API_KEY
export ELEVENLABS_VOICE_ID

python3 -m ai_podcast_pipeline run "$@"
