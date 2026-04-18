from __future__ import annotations

import csv
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from .security import redact

logger = logging.getLogger(__name__)


class QwenTTSError(RuntimeError):
    pass


class AudioError(RuntimeError):
    """Generic audio error raised when the specific provider is not relevant."""
    pass


def _retime_mp3(
    output_path: Path,
    speed: float,
    source_label: str,
    error_cls: type[RuntimeError] = RuntimeError,
) -> None:
    """Re-encode the MP3 at the requested speed using ffmpeg atempo filter."""
    if abs(speed - 1.0) < 1e-6:
        return
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise error_cls(
            f"{source_label} speed control requires ffmpeg to be installed."
        )

    with NamedTemporaryFile("wb", suffix=".mp3", delete=False, dir=output_path.parent) as tmp:
        temp_output = Path(tmp.name)

    cmd = [
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(output_path),
        "-filter:a", f"atempo={speed:.6f}",
        "-codec:a", "libmp3lame", "-q:a", "2",
        str(temp_output),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        logger.debug("Re-timed MP3 to speed=%.2f via ffmpeg.", speed)
    except subprocess.CalledProcessError as exc:
        temp_output.unlink(missing_ok=True)
        raise error_cls(
            f"{source_label} speed control failed: {redact(exc.stderr.decode('utf-8', 'ignore'))}"
        ) from exc

    temp_output.replace(output_path)


def _embed_mp3_metadata(
    output_path: Path,
    cover_art_path: Path | None,
    episode_name: str | None,
    episode_number: int | None,
    episode_dt: datetime | None,
    error_cls: type[RuntimeError] = AudioError,
) -> None:
    """Embed ID3 metadata and cover art into output_path.

    Tries mutagen first, falls back to ffmpeg.
    The `error_cls` parameter lets callers receive provider-specific errors
    (ElevenLabsError, QwenTTSError) rather than the generic AudioError.
    """
    try:
        from mutagen.id3 import APIC, TALB, TDRC, TIT2, TRCK, TPE1, ID3, ID3NoHeaderError
        _embed_mp3_metadata_mutagen(
            output_path=output_path,
            cover_art_path=cover_art_path,
            episode_name=episode_name,
            episode_number=episode_number,
            episode_dt=episode_dt,
            error_cls=error_cls,
        )
    except ImportError:
        _embed_mp3_metadata_ffmpeg(
            output_path=output_path,
            cover_art_path=cover_art_path,
            episode_name=episode_name,
            episode_number=episode_number,
            episode_dt=episode_dt,
            error_cls=error_cls,
        )


def _embed_mp3_metadata_mutagen(
    output_path: Path,
    cover_art_path: Path | None,
    episode_name: str | None,
    episode_number: int | None,
    episode_dt: datetime | None,
    error_cls: type[RuntimeError] = AudioError,
) -> None:
    from mutagen.id3 import APIC, TALB, TDRC, TIT2, TRCK, TPE1, ID3, ID3NoHeaderError

    try:
        tags = ID3(output_path)
    except ID3NoHeaderError:
        tags = ID3()

    if episode_name:
        tags.delall("TIT2")
        tags.add(TIT2(encoding=3, text=episode_name))

    tags.delall("TPE1")
    tags.add(TPE1(encoding=3, text="Jeff Scott"))
    tags.delall("TALB")
    tags.add(TALB(encoding=3, text="The Signal"))

    if episode_number is not None:
        tags.delall("TRCK")
        tags.add(TRCK(encoding=3, text=str(episode_number)))

    if episode_dt is not None:
        tags.delall("TDRC")
        tags.add(TDRC(encoding=3, text=episode_dt.strftime("%Y-%m-%d")))

    if cover_art_path:
        if not cover_art_path.exists():
            raise error_cls(f"Cover art file does not exist: {cover_art_path}")
        mime = "image/png"
        if cover_art_path.suffix.lower() in {".jpg", ".jpeg"}:
            mime = "image/jpeg"
        tags.delall("APIC")
        tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=cover_art_path.read_bytes()))

    tags.save(output_path, v2_version=3)
    logger.debug("Embedded ID3 metadata via mutagen.")


