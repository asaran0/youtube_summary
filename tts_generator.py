"""
tts_generator.py — Generate Hindi speech from transcript text (fully offline).

Two backends are supported (priority order):

  1. MMS-TTS  (Meta Massively Multilingual Speech)
       Model : facebook/mms-tts-hin  (~500 MB, auto-downloaded once)
       Quality: ★★★★☆  — neural, natural-sounding Hindi
       Speed  : medium  (uses Apple MPS on M1)
       Needs  : transformers, torch

  2. macOS built-in Lekha voice  (fallback)
       Model : Apple Neural TTS, built-in to macOS
       Quality: ★★★☆☆  — good, available with zero setup
       Speed  : fast
       Needs  : nothing extra

Configure which backend to use in config.py  →  TTS_BACKEND

The module takes the selected transcript chunks, generates one WAV per chunk,
then stitches them together with short natural pauses between sentences.
The final file  temp/tts_audio.wav  is used as the video's audio track.
"""

import os
import hashlib
import subprocess
import tempfile
import numpy as np

import config
from utils import get_logger, ensure_dirs

log = get_logger("tts")


# ─────────────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────────────

def generate_tts_audio(selected_chunks: list[dict]) -> str:
    """
    Generate Hindi TTS audio for all selected chunks.

    Parameters
    ----------
    selected_chunks : list of chunk dicts (output of summarizer)

    Returns
    -------
    Path to the final stitched WAV file  (temp/tts_audio.wav)
    """
    ensure_dirs(config.TEMP_DIR)

    # Extract ordered text from chunks
    texts = [chunk["text"].strip() for chunk in selected_chunks if chunk["text"].strip()]
    cache_key = _tts_cache_key(texts)
    output_path = os.path.join(config.TEMP_DIR, f"tts_audio_{cache_key}.wav")
    timings_path = os.path.join(config.TEMP_DIR, f"tts_timings_{cache_key}.json")

    if os.path.exists(output_path) and os.path.exists(timings_path):
        log.info("TTS audio already generated, reusing cached file.")
        if _apply_cached_timings(selected_chunks, timings_path):
            return output_path

    log.info("Generating TTS for %d text segments …", len(texts))
    log.info("Backend: %s", config.TTS_BACKEND)

    if config.TTS_BACKEND == "mms":
        durations = _generate_mms(texts, output_path)
    elif config.TTS_BACKEND == "macos":
        durations = _generate_macos(texts, output_path)
    else:
        raise ValueError(
            f"Unknown TTS_BACKEND '{config.TTS_BACKEND}'. "
            "Choose 'mms' or 'macos' in config.py"
        )

    _retime_chunks_for_tts(selected_chunks, durations)
    _write_timings(selected_chunks, timings_path)
    log.info("TTS audio saved → %s", output_path)
    return output_path


