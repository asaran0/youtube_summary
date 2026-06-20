"""
core/tts/xtts_strategy.py — Coqui XTTS-v2 voice cloning strategy.

Quality: best realism, clones the user's own voice from a sample WAV.
Speed: fast on Apple Silicon (MPS), slow on CPU-only machines.
Needs: pip install TTS, plus cfg.XTTS_VOICE_SAMPLE pointing at a clean
       10-30 second recording of the user's voice.

Runs fully offline after the ~2 GB model is downloaded once.
"""

import os

import numpy as np

from utils import get_logger
from core.tts.base import TTSStrategy
from core.tts.audio_utils import (
    normalize_and_write_wav, resample_wav, polish_audio,
)
from core.lang.transliterate import clean_text

log = get_logger("tts.xtts")


class XTTSStrategy(TTSStrategy):
    name = "xtts"

    def check_available(self, cfg) -> None:
        try:
            import TTS  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "TTS_BACKEND is 'xtts' but the Coqui TTS package isn't installed.\n"
                "Install with:  pip install TTS"
            )

        sample = getattr(cfg, "XTTS_VOICE_SAMPLE", None)
        if not sample or not os.path.exists(sample):
            raise RuntimeError(
                f"TTS_BACKEND is 'xtts' but no voice sample was found at: {sample!r}.\n"
                "Set cfg.XTTS_VOICE_SAMPLE to a WAV of your own voice "
                "(10-30 seconds, quiet room)."
            )

    def synthesize(self, texts: list[str], output_path: str, cfg) -> list[dict]:
        import torch

        try:
            from TTS.api import TTS
        except ImportError:
            raise RuntimeError(
                "Coqui TTS is not installed. Run:  pip install TTS"
            )

        voice_sample = cfg.XTTS_VOICE_SAMPLE
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        log.info("Loading Coqui XTTS-v2 model (first run downloads ~2 GB) …")
        log.info("TTS device: %s", device)

        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

        sample_rate = 24000   # XTTS-v2 always outputs at 24 kHz
        pause_samples = int(sample_rate * cfg.TTS_PAUSE_BETWEEN_SEGMENTS)
        xtts_language = "hi" if cfg.LANGUAGE in ("hi", "hig") else "en"

        all_audio = []
        timings = []

        for i, text in enumerate(texts, 1):
            log.info("  XTTS %d/%d: %s …", i, len(texts), text[:50])
            text = clean_text(text, cfg)
            if not text:
                continue

            try:
                wav_list = tts.tts(
                    text=text,
                    speaker_wav=voice_sample,
                    language=xtts_language,
                )
                waveform = np.array(wav_list, dtype=np.float32)
                all_audio.append(waveform)
                dur = len(waveform) / sample_rate
                timings.append({
                    "duration": dur,
                    "phrases": [{"text": text, "start": 0.0, "end": dur}],
                })
                all_audio.append(np.zeros(pause_samples, dtype=np.float32))

            except Exception as e:
                log.warning("XTTS failed for segment %d: %s", i, e)
                silence = np.zeros(int(sample_rate * 2), dtype=np.float32)
                all_audio.append(silence)
                timings.append({
                    "duration": 2.0,
                    "phrases": [{"text": text, "start": 0.0, "end": 2.0}],
                })

        tmp_wav = os.path.join(cfg.TEMP_DIR, "tts_raw_xtts.wav")
        normalize_and_write_wav(all_audio, sample_rate, tmp_wav)

        resampled_wav = os.path.join(cfg.TEMP_DIR, "tts_xtts_resampled.wav")
        resample_wav(tmp_wav, resampled_wav, target_rate=44100)
        polish_audio(resampled_wav, output_path, cfg)
        log.info("XTTS-v2 generation complete.")
        return timings
