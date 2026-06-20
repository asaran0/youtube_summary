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
from core.tts.audio_utils import concat_wav_clips_with_pauses, polish_audio, get_wav_duration
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

    def synthesize(self, texts: list[str], output_path: str, cfg) -> list[dict]:
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

        clip_paths = []
        pause_after = []
        timings = []
        sample_rate = 44100
        phrase_index = 0

        for i, text in enumerate(texts, 1):
            log.info("  TTS %d/%d: %s …", i, len(texts), text[:50])
            text = clean_text(text, cfg)
            if not text:
                continue

            phrases = _split_text_for_voice(text)
            chunk_duration = 0.0
            phrase_timings = []
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
                except subprocess.CalledProcessError as e:
                    log.warning("'say' failed for segment %d phrase %d: %s", i, phrase_num + 1, e)
                    continue

                subprocess.run(
                    ["ffmpeg", "-y", "-i", aiff_path,
                     "-ar", str(sample_rate), "-ac", "1", wav_path],
                    check=True, capture_output=True,
                )
                os.remove(aiff_path)

                clip_dur = get_wav_duration(wav_path)
                phrase_start = chunk_duration
                phrase_timings.append({
                    "text": phrase,
                    "start": phrase_start,
                    "end": phrase_start + clip_dur,
                })
                inner_pause = (
                    cfg.TTS_PAUSE_BETWEEN_PHRASES
                    if phrase_num < len(phrases) - 1
                    else cfg.TTS_PAUSE_BETWEEN_SEGMENTS
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

        raw_output = os.path.join(cfg.TEMP_DIR, "tts_macos_raw.wav")
        concat_wav_clips_with_pauses(clip_paths, pause_after, raw_output, sample_rate)
        polish_audio(raw_output, output_path, cfg)

        for p in clip_paths:
            if os.path.exists(p):
                os.remove(p)

        log.info("macOS TTS generation complete.")
        return timings