def get_tts_duration(tts_wav_path: str) -> float:
    """Return duration of generated TTS audio in seconds."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        tts_wav_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


# ─────────────────────────────────────────────────────────────
#  BACKEND 1 — META MMS-TTS  (best quality, offline after first download)
# ─────────────────────────────────────────────────────────────

def _generate_mms(texts: list[str], output_path: str) -> list[float]:
    """
    Use facebook/mms-tts-hin via HuggingFace Transformers.
    Model is downloaded once (~500 MB) and cached locally.
    Subsequent runs are fully offline.
    """
    import torch
    from transformers import VitsModel, AutoTokenizer
    import scipy.io.wavfile as wavfile

    log.info("Loading MMS-TTS model (first run downloads model files) …")
    model_id = config.MMS_TTS_MODEL_IDS.get(config.LANGUAGE, "facebook/mms-tts-hin")

    tokenizer = AutoTokenizer.from_pretrained(model_id)

    # Use MPS on M1 if available, else CPU
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    log.info("TTS device: %s", device)

    model = VitsModel.from_pretrained(model_id).to(device)
    model.eval()

    sample_rate = model.config.sampling_rate   # typically 16000 Hz
    pause_samples = int(sample_rate * config.TTS_PAUSE_BETWEEN_SEGMENTS)

    all_audio = []
    timings = []

    for i, text in enumerate(texts, 1):
        log.info("  TTS %d/%d: %s …", i, len(texts), text[:50])
        text = _clean_text_for_tts(text)
        if not text:
            continue

        try:
            inputs = tokenizer(text, return_tensors="pt").to(device)

            with torch.no_grad():
                output = model(**inputs)

            # Move to CPU numpy
            waveform = output.waveform.squeeze().cpu().numpy()
            all_audio.append(waveform)
            dur = len(waveform) / sample_rate
            timings.append({
                "duration": dur,
                "phrases": [{"text": text, "start": 0.0, "end": dur}],
            })

            # Add a short natural pause between segments
            pause = np.zeros(pause_samples, dtype=np.float32)
            all_audio.append(pause)

        except Exception as e:
            log.warning("TTS failed for segment %d: %s", i, e)
            # Insert silence of approximate duration instead
            silence = np.zeros(int(sample_rate * 2), dtype=np.float32)
            all_audio.append(silence)
            timings.append({
                "duration": 2.0,
                "phrases": [{"text": text, "start": 0.0, "end": 2.0}],
            })

    if not all_audio:
        raise RuntimeError("TTS produced no audio output")

    combined = np.concatenate(all_audio).astype(np.float32)

    # Normalise volume to avoid clipping
    max_val = np.max(np.abs(combined))
    if max_val > 0:
        combined = combined / max_val * 0.85

    # Convert to int16 for WAV
    combined_int16 = (combined * 32767).astype(np.int16)

    # Save temporary WAV
    tmp_wav = os.path.join(config.TEMP_DIR, "tts_raw.wav")
    wavfile.write(tmp_wav, sample_rate, combined_int16)

    # Re-encode at 44100 Hz for compatibility with moviepy/ffmpeg
    resampled_wav = os.path.join(config.TEMP_DIR, "tts_mms_resampled.wav")
    _resample_wav(tmp_wav, resampled_wav, target_rate=44100)
    _polish_audio(resampled_wav, output_path)
    log.info("MMS-TTS generation complete.")
    return timings


# ─────────────────────────────────────────────────────────────
#  BACKEND 2 — macOS BUILT-IN VOICE  (Lekha, zero setup)
# ─────────────────────────────────────────────────────────────

def _generate_macos(texts: list[str], output_path: str) -> list[float]:
    """
    Use macOS built-in 'say' command with the Lekha Hindi voice.
    Lekha is a neural TTS voice included in macOS — no download needed.

    To see all available voices:
        say -v '?'   |   grep -i hindi
    """
    voice = config.MACOS_TTS_VOICE

    # Verify the voice exists
    result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
    available = result.stdout + result.stderr
    if voice.lower() not in available.lower():
        fallback = config.MACOS_TTS_VOICES.get(config.LANGUAGE, "Lekha")
        log.warning("Voice '%s' not found. Trying '%s' …", voice, fallback)
        voice = fallback
        if voice.lower() not in available.lower():
            log.warning("Fallback voice not found either. Using default system voice.")
            voice = None

    clip_paths = []
    pause_after = []
    timings = []
    sample_rate = 44100
    phrase_index = 0

    for i, text in enumerate(texts, 1):
        log.info("  TTS %d/%d: %s …", i, len(texts), text[:50])
        text = _clean_text_for_tts(text)
        if not text:
            continue

        phrases = _split_text_for_voice(text)
        chunk_duration = 0.0
        phrase_timings = []
        for phrase_num, phrase in enumerate(phrases):
            phrase_index += 1
            aiff_path = os.path.join(config.TEMP_DIR, f"tts_chunk_{phrase_index:04d}.aiff")
            wav_path  = os.path.join(config.TEMP_DIR, f"tts_chunk_{phrase_index:04d}.wav")

            cmd = ["say", "-o", aiff_path, "-r", str(config.MACOS_TTS_RATE)]
            if voice:
                cmd += ["-v", voice]
            cmd.append(phrase)

            try:
                subprocess.run(cmd, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                log.warning("'say' failed for segment %d phrase %d: %s", i, phrase_num + 1, e)
                continue

            subprocess.run(
                ["ffmpeg", "-y", "-i", aiff_path,
                 "-ar", str(sample_rate), "-ac", "1", wav_path],
                check=True, capture_output=True
            )
            os.remove(aiff_path)

            clip_dur = get_tts_duration(wav_path)
            phrase_start = chunk_duration
            phrase_timings.append({
                "text": phrase,
                "start": phrase_start,
                "end": phrase_start + clip_dur,
            })
            inner_pause = (
                config.TTS_PAUSE_BETWEEN_PHRASES
                if phrase_num < len(phrases) - 1
                else config.TTS_PAUSE_BETWEEN_SEGMENTS
            )
            chunk_duration += clip_dur
            if phrase_num < len(phrases) - 1:
                chunk_duration += inner_pause

            clip_paths.append(wav_path)
            pause_after.append(inner_pause)

        if chunk_duration > 0:
            timings.append({
                "duration": chunk_duration,
                "phrases": phrase_timings,
            })

    if not clip_paths:
        raise RuntimeError("macOS TTS produced no audio output")

    raw_output = os.path.join(config.TEMP_DIR, "tts_macos_raw.wav")
    _concat_wav_clips_with_pauses(clip_paths, pause_after, raw_output, sample_rate)
    _polish_audio(raw_output, output_path)

    # Remove individual clips
    for p in clip_paths:
        if os.path.exists(p):
            os.remove(p)

    log.info("macOS TTS generation complete.")
    return timings


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

def _clean_text_for_tts(text: str) -> str:
    """
    Clean text before sending to TTS engine.
    Removes timestamps, URLs, special symbols, excess whitespace.
    """
    import re
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove common noise markers whisper sometimes adds
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    # Remove repeated punctuation
    text = re.sub(r"[।\.]{2,}", "।", text)
    # Clean whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_text_for_voice(text: str, max_chars: int = 180) -> list[str]:
    """Split long narration into more natural speakable phrases."""
    import re
    text = _clean_text_for_tts(text)
    pieces = [p.strip() for p in re.split(r"(?<=[।.!?])\s+", text) if p.strip()]
    if len(pieces) <= 1 and len(text) <= max_chars:
        return [text]

    phrases = []
    for piece in pieces or [text]:
        if len(piece) <= max_chars:
            phrases.append(piece)
            continue
        words = piece.split()
        current = []
        for word in words:
            trial = " ".join(current + [word])
            if current and len(trial) > max_chars:
                phrases.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            phrases.append(" ".join(current))
    return phrases


def _tts_cache_key(texts: list[str]) -> str:
    payload = "\n".join([
        "tts-cache-v3",
        config.TTS_BACKEND,
        config.LANGUAGE,
        config.MACOS_TTS_VOICE,
        str(config.MACOS_TTS_RATE),
        str(config.TTS_PAUSE_BETWEEN_SEGMENTS),
        str(config.TTS_PAUSE_BETWEEN_PHRASES),
        str(config.AUDIO_POST_PROCESSING),
        config.AUDIO_FILTER,
        "\n".join(texts),
    ])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _resample_wav(input_wav: str, output_wav: str, target_rate: int = 44100) -> None:
    """Resample a WAV file to target_rate Hz using ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_wav,
         "-ar", str(target_rate), "-ac", "1", output_wav],
        check=True, capture_output=True
    )