def _embed_mp3_metadata_ffmpeg(
    output_path: Path,
    cover_art_path: Path | None,
    episode_name: str | None,
    episode_number: int | None,
    episode_dt: datetime | None,
    error_cls: type[RuntimeError] = AudioError,
) -> None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise error_cls(
            "MP3 metadata embedding requires either 'mutagen' or 'ffmpeg', but neither is available."
        )

    if cover_art_path and not cover_art_path.exists():
        raise error_cls(f"Cover art file does not exist: {cover_art_path}")

    with NamedTemporaryFile("wb", suffix=".mp3", delete=False, dir=output_path.parent) as tmp:
        temp_output = Path(tmp.name)

    cmd = [ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", str(output_path)]
    if cover_art_path:
        cmd.extend(["-i", str(cover_art_path)])

    cmd.extend(["-map", "0:a:0"])
    if cover_art_path:
        cmd.extend(["-map", "1:v:0", "-c:v", "mjpeg", "-disposition:v:0", "attached_pic"])

    cmd.extend(["-c:a", "copy", "-id3v2_version", "3"])

    if episode_name:
        cmd.extend(["-metadata", f"title={episode_name}"])
    cmd.extend(["-metadata", "artist=Jeff Scott", "-metadata", "album=The Signal"])
    if episode_number is not None:
        cmd.extend(["-metadata", f"track={episode_number}"])
    if episode_dt is not None:
        cmd.extend(["-metadata", f"date={episode_dt.strftime('%Y-%m-%d')}"])

    cmd.append(str(temp_output))

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        logger.debug("Embedded ID3 metadata via ffmpeg.")
    except subprocess.CalledProcessError as exc:
        temp_output.unlink(missing_ok=True)
        raise error_cls(
            f"ffmpeg metadata embedding failed: {redact(exc.stderr.decode('utf-8', 'ignore'))}"
        ) from exc

    temp_output.replace(output_path)


def _convert_wav_to_mp3(input_wav: Path, output_mp3: Path) -> None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise QwenTTSError("Qwen audio conversion requires 'ffmpeg' to be installed.")
    cmd = [
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(input_wav),
        "-codec:a", "libmp3lame", "-q:a", "2",
        str(output_mp3),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        logger.debug("Converted WAV to MP3 via ffmpeg.")
    except subprocess.CalledProcessError as exc:
        raise QwenTTSError(
            f"ffmpeg WAV→MP3 conversion failed: {redact(exc.stderr.decode('utf-8', 'ignore'))}"
        ) from exc


def _select_qwen_reference(
    profile_manifest_path: Path, ref_clip_id: str | None = None
) -> tuple[str, Path, str]:
    if not profile_manifest_path.exists():
        raise QwenTTSError(f"Qwen profile manifest not found: {profile_manifest_path}")

    with profile_manifest_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise QwenTTSError(f"Qwen profile manifest has no rows: {profile_manifest_path}")

    candidates: list[dict] = []
    for row in rows:
        clip_id = (row.get("clip_id") or "").strip()
        audio_path_raw = (row.get("audio_path") or "").strip()
        transcript = (row.get("transcript") or row.get("text") or "").strip()
        if not clip_id or not audio_path_raw or not transcript:
            continue

        passed = (row.get("passed") or "yes").strip().lower()
        if passed in {"no", "false", "0"}:
            continue

        audio_path = Path(audio_path_raw).expanduser()
        if not audio_path.exists():
            continue

        try:
            duration_s = float(row.get("duration_s") or 0.0)
        except (TypeError, ValueError):
            duration_s = 0.0

        try:
            rms_dbfs = float(row.get("rms_dbfs") or -18.0)
        except (TypeError, ValueError):
            rms_dbfs = -18.0

        candidates.append(
            {
                "clip_id": clip_id,
                "audio_path": audio_path,
                "transcript": transcript,
                "duration_s": duration_s,
                "rms_dbfs": rms_dbfs,
            }
        )

    if not candidates:
        raise QwenTTSError(
            "Qwen profile manifest has no usable rows with clip_id/audio_path/transcript and passed status."
        )

    if ref_clip_id:
        wanted = ref_clip_id.strip()
        for item in candidates:
            if item["clip_id"] == wanted:
                logger.debug("Using forced Qwen reference clip: %s", wanted)
                return item["clip_id"], item["audio_path"], item["transcript"]
        raise QwenTTSError(
            f"Requested Qwen ref clip id '{wanted}' was not found among usable clips in {profile_manifest_path}"
        )

    def _score(item: dict) -> tuple[float, str]:
        # Prefer mid-length, steady-loudness clips for stable clone prompts.
        duration = float(item["duration_s"])
        rms = float(item["rms_dbfs"])
        duration_penalty = abs((duration if duration > 0 else 6.0) - 6.0)
        loudness_penalty = abs(rms + 18.0) * 0.2
        return duration_penalty + loudness_penalty, str(item["clip_id"])

    chosen = sorted(candidates, key=_score)[0]
    logger.debug("Selected Qwen reference clip: %s", chosen["clip_id"])
    return chosen["clip_id"], chosen["audio_path"], chosen["transcript"]


def _preprocess_tts_text(text: str) -> str:
    """Preprocess script text so the TTS engine produces natural pauses and inflection.

    Qwen3-TTS responds to standard punctuation (periods, commas, ellipses, question
    marks) but does NOT pause for em dashes, markdown formatting, or other literary
    devices. This function converts script formatting into TTS-friendly punctuation:

    - Em dashes → ellipses (the strongest pause cue besides a period)
    - *italic emphasis* → CAPS (TTS reads caps slightly louder/stressed)
    - Ellipses already in text are preserved
    - Colons and semicolons get trailing pauses
    """
    import re as _re

    processed = text

    # 1. Strip markdown italic markers and CAPITALIZE for vocal stress
    #    *whether* → WHETHER  (TTS adds slight emphasis to caps)
    processed = _re.sub(r'\*([^*]+)\*', lambda m: m.group(1).upper(), processed)

    # 2. Convert em dashes to ellipses for pauses.
    #    "teams — even the ready ones — are nowhere close"
    #    → "teams... even the ready ones... are nowhere close"
    processed = _re.sub(r'\s*—\s*', '... ', processed)

    # 3. Normalize ellipses: ensure exactly three dots with trailing space
    processed = _re.sub(r'\.{2,}', '...', processed)
    processed = _re.sub(r'\.\.\.\s*', '... ', processed)

    # 4. Convert colons/semicolons to period-pause for clearer breaks
    #    "Here's the thing: most companies" → "Here's the thing. Most companies"
    processed = _re.sub(r':\s+(\w)', lambda m: '. ' + m.group(1).upper(), processed)
    processed = _re.sub(r';\s+(\w)', lambda m: '. ' + m.group(1).upper(), processed)

    # 5. Clean up any resulting double/triple spaces
    processed = _re.sub(r'  +', ' ', processed)

    # 6. Clean up awkward punctuation combos like "... ." or "... ,"
    processed = _re.sub(r'\.\.\.\s*\.', '...', processed)
    processed = _re.sub(r'\.\.\.\s*,', '...', processed)

    return processed.strip()


def _split_script_segments(text: str) -> list[str]:
    """Split a podcast script into natural segments for parallel TTS generation.

    Splits on double-newline paragraph boundaries, then merges very short
    paragraphs (< 20 words) with the previous segment to avoid choppy audio.
    Each segment is preprocessed for TTS delivery.
    """
    raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(raw_paragraphs) <= 1:
        return [_preprocess_tts_text(p) for p in (raw_paragraphs or [text])]

    segments: list[str] = []
    for para in raw_paragraphs:
        word_count = len(para.split())
        if segments and word_count < 20:
            # Merge short paragraphs with the previous segment
            segments[-1] = segments[-1] + "\n\n" + para
        else:
            segments.append(para)
    return [_preprocess_tts_text(s) for s in segments]


def _generate_segment_wav(
    segment_text: str,
    segment_idx: int,
    clone_script: Path,
    project_root: Path,
    model_id: str,
    selected_audio: Path,
    selected_transcript: str,
    language: str,
    instruct: str | None,
    temperature: float,
    top_p: float,
    top_k: int,
    max_new_tokens: int,
    timeout: int,
    output_dir: Path,
) -> Path:
    """Generate a single WAV segment. Called in parallel by the thread pool."""
    wav_path = output_dir / f"_segment_{segment_idx:03d}.wav"

    cmd = [
        str(clone_script),
        "--model", model_id,
        "--ref-audio", str(selected_audio),
        "--ref-text", selected_transcript,
        "--text", segment_text,
        "--language", language,
        "--output", str(wav_path),
        "--temperature", str(temperature),
        "--top-p", str(top_p),
        "--top-k", str(top_k),
        "--max-new-tokens", str(max_new_tokens),
    ]
    if instruct:
        cmd.extend(["--instruct", instruct])

    try:
        subprocess.run(
            cmd,
            cwd=str(project_root),
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        wav_path.unlink(missing_ok=True)
        raise QwenTTSError(
            f"Segment {segment_idx} timed out after {timeout}s"
        ) from exc
    except subprocess.CalledProcessError as exc:
        wav_path.unlink(missing_ok=True)
        details = (exc.stderr or exc.stdout or "").strip()
        raise QwenTTSError(
            f"Segment {segment_idx} failed: {redact(details)}"
        ) from exc

    if not wav_path.exists():
        raise QwenTTSError(f"Segment {segment_idx} produced no output WAV")

    return wav_path


def _generate_silence_wav(output_path: Path, duration_ms: int = 600, sample_rate: int = 24000) -> Path:
    """Generate a silent WAV file for inter-segment pauses."""
    import wave as _wave
    num_samples = int(sample_rate * duration_ms / 1000)
    silence = b"\x00\x00" * num_samples  # 16-bit silence
    with _wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(silence)
    return output_path


def _concatenate_wavs(
    wav_paths: list[Path],
    output_wav: Path,
    pause_between_ms: int = 600,
) -> None:
    """Concatenate multiple WAV files with silence gaps between segments."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise QwenTTSError("ffmpeg is required for WAV concatenation")

    # If we have multiple segments and a pause duration, interleave silence
    if len(wav_paths) > 1 and pause_between_ms > 0:
        silence_path = output_wav.parent / "_silence_pad.wav"
        _generate_silence_wav(silence_path, duration_ms=pause_between_ms)

        interleaved: list[Path] = []
        for i, wav in enumerate(wav_paths):
            interleaved.append(wav)
            if i < len(wav_paths) - 1:
                interleaved.append(silence_path)
        paths_to_concat = interleaved
    else:
        paths_to_concat = wav_paths

    # Build ffmpeg concat filter
    filter_parts = []
    input_args = []
    for i, wav in enumerate(paths_to_concat):
        input_args.extend(["-i", str(wav)])
        filter_parts.append(f"[{i}:a:0]")

    filter_str = "".join(filter_parts) + f"concat=n={len(paths_to_concat)}:v=0:a=1[out]"

    cmd = [
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        *input_args,
        "-filter_complex", filter_str,
        "-map", "[out]",
        str(output_wav),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise QwenTTSError(
            f"WAV concatenation failed: {exc.stderr.decode('utf-8', 'ignore')}"
        ) from exc
    finally:
        # Clean up silence pad
        silence_path = output_wav.parent / "_silence_pad.wav"
        silence_path.unlink(missing_ok=True)


def synthesize_qwen_clone_mp3(
    profile_manifest_path: Path,
    model_id: str,
    text: str,
    output_path: Path,
    cover_art_path: Path | None = None,
    episode_name: str | None = None,
    episode_number: int | None = None,
    episode_dt: datetime | None = None,
    ref_clip_id: str | None = None,
    language: str = "English",
    instruct: str | None = None,
    temperature: float = 0.72,
    top_p: float = 0.92,
    top_k: int = 45,
    max_new_tokens: int = 4096,
    speed: float = 1.0,
    timeout: int = 1800,
    segmented: bool = True,
) -> None:
    """Synthesize speech via local Qwen3-TTS clone and write an MP3 with embedded metadata.

    When segmented=True, splits the script into paragraph-level segments and
    passes them all to a single clone process (model loads once, generates each
    segment sequentially). This avoids the ~30-60s model reload per call.
    """
    project_root = Path(__file__).resolve().parent.parent
    clone_script = project_root / "scripts" / "qwen3_tts_clone.sh"
    if not clone_script.exists():
        raise QwenTTSError(f"Qwen clone helper script not found: {clone_script}")

    selected_clip_id, selected_audio, selected_transcript = _select_qwen_reference(
        profile_manifest_path=profile_manifest_path,
        ref_clip_id=ref_clip_id,
    )

    segments = _split_script_segments(text) if segmented else [_preprocess_tts_text(text)]
    use_segments_mode = len(segments) > 1

    if use_segments_mode:
        # Write segments to a temp file (delimited by ---) for the clone script
        tmp_dir = output_path.parent / "_tts_segments"
        tmp_dir.mkdir(exist_ok=True)

        segments_file = tmp_dir / "segments.txt"
        segments_file.write_text("\n---\n".join(segments), encoding="utf-8")

        wav_stem = tmp_dir / "seg.wav"

        cmd = [
            str(clone_script),
            "--model", model_id,
            "--ref-audio", str(selected_audio),
            "--ref-text", selected_transcript,
            "--text", "unused",  # required arg but ignored when --segments-file is set
            "--language", language,
            "--output", str(wav_stem),
            "--segments-file", str(segments_file),
            "--temperature", str(temperature),
            "--top-p", str(top_p),
            "--top-k", str(top_k),
            "--max-new-tokens", str(max_new_tokens),
        ]
        if instruct:
            cmd.extend(["--instruct", instruct])

        logger.info(
            "Synthesizing %d segments via Qwen3-TTS (model=%s, clip=%s, single model load)…",
            len(segments), model_id, selected_clip_id,
        )
        try:
            subprocess.run(
                cmd,
                cwd=str(project_root),
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise QwenTTSError(
                f"Segmented generation timed out after {timeout}s"
            ) from exc
        except subprocess.CalledProcessError as exc:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            details = (exc.stderr or exc.stdout or "").strip()
            raise QwenTTSError(
                f"Segmented generation failed: {redact(details)}"
            ) from exc

        # Collect numbered segment WAVs in order
        wav_paths = sorted(tmp_dir.glob("seg_*.wav"))
        if len(wav_paths) != len(segments):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise QwenTTSError(
                f"Expected {len(segments)} segment WAVs, got {len(wav_paths)}"
            )

        # Concatenate
        combined_wav = tmp_dir / "_combined.wav"
        _concatenate_wavs(wav_paths, combined_wav)

        try:
            _convert_wav_to_mp3(combined_wav, output_path)
            _retime_mp3(output_path, speed=speed, source_label="Qwen", error_cls=QwenTTSError)
            _embed_mp3_metadata(
                output_path=output_path,
                cover_art_path=cover_art_path,
                episode_name=episode_name,
                episode_number=episode_number,
                episode_dt=episode_dt,
                error_cls=QwenTTSError,
            )
            logger.info("Qwen audio written to %s (%d segments, single model load).", output_path.name, len(segments))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    else:
        # Single-shot path (short text or segmented=False)
        with NamedTemporaryFile("wb", suffix=".wav", delete=False) as tmp_wav:
            wav_path = Path(tmp_wav.name)
        wav_path.unlink(missing_ok=True)

        cmd = [
            str(clone_script),
            "--model", model_id,
            "--ref-audio", str(selected_audio),
            "--ref-text", selected_transcript,
            "--text", text,
            "--language", language,
            "--output", str(wav_path),
            "--temperature", str(temperature),
            "--top-p", str(top_p),
            "--top-k", str(top_k),
            "--max-new-tokens", str(max_new_tokens),
        ]
        if instruct:
            cmd.extend(["--instruct", instruct])

        logger.info(
            "Synthesizing audio via Qwen3-TTS (model=%s, clip=%s, timeout=%ds)…",
            model_id, selected_clip_id, timeout,
        )
        try:
            subprocess.run(
                cmd,
                cwd=str(project_root),
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            wav_path.unlink(missing_ok=True)
            raise QwenTTSError(
                f"Qwen clone generation timed out after {timeout}s (clip={selected_clip_id})"
            ) from exc
        except subprocess.CalledProcessError as exc:
            wav_path.unlink(missing_ok=True)
            details = (exc.stderr or exc.stdout or "").strip()
            raise QwenTTSError(
                f"Qwen clone generation failed (clip={selected_clip_id}): {redact(details)}"
            ) from exc

        if not wav_path.exists():
            raise QwenTTSError(
                f"Qwen clone command completed but no output WAV was produced (expected: {wav_path})"
            )

        try:
            _convert_wav_to_mp3(wav_path, output_path)
            _retime_mp3(output_path, speed=speed, source_label="Qwen", error_cls=QwenTTSError)
            _embed_mp3_metadata(
                output_path=output_path,
                cover_art_path=cover_art_path,
                episode_name=episode_name,
                episode_number=episode_number,
                episode_dt=episode_dt,
                error_cls=QwenTTSError,
            )
            logger.info("Qwen audio written to %s.", output_path.name)
        finally:
            wav_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Fish Audio S2 TTS provider
# ---------------------------------------------------------------------------

class FishAudioError(RuntimeError):
    pass


def synthesize_fish_audio_mp3(
    api_key: str,
    text: str,
    output_path: Path,
    voice_id: str | None = None,
    reference_audio_path: Path | None = None,
    reference_transcript: str | None = None,
    speed: float = 1.0,
    cover_art_path: Path | None = None,
    episode_name: str | None = None,
    episode_number: int | None = None,
    episode_dt: datetime | None = None,
    timeout: int = 600,
) -> None:
    """Synthesize speech via Fish Audio S2 and write an MP3 with embedded metadata.

    Uses either a pre-registered voice model (voice_id) or inline reference audio
    for zero-shot voice cloning. If both are provided, voice_id takes precedence.
    """
    try:
        from fish_audio_sdk import Session, TTSRequest, ReferenceAudio, Prosody
    except ImportError as exc:
        raise FishAudioError(
            "fish-audio-sdk is required for Fish Audio TTS. "
            "Install with: pip install fish-audio-sdk"
        ) from exc

    session = Session(api_key)

    # Build references list for inline cloning (if no voice_id)
    references = []
    if not voice_id and reference_audio_path:
        ref_path = Path(reference_audio_path)
        if not ref_path.exists():
            raise FishAudioError(f"Reference audio file not found: {ref_path}")
        ref_bytes = ref_path.read_bytes()
        references.append(ReferenceAudio(
            audio=ref_bytes,
            text=reference_transcript or "",
        ))

    # Preprocess text for TTS (same as other providers)
    tts_text = _preprocess_tts_text(text)

    prosody = Prosody(speed=speed) if abs(speed - 1.0) > 1e-6 else None

    request = TTSRequest(
        text=tts_text,
        reference_id=voice_id or None,
        references=references,
        format="mp3",
        mp3_bitrate=128,
        latency="normal",
        normalize=True,
        prosody=prosody,
    )

    logger.info("Generating audio via Fish Audio S2 (voice=%s)…", voice_id or "inline-ref")
    try:
        audio_chunks = session.tts(request)
        audio_data = b"".join(audio_chunks)
    except Exception as exc:
        raise FishAudioError(f"Fish Audio TTS failed: {exc}") from exc

    if not audio_data or len(audio_data) < 100:
        raise FishAudioError("Fish Audio returned empty or invalid audio data")

    output_path.write_bytes(audio_data)
    logger.info("Fish Audio raw MP3 written (%d bytes).", len(audio_data))

    # Speed adjustment via ffmpeg (if prosody wasn't available or for fine-tuning)
    # Fish Audio handles speed via prosody, so this is a no-op unless needed
    # _retime_mp3(output_path, speed=speed, source_label="FishAudio", error_cls=FishAudioError)

    _embed_mp3_metadata(
        output_path=output_path,
        cover_art_path=cover_art_path,
        episode_name=episode_name,
        episode_number=episode_number,
        episode_dt=episode_dt,
        error_cls=FishAudioError,
    )
    logger.info("Fish Audio episode written to %s.", output_path.name)
