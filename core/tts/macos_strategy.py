"""
core/tts/macos_strategy.py — macOS built-in 'say' command strategy.

Quality: good, zero setup. Uses the Lekha Hindi voice (or any installed
system voice) built into macOS.
Speed: fast.
Needs: nothing extra — works out of the box on macOS.

To see all available voices:  say -v '?' | grep -i hindi
"""

import os
import subprocess

from utils import get_logger
from core.tts.base import TTSStrategy
from core.tts.audio_utils import get_wav_duration
from core.lang.transliterate import clean_text

log = get_logger("tts.macos")


def _split_text_for_voice(text: str, max_chars: int = 180) -> list[str]:
    """Split long text into voice-friendly chunks at sentence boundaries."""
    import re
    sentences = re.split(r"(?<=[।.?!])\s+", text.strip())
    phrases = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        if current and len(current) + len(sentence) + 1 > max_chars:
            phrases.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        phrases.append(current.strip())
    return phrases or [text]


class MacOSStrategy(TTSStrategy):
    name = "macos"

    def check_available(self, cfg) -> None:
        result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                "TTS_BACKEND is 'macos' but the 'say' command isn't available. "
                "This backend only works on macOS."
            )

    def synthesize_segments(self, texts: list[str], cfg) -> list[dict]:
        import numpy as np

        voice = cfg.MACOS_TTS_VOICE

        result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
        available = result.stdout + result.stderr
        if voice.lower() not in available.lower():
            fallback = cfg.MACOS_TTS_VOICES.get(cfg.LANGUAGE, "Lekha")
            log.warning("Voice '%s' not found. Trying '%s' …", voice, fallback)
            voice = fallback
            if voice.lower() not in available.lower():
                log.warning("Fallback voice not found either. Using default system voice.")
                voice = None

        sample_rate = 44100
        phrase_index = 0
        results = []

        for i, text in enumerate(texts, 1):
            log.info("  TTS %d/%d: %s …", i, len(texts), text[:50])
            cleaned = clean_text(text, cfg)
            if not cleaned:
                results.append(_silent_segment(text, sample_rate))
                continue

            phrases = _split_text_for_voice(cleaned)
            segment_clip_paths = []
            phrase_timings = []
            cursor = 0.0

            for phrase_num, phrase in enumerate(phrases):
                phrase_index += 1
                aiff_path = os.path.join(cfg.TEMP_DIR, f"tts_chunk_{phrase_index:04d}.aiff")
                wav_path = os.path.join(cfg.TEMP_DIR, f"tts_chunk_{phrase_index:04d}.wav")

                cmd = ["say", "-o", aiff_path, "-r", str(cfg.MACOS_TTS_RATE)]
                if voice:
                    cmd += ["-v", voice]
                cmd.append(phrase)

                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", aiff_path,
                         "-ar", str(sample_rate), "-ac", "1", wav_path],
                        check=True, capture_output=True,
                    )
                    os.remove(aiff_path)
                except subprocess.CalledProcessError as e:
                    log.warning("'say' failed for segment %d phrase %d: %s", i, phrase_num + 1, e)
                    continue

                clip_dur = get_wav_duration(wav_path)
                phrase_timings.append({"text": phrase, "start": cursor, "end": cursor + clip_dur})
                cursor += clip_dur
                if phrase_num < len(phrases) - 1:
                    cursor += cfg.TTS_PAUSE_BETWEEN_PHRASES

                segment_clip_paths.append(wav_path)

            if not segment_clip_paths:
                results.append(_silent_segment(text, sample_rate))
                continue

            inner_pauses = [
                cfg.TTS_PAUSE_BETWEEN_PHRASES if n < len(segment_clip_paths) - 1 else 0.0
                for n in range(len(segment_clip_paths))
            ]
            samples = _concat_wav_samples_with_pauses(segment_clip_paths, inner_pauses, sample_rate)

            for p in segment_clip_paths:
                if os.path.exists(p):
                    os.remove(p)

            results.append({
                "samples": samples,
                "sample_rate": sample_rate,
                "phrases": phrase_timings,
            })

        if all(r["samples"].size == 0 or _is_silence(r["samples"]) for r in results):
            raise RuntimeError("macOS TTS produced no audio output for any segment")

        log.info("macOS TTS generation complete.")
        return results


def _silent_segment(text: str, sample_rate: int, duration: float = 2.0) -> dict:
    import numpy as np
    n_samples = int(sample_rate * duration)
    return {
        "samples": np.zeros(n_samples, dtype=np.int16),
        "sample_rate": sample_rate,
        "phrases": [{"text": text, "start": 0.0, "end": duration}],
    }


def _is_silence(samples) -> bool:
    import numpy as np
    return bool(np.all(samples == 0))


def _concat_wav_samples_with_pauses(clip_paths: list[str], pause_after: list[float], sample_rate: int):
    """Read mono 16-bit WAV clips and concatenate with a pause (in seconds) after each."""
    import wave
    import numpy as np

    parts = []
    for path, pause_sec in zip(clip_paths, pause_after):
        with wave.open(path, "rb") as wav:
            frames = wav.readframes(wav.getnframes())
            data = np.frombuffer(frames, dtype=np.int16)
        parts.append(data)
        if pause_sec > 0:
            parts.append(np.zeros(int(sample_rate * pause_sec), dtype=np.int16))

    return np.concatenate(parts) if parts else np.zeros(1, dtype=np.int16)
