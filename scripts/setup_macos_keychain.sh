#!/usr/bin/env bash
set -euo pipefail

SERVICE_OPENAI="the-signal-openai-api-key"
SERVICE_EL="the-signal-elevenlabs-api-key"
SERVICE_VOICE="the-signal-elevenlabs-voice-id"

read -rsp "OpenAI API key: " OPENAI_KEY
echo
read -rsp "ElevenLabs API key: " ELEVENLABS_KEY
echo
read -rp "ElevenLabs Voice ID: " VOICE_ID

security add-generic-password -U -a "$USER" -s "$SERVICE_OPENAI" -w "$OPENAI_KEY" >/dev/null
security add-generic-password -U -a "$USER" -s "$SERVICE_EL" -w "$ELEVENLABS_KEY" >/dev/null
security add-generic-password -U -a "$USER" -s "$SERVICE_VOICE" -w "$VOICE_ID" >/dev/null

echo "Saved secrets in macOS Keychain."
echo "Use ./scripts/run_with_keychain_env.sh to run pipeline with exported env vars."
