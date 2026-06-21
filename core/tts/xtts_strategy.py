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

    def synthesize_segments(self, texts: list[str], cfg) -> list[dict]:
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
        xtts_language = "hi" if cfg.LANGUAGE in ("hi", "hig") else "en"
        results = []

        for i, text in enumerate(texts, 1):
            log.info("  XTTS %d/%d: %s …", i, len(texts), text[:50])
            cleaned = clean_text(text, cfg)
            if not cleaned:
                results.append(_silent_segment(text, sample_rate))
                continue

            try:
                wav_list = tts.tts(
                    text=cleaned,
                    speaker_wav=voice_sample,
                    language=xtts_language,
                )
                waveform = np.array(wav_list, dtype=np.float32)
                samples = _float_to_int16(waveform)
                dur = len(samples) / sample_rate
                results.append({
                    "samples": samples,
                    "sample_rate": sample_rate,
                    "phrases": [{"text": cleaned, "start": 0.0, "end": dur}],
                })

            except Exception as e:
                log.warning("XTTS failed for segment %d: %s", i, e)
                results.append(_silent_segment(text, sample_rate))

        log.info("XTTS-v2 generation complete.")
        return results


def _silent_segment(text: str, sample_rate: int, duration: float = 2.0) -> dict:
    n_samples = int(sample_rate * duration)
    return {
        "samples": np.zeros(n_samples, dtype=np.int16),
        "sample_rate": sample_rate,
        "phrases": [{"text": text, "start": 0.0, "end": duration}],
    }


def _float_to_int16(waveform: np.ndarray) -> np.ndarray:
    """Convert a float32 [-1, 1] waveform to normalized int16 PCM."""
    max_val = np.max(np.abs(waveform))
    if max_val > 0:
        waveform = waveform / max_val * 0.95
    return (waveform * 32767).astype(np.int16)
