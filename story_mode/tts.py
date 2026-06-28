"""
story_mode/tts.py — Story-mode TTS entry point.

Thin wrapper around core/tts/pipeline.py. Story mode uses a single
voice for everything — no question/answer split. This file exists so
story_mode/runner.py imports from its own namespace and stays decoupled
from qa_mode.

Story-specific TTS concerns live here:
  - Emotional pacing (KOKORO_SPEED slower than default)
  - Storytelling voice selection (warm, emotive voices)
  - Punctuation-based pause variation (TTS_PAUSE_VARY_BY_PUNCTUATION)

Nothing in core/ knows about "story mode".
"""

from utils import get_logger
from core.tts.pipeline import generate_tts_audio as _core_generate

log = get_logger("story.tts")


def generate_tts_audio(selected_chunks: list[dict], cfg) -> str:
    """
    Story-mode TTS. Delegates to core pipeline — story mode is always
    single-voice, so no extra orchestration is needed here.

    Story-specific settings are read from story_mode/config.py:
        KOKORO_SPEED = 0.82           # slower, emotional pace
        KOKORO_VOICES = {"en": "am_adam", "hi": "hm_omega"}
        TTS_PAUSE_VARY_BY_PUNCTUATION = True   # natural breath between sentences
    """
    log.info("Story TTS: backend=%s voice=%s speed=%.2f",
             cfg.TTS_BACKEND,
             (getattr(cfg, "KOKORO_VOICES", {}) or {}).get(cfg.LANGUAGE, "?"),
             getattr(cfg, "KOKORO_SPEED", 1.0))
    return _core_generate(selected_chunks, cfg)


def check_backend_available(cfg) -> None:
    """Verify the configured TTS backend is installed and ready."""
    from core.tts.factory import get_strategy as _get_strategy
    _get_strategy(cfg.TTS_BACKEND).check_available(cfg)
