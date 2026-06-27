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
    "en":  "a",   # American English
    "hi":  "h",   # Hindi
    "hig": "h",   # Hinglish -> closest is the Hindi voice set
}

# Default voices — override via cfg.KOKORO_VOICES in your mode config.
# ┌─────────────────────────────────────────────────────────────────────┐
# │  AVAILABLE VOICES                                                   │
# │                                                                     │
# │  English (lang_code "a" — American):                                │
# │    FEMALE: af_heart★ af_bella af_nicole af_aoede af_kore            │
# │            af_sarah af_sky                                          │
# │    MALE:   am_adam★  am_michael am_echo am_eric am_fenrir           │
# │            am_liam   am_onyx    am_orion am_santa                   │
# │                                                                     │
# │  English (lang_code "b" — British):                                 │
# │    FEMALE: bf_emma bf_isabella                                      │
# │    MALE:   bm_george bm_lewis                                       │
# │                                                                     │
# │  Hindi (lang_code "h"):                                             │
# │    FEMALE: hf_alpha★ hf_beta                                        │
# │    MALE:   hm_omega★ hm_psi                                         │
# │                                                                     │
# │  ★ = recommended default for that language/gender                   │
# └─────────────────────────────────────────────────────────────────────┘
_DEFAULT_VOICES = {
    "en":  "af_heart",   # warm female — change to "am_adam" for male
    "hi":  "hf_alpha",   # clear Hindi female — change to "hm_omega" for male
    "hig": "hf_alpha",   # same as Hindi
}

# Corresponding lang_codes for British English voices
_BRITISH_VOICES = {"bf_emma", "bf_isabella", "bm_george", "bm_lewis"}

def _resolve_lang_code(voice: str, lang: str) -> str:
    """Pick the right Kokoro lang_code for a given voice name."""
    if voice in _BRITISH_VOICES:
        return "b"
    return _LANG_CODE_MAP.get(lang, "a")


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

    def synthesize_segments(self, texts: list[str], cfg,
                            is_answer_flags: list[bool] | None = None) -> list[dict]:
        from kokoro import KPipeline

        lang = cfg.LANGUAGE
        sample_rate = 24000

        # ── Resolve voices and speeds ─────────────────────────────────────────
        # Dual-voice: QA_QUESTION_VOICE / QA_ANSWER_VOICE override KOKORO_VOICES
        q_voices = getattr(cfg, "QA_QUESTION_VOICE", None)
        a_voices = getattr(cfg, "QA_ANSWER_VOICE",   None)
        dual     = (q_voices is not None or a_voices is not None) and is_answer_flags is not None

        default_voices = getattr(cfg, "KOKORO_VOICES", _DEFAULT_VOICES)
        default_voice  = default_voices.get(lang, _DEFAULT_VOICES.get(lang, "af_heart"))
        default_speed  = getattr(cfg, "KOKORO_SPEED", 1.0)

        if dual:
            q_voice = (q_voices or default_voices).get(lang, default_voice)
            a_voice = (a_voices or default_voices).get(lang, default_voice)
            q_speed = getattr(cfg, "QA_QUESTION_SPEED", default_speed)
            a_speed = getattr(cfg, "QA_ANSWER_SPEED",   default_speed)
            log.info("Dual-voice mode: Q=%s (%.2fx)  A=%s (%.2fx)",
                     q_voice, q_speed, a_voice, a_speed)
        else:
            q_voice = a_voice = default_voice
            q_speed = a_speed = default_speed
            log.info("Single-voice mode: voice=%s speed=%.2f", default_voice, default_speed)

        # ── Build per-lang-code pipelines (lazy, cached) ──────────────────────
        pipelines: dict[str, object] = {}
        def get_pipeline(voice: str) -> object:
            lc = _resolve_lang_code(voice, lang)
            if lc not in pipelines:
                log.info("Loading Kokoro pipeline lang_code=%s …", lc)
                pipelines[lc] = KPipeline(lang_code=lc)
            return pipelines[lc]

        # ── Synthesize each segment ────────────────────────────────────────────
        flags   = is_answer_flags or [False] * len(texts)
        results = []

        for i, (text, is_ans) in enumerate(zip(texts, flags), 1):
            voice = a_voice if is_ans else q_voice
            speed = a_speed if is_ans else q_speed
            role  = "Answer" if is_ans else "Question"
            log.info("  TTS %d/%d [%s | %s]: %s …", i, len(texts), role, voice, text[:50])

            cleaned = clean_text(text, cfg)
            if not cleaned:
                results.append(_silent_segment(text, sample_rate))
                continue

            try:
                pipe   = get_pipeline(voice)
                chunks = [np.asarray(audio)
                          for _g, _p, audio in pipe(cleaned, voice=voice, speed=speed)]

                if not chunks:
                    results.append(_silent_segment(text, sample_rate))
                    continue

                waveform = np.concatenate(chunks)
                samples  = _float_to_int16(waveform)
                dur      = len(samples) / sample_rate
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
