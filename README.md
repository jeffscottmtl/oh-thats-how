# The Signal v4 Pipeline

This project runs a deterministic weekly podcast production workflow for **The Signal**.

## What it produces
Per run, it generates:
- `The Signal – Month D, YYYY - Script.md`
- `The Signal – Month D, YYYY - Script.json`
- `The Signal – Month D, YYYY - Sources.json`
- `The Signal – Month D, YYYY - Cover.png`
- `The Signal – Month D, YYYY.mp3` (after confirmation, with embedded cover art)
- `The Signal – Month D, YYYY - Manifest.json`

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Audio metadata embedding uses `mutagen` when available, and falls back to `ffmpeg` if installed.

## API keys and secret handling
The pipeline only reads these values from environment variables:
- `OPENAI_API_KEY`
- `OPENAI_PROJECT_ID` (optional)
- `OPENAI_ORGANIZATION` (optional)
- `TTS_PROVIDER` (`qwen` or `elevenlabs`, default `qwen`)
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `ELEVENLABS_MODEL_ID` (optional, default `eleven_multilingual_v2`)
- `ELEVENLABS_STABILITY` (optional, default `0.35`)
- `ELEVENLABS_SIMILARITY_BOOST` (optional, default `0.8`)
- `ELEVENLABS_STYLE` (optional, default `0.55`)
- `ELEVENLABS_USE_SPEAKER_BOOST` (optional, default `true`)
- `ELEVENLABS_SPEED` (optional, default `1.0`)
- `QWEN_PROFILE_MANIFEST` (default `voice_profiles/jeff_v1/profile_manifest.csv`)
- `QWEN_TTS_MODEL` (default `Qwen/Qwen3-TTS-12Hz-0.6B-Base`)
- `QWEN_REF_CLIP_ID` (optional)
- `QWEN_TTS_LANGUAGE` (optional, default `English`)
- `QWEN_TTS_INSTRUCT` (optional style/prosody prompt)
- `QWEN_TTS_TEMPERATURE` (optional, default `0.72`)
- `QWEN_TTS_TOP_P` (optional, default `0.92`)
- `QWEN_TTS_TOP_K` (optional, default `45`)
- `QWEN_TTS_MAX_NEW_TOKENS` (optional, default `4096`)
- `QWEN_TTS_SPEED` (optional, default `1.0`)
- `QWEN_TTS_TIMEOUT_SECONDS` (optional, default `1800`)

Optional:
- `OPENAI_MODEL` (default: `gpt-4.1-mini`)

Audio provider policy:
- `qwen` is the primary/default provider for local generation.
- If `qwen` is selected and fails during a run, the pipeline automatically falls back to ElevenLabs when `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` are available.
- Set `TTS_PROVIDER=elevenlabs` only when you explicitly want cloud TTS as primary.

### Option A: shell env vars
```bash
export OPENAI_API_KEY='...'
export ELEVENLABS_API_KEY='...'
export ELEVENLABS_VOICE_ID='...'
export TTS_PROVIDER='qwen'
export QWEN_PROFILE_MANIFEST='voice_profiles/jeff_v1/profile_manifest.csv'
export QWEN_TTS_INSTRUCT='Warm, conversational, confident. Keep energy up with natural emphasis.'
```

### Option B: macOS Keychain helpers
```bash
./scripts/setup_macos_keychain.sh
./scripts/run_with_keychain_env.sh --output-dir ./output
```

## Run
```bash
python3 -m ai_podcast_pipeline run --output-dir ./output
```

Useful flags:
- `--allow-domain example.com` approve additional source domain (repeatable)
- `--stories 3` optional preferred count hint only (selection count is your manual choice)
- `--episode-number 1` override cover/audio episode number label (default: next inferred number)
- `--episode-date 2026-02-15` override episode date shown in filenames/cover and constrain candidates to that week (episode date minus 6 days through episode date)
- `--window-start 2026-01-01 --window-end 2026-01-31` constrain candidates to a custom date window (for month/quarter recaps)
- `--tts-provider qwen|elevenlabs` override current provider for this run
- `--qwen-profile-manifest /abs/path/profile_manifest.csv` override Qwen profile source
- `--qwen-model Qwen/Qwen3-TTS-12Hz-0.6B-Base` override Qwen model
- `--qwen-ref-clip-id clip_03` force a specific reference clip from profile manifest
- `--skip-audio` skip audio generation
- `--auto-confirm-audio` skip confirmation prompt
- `--log-level DEBUG|INFO|WARNING|ERROR` control logging verbosity (default: INFO)

## Test
```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## What changed from v3

### Bugs fixed
- **`canonical_url` stripped all query parameters** — broke Google News redirect URLs. Now only tracking params (`utm_*`, `fbclid`, `ref`, etc.) are stripped; functional params are preserved.
- **Wrong error class in `audio.py`** — `_embed_mp3_metadata` always raised `ElevenLabsError` even when called from the Qwen path. Fixed via an `error_cls` parameter so callers receive `QwenTTSError` or `ElevenLabsError` as appropriate.
- **`cover.py` unused variable** — `_ = episode_name` was a silent discard. The parameter is now documented as present for future extension.
- **`_blend()` return type** — returned a generic tuple from a generator expression instead of an explicit `tuple[int, int, int]`. Now uses explicit construction.
- **`parse_json_response` fragile fence stripping** — old logic stripped backtick chars incorrectly in some edge cases. Rewritten to find the opening fence line and closing fence reliably.
- **`load_optional_env_file` inline comments** — values containing ` #` were not comment-stripped. Fixed.
- **Unused `shortlist()` function in `scoring.py`** — dead code, removed.
- **Duplicate sort key** — `_score_sort_key` in `pipeline.py` and `_sort_key` in `scoring.py` were identical. Consolidated into `story_sort_key` exported from `scoring.py`.

### Performance
- **Parallel RSS feed fetching** — all ~40 feeds are now fetched concurrently using `ThreadPoolExecutor` (12 workers). Feed startup is dramatically faster.

### Reliability
- **OpenAI retry logic** — `llm.py` now retries on HTTP 429/5xx with exponential backoff (up to 2 retries).

### Observability
- **Structured logging** — all `print()` debug/info statements replaced with `logging` calls. Run with `--log-level DEBUG` for full detail. The pipeline summary is still printed to stdout for human readability.

### Code quality
- **`pipeline.py` broken into stages** — `run_pipeline()` was a 340-line monolith. It now delegates to `_stage_build_full_list`, `_stage_select_and_verify`, `_stage_generate_script`, `_stage_render_cover`, `_stage_audio`, each independently readable and testable.
- **Padding paragraphs moved to `constants.py`** as `PADDING_PARAGRAPHS` tuple.
- **`cover.py` cross-platform font search** — Linux font paths added as fallbacks.

### Tests
- Tests expanded from 3 files (~15 tests) to 8 files (122 tests).
- New: `test_utils.py`, `test_llm.py`, `test_ingest.py`.
- Improved: `test_scoring.py`, `test_script_writer.py`, `test_security.py`, `test_verification.py`, `test_pipeline_week_filter.py`, `test_artifacts.py`, `test_contracts.py`.
