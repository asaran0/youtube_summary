"""
core/tts/kokoro_strategy.py — Kokoro-82M TTS strategy.

Quality: good, very lightweight (82M params), fast even on CPU/MPS.
Languages: English is first-class; Hindi support exists but is newer/
thinner than English. Hinglish ("hig") falls back to the Hindi voice set.
No voice cloning — picks from a fixed set of built-in voices.

Install (NOT in requirements.txt by default — uncomment there, or):
    pip install kokoro>=0.9.4 soundfile
    brew install espeak-ng        # macOS, needed for IPA fallback

To remove this backend entirely: delete this file and its one line in
core/tts/factory.py — nothing else references it.
"""

import numpy as np

from utils import get_logger
from core.tts.base import TTSStrategy
from core.lang.transliterate import clean_text

log = get_logger("tts.kokoro")

# Kokoro's own language codes (not the same as our cfg.LANGUAGE values).
_LANG_CODE_MAP = {
    "en": "a",   # American English
    "hi": "h",   # Hindi
    "hig": "h",  # Hinglish -> closest is the Hindi voice set
}

# A reasonable default voice per language; override via cfg.KOKORO_VOICES.
_DEFAULT_VOICES = {
    "en": "af_heart",
    "hi": "hf_alpha",
    "hig": "hf_alpha",
}


class KokoroStrategy(TTSStrategy):
    name = "kokoro"

    def check_available(self, cfg) -> None:
        try:
            import kokoro  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                f"TTS_BACKEND is 'kokoro' but the package is missing: {e}.\n"
                "Install with:  pip install kokoro>=0.9.4 soundfile\n"
                "macOS also needs espeak-ng:  brew install espeak-ng"
            )

    def synthesize_segments(self, texts: list[str], cfg) -> list[dict]:
        from kokoro import KPipeline

        lang_code = getattr(cfg, "KOKORO_LANG_CODES", _LANG_CODE_MAP).get(cfg.LANGUAGE, "a")
        voice = getattr(cfg, "KOKORO_VOICES", _DEFAULT_VOICES).get(cfg.LANGUAGE, "af_heart")
        speed = getattr(cfg, "KOKORO_SPEED", 1.0)
        sample_rate = 24000  # fixed by the Kokoro model

        log.info("Loading Kokoro pipeline (lang_code=%s, voice=%s) …", lang_code, voice)
        pipeline = KPipeline(lang_code=lang_code)

        results = []
        for i, text in enumerate(texts, 1):
            log.info("  TTS %d/%d: %s …", i, len(texts), text[:50])
            cleaned = clean_text(text, cfg)
            if not cleaned:
                results.append(_silent_segment(text, sample_rate))
                continue

            try:
                chunks = []
                for _graphemes, _phonemes, audio in pipeline(cleaned, voice=voice, speed=speed):
                    chunks.append(np.asarray(audio))

                if not chunks:
                    results.append(_silent_segment(text, sample_rate))
                    continue

                waveform = np.concatenate(chunks)
                samples = _float_to_int16(waveform)
                dur = len(samples) / sample_rate
                results.append({
                    "samples": samples,
                    "sample_rate": sample_rate,
                    "phrases": [{"text": cleaned, "start": 0.0, "end": dur}],
                })

            except Exception as e:
                log.warning("Kokoro TTS failed for segment %d: %s", i, e)
                results.append(_silent_segment(text, sample_rate))

        log.info("Kokoro generation complete.")
        return results


def _silent_segment(text: str, sample_rate: int, duration: float = 2.0) -> dict:
    n_samples = int(sample_rate * duration)
    return {
        "samples": np.zeros(n_samples, dtype=np.int16),
        "sample_rate": sample_rate,
        "phrases": [{"text": text, "start": 0.0, "end": duration}],
    }


def _float_to_int16(waveform: np.ndarray) -> np.ndarray:
    max_val = np.max(np.abs(waveform))
    if max_val > 0:
        waveform = waveform / max_val * 0.95
    return (waveform * 32767).astype(np.int16)