def _polish_audio(input_wav: str, output_wav: str) -> None:
    """Apply light cleanup, compression and loudness normalization."""
    if not config.AUDIO_POST_PROCESSING:
        if input_wav != output_wav:
            subprocess.run(["ffmpeg", "-y", "-i", input_wav, output_wav], check=True, capture_output=True)
        return

    cmd = [
        "ffmpeg", "-y",
        "-i", input_wav,
        "-af", config.AUDIO_FILTER,
        "-ar", "44100",
        "-ac", "1",
        output_wav,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _concat_wav_clips(
    clip_paths: list[str],
    output_path: str,
    pause_sec: float,
    sample_rate: int,
) -> None:
    """
    Concatenate WAV clips with a short silence between each using scipy/numpy.
    Falls back to ffmpeg concat if scipy is unavailable.
    """
    try:
        import scipy.io.wavfile as wavfile
        _concat_with_numpy(clip_paths, output_path, pause_sec, sample_rate)
    except ImportError:
        _concat_with_ffmpeg(clip_paths, output_path, pause_sec)


def _concat_wav_clips_with_pauses(
    clip_paths: list[str],
    pause_after: list[float],
    output_path: str,
    sample_rate: int,
) -> None:
    """Concatenate mono WAV clips with per-clip pause durations."""
    import wave

    audio_parts = []
    for path, pause_sec in zip(clip_paths, pause_after):
        with wave.open(path, "rb") as wav:
            frames = wav.readframes(wav.getnframes())
            data = np.frombuffer(frames, dtype=np.int16)
        audio_parts.append(data)
        if pause_sec > 0:
            audio_parts.append(np.zeros(int(sample_rate * pause_sec), dtype=np.int16))

    combined = np.concatenate(audio_parts) if audio_parts else np.zeros(1, dtype=np.int16)
    with wave.open(output_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(combined.tobytes())


def _concat_with_numpy(
    clip_paths: list[str],
    output_path: str,
    pause_sec: float,
    sample_rate: int,
) -> None:
    """Concatenate WAV clips using numpy for precise silence insertion."""
    import scipy.io.wavfile as wavfile

    pause_samples = int(sample_rate * pause_sec)
    pause = np.zeros(pause_samples, dtype=np.int16)

    all_audio = []
    for path in clip_paths:
        rate, data = wavfile.read(path)
        if data.ndim > 1:
            data = data[:, 0]   # take left channel if stereo
        if rate != sample_rate:
            # Basic resample (not ideal, but ffmpeg handles quality resampling)
            pass
        all_audio.append(data.astype(np.int16))
        all_audio.append(pause)

    combined = np.concatenate(all_audio)
    wavfile.write(output_path, sample_rate, combined)


def _concat_with_ffmpeg(
    clip_paths: list[str],
    output_path: str,
    pause_sec: float,
) -> None:
    """Concatenate WAVs using ffmpeg concat filter (scipy not available)."""
    # Build a complex filter that interleaves clips with silence
    inputs  = []
    filters = []
    for i, path in enumerate(clip_paths):
        inputs += ["-i", path]
        filters.append(f"[{i}:a]")

    # Build concat filter
    n = len(clip_paths)
    filter_str = "".join(filters) + f"concat=n={n}:v=0:a=1[outa]"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_str,
        "-map", "[outa]",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _retime_chunks_for_tts(chunks: list[dict], timings: list) -> None:
    """Replace original-video timings with generated narration timings."""
    current = 0.0
    pause = config.TTS_PAUSE_BETWEEN_SEGMENTS
    timing_iter = iter(timings)

    for chunk in chunks:
        if not chunk.get("text", "").strip():
            continue
        timing = next(timing_iter, None)
        if isinstance(timing, dict):
            dur = max(timing.get("duration", 0.0), 0.2)
            phrases = timing.get("phrases", [])
        else:
            dur = max(timing or chunk.get("new_end", 0) - chunk.get("new_start", 0), 0.2)
            phrases = [{"text": chunk["text"], "start": 0.0, "end": dur}]
        old_start = chunk.get("new_start", chunk.get("start", 0.0))
        chunk["source_new_start"] = old_start
        chunk["new_start"] = current
        chunk["new_end"] = current + dur
        chunk["segments"] = [
            {
                "id": chunk.get("id", 0),
                "start": chunk.get("start", 0.0),
                "end": chunk.get("end", 0.0),
                "text": phrase.get("text", chunk["text"]),
                "avg_logprob": chunk.get("avg_logprob", 0.0),
                "no_speech_prob": chunk.get("no_speech_prob", 0.0),
                "new_start": current + phrase.get("start", 0.0),
                "new_end": current + phrase.get("end", dur),
            }
            for phrase in phrases
            if phrase.get("text")
        ]
        current = chunk["new_end"] + pause


def _write_timings(chunks: list[dict], timings_path: str) -> None:
    """Persist generated narration timings for cached TTS reuse."""
    import json
    timings = [
        {
            "new_start": chunk.get("new_start", 0.0),
            "new_end": chunk.get("new_end", 0.0),
            "source_new_start": chunk.get("source_new_start", 0.0),
            "segments": chunk.get("segments", []),
        }
        for chunk in chunks
    ]
    with open(timings_path, "w", encoding="utf-8") as f:
        json.dump(timings, f, indent=2)


def _apply_cached_timings(chunks: list[dict], timings_path: str) -> bool:
    """Apply cached generated narration timings to selected chunks."""
    import json
    with open(timings_path, "r", encoding="utf-8") as f:
        timings = json.load(f)

    if len(timings) != len(chunks):
        log.warning("Cached TTS timings do not match selected chunks; subtitle timing may be stale.")
        return False

    for chunk, timing in zip(chunks, timings):
        chunk["source_new_start"] = timing.get("source_new_start", chunk.get("new_start", 0.0))
        chunk["new_start"] = timing["new_start"]
        chunk["new_end"] = timing["new_end"]
        chunk["segments"] = timing.get("segments") or [{
            "id": chunk.get("id", 0),
            "start": chunk.get("start", 0.0),
            "end": chunk.get("end", 0.0),
            "text": chunk["text"],
            "avg_logprob": chunk.get("avg_logprob", 0.0),
            "no_speech_prob": chunk.get("no_speech_prob", 0.0),
            "new_start": chunk["new_start"],
            "new_end": chunk["new_end"],
        }]
    return True
