"""
core/tts/audio_utils.py — Shared audio helpers used by every TTS strategy.

None of this is backend-specific: resampling, loudness/EQ polishing, and
WAV concatenation are needed identically whether the audio came from
XTTS, MMS, or macOS 'say'. Keeping it here means a fix or improvement
(e.g. a better loudness filter) benefits all three strategies at once.
"""

import os
import subprocess
import wave

import numpy as np

from utils import get_logger

log = get_logger("tts.audio")


def resample_wav(input_wav: str, output_wav: str, target_rate: int = 44100) -> None:
    """Resample a WAV file to target_rate Hz using ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_wav,
         "-ar", str(target_rate), "-ac", "1", output_wav],
        check=True, capture_output=True,
    )


def polish_audio(input_wav: str, output_wav: str, cfg) -> None:
    """
    Apply light cleanup, compression and loudness normalization.

    cfg must provide AUDIO_POST_PROCESSING (bool) and AUDIO_FILTER
    (ffmpeg -af filter string) — both come from the active mode config.
    """
    if not cfg.AUDIO_POST_PROCESSING:
        if input_wav != output_wav:
            subprocess.run(["ffmpeg", "-y", "-i", input_wav, output_wav],
                            check=True, capture_output=True)
        return

    cmd = [
        "ffmpeg", "-y",
        "-i", input_wav,
        "-af", cfg.AUDIO_FILTER,
        "-ar", "44100",
        "-ac", "1",
        output_wav,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def normalize_and_write_wav(audio_segments: list[np.ndarray], sample_rate: int, tmp_wav_path: str) -> None:
    """
    Concatenate float32 audio segments (already including any pauses
    the caller inserted), normalize to avoid clipping, and write as a
    16-bit PCM WAV file. Used by xtts and mms strategies, whose models
    return raw float waveforms directly.
    """
    if not audio_segments:
        raise RuntimeError("No audio segments to write — TTS produced no output")

    import scipy.io.wavfile as wavfile

    combined = np.concatenate(audio_segments).astype(np.float32)
    max_val = np.max(np.abs(combined))
    if max_val > 0:
        combined = combined / max_val * 0.85

    combined_int16 = (combined * 32767).astype(np.int16)
    wavfile.write(tmp_wav_path, sample_rate, combined_int16)


def concat_wav_clips_with_pauses(
    clip_paths: list[str],
    pause_after: list[float],
    output_path: str,
    sample_rate: int,
) -> None:
    """
    Concatenate mono 16-bit WAV clips with a per-clip pause duration
    after each one. Used by the macOS strategy, which produces one WAV
    file per spoken phrase via the 'say' command.
    """
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


def get_wav_duration(filepath: str) -> float:
    """Return duration of a WAV file in seconds."""
    with wave.open(filepath, "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        return frames / float(rate) if rate else 0.0
