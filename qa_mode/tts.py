"""
qa_mode/tts.py — QA-specific TTS orchestration.

This is the ONLY place that knows about QA concepts like questions vs
answers, dual voices, answer pauses, etc. core/tts/pipeline.py stays
completely mode-agnostic — it just stitches audio + builds timelines.

Architecture
------------
                    qa_mode/runner.py
                           │
                           ▼
                   qa_mode/tts.py          ← you are here
                    ╱           ╲
     core/tts/pipeline.py    core/tts/kokoro_strategy.py
       (stitch + timeline)         (single-voice synth)

For dual-voice (question=male, answer=female), this module calls the
Kokoro strategy twice — once per voice — then reassembles the results
in original order before handing everything to core/tts/pipeline.py.
"""

import os
import copy
import hashlib
import json

import numpy as np

from utils import get_logger
from core.tts.factory import get_strategy as _get_strategy
from core.tts.pipeline import (
    generate_tts_audio as _core_generate,
    _build_audio_and_timeline,
    _write_timings,
    _apply_cached_timings,
)
from core.tts.factory import get_strategy
from core.tts.audio_utils import resample_wav, polish_audio

import wave

log = get_logger("qa.tts")


def generate_tts_audio(selected_chunks: list[dict], cfg) -> str:
    """
    QA-aware TTS entry point.

    If cfg has QA_QUESTION_VOICE and/or QA_ANSWER_VOICE set (dual-voice
    mode), question and answer chunks are synthesised with different
    voices and speeds, then reassembled before stitching.

    Falls back to core generate_tts_audio for single-voice mode.
    """
    from utils import ensure_dirs
    ensure_dirs(cfg.TEMP_DIR)

    q_voices = getattr(cfg, "QA_QUESTION_VOICE", None)
    a_voices = getattr(cfg, "QA_ANSWER_VOICE",   None)
    dual     = bool(q_voices or a_voices)

    if not dual:
        # Single voice — delegate entirely to core pipeline
        log.info("QA TTS: single-voice mode → core pipeline")
        return _core_generate(selected_chunks, cfg)

    # ── Dual-voice mode ───────────────────────────────────────────────────────
    log.info("QA TTS: dual-voice mode (Q=%s / A=%s)",
             (q_voices or {}).get(cfg.LANGUAGE, "?"),
             (a_voices or {}).get(cfg.LANGUAGE, "?"))

    spoken_chunks = [
        c for c in selected_chunks
        if c.get("text", "").strip() and not c.get("is_silent")
    ]

    # Split into question and answer index lists
    q_indices = [i for i, c in enumerate(spoken_chunks) if not c.get("is_answer")]
    a_indices = [i for i, c in enumerate(spoken_chunks) if     c.get("is_answer")]
    q_texts   = [spoken_chunks[i]["text"].strip() for i in q_indices]
    a_texts   = [spoken_chunks[i]["text"].strip() for i in a_indices]

    # Cache key covers both voices + speeds + texts
    cache_key  = _dual_cache_key(q_texts, a_texts, cfg)
    out_path   = os.path.join(cfg.TEMP_DIR, f"tts_audio_{cache_key}.wav")
    time_path  = os.path.join(cfg.TEMP_DIR, f"tts_timings_{cache_key}.json")

    if os.path.exists(out_path) and os.path.exists(time_path):
        log.info("QA TTS: reusing cached dual-voice audio.")
        if _apply_cached_timings(selected_chunks, time_path):
            return out_path

    strategy = get_strategy(cfg.TTS_BACKEND)
    strategy.check_available(cfg)

    # Synthesise questions with question-voice config
    q_cfg    = _voice_cfg(cfg, q_voices, getattr(cfg, "QA_QUESTION_SPEED", None))
    a_cfg    = _voice_cfg(cfg, a_voices, getattr(cfg, "QA_ANSWER_SPEED",   None))

    log.info("Synthesising %d question segments …", len(q_texts))
    q_audio  = strategy.synthesize_segments(q_texts, q_cfg) if q_texts else []

    log.info("Synthesising %d answer segments …", len(a_texts))
    a_audio  = strategy.synthesize_segments(a_texts, a_cfg) if a_texts else []

    # Reassemble in original order
    per_segment_audio = [None] * len(spoken_chunks)
    for list_pos, orig_idx in enumerate(q_indices):
        per_segment_audio[orig_idx] = q_audio[list_pos]
    for list_pos, orig_idx in enumerate(a_indices):
        per_segment_audio[orig_idx] = a_audio[list_pos]

    # Add answer pause to answer chunks (QA-specific timing)
    answer_pause = getattr(cfg, "TTS_ANSWER_PAUSE_EXTRA", 0.0)
    if answer_pause > 0:
        _inject_answer_pauses(selected_chunks, per_segment_audio, answer_pause)

    # Stitch via core pipeline
    _build_audio_and_timeline(selected_chunks, per_segment_audio, out_path, cfg)
    _write_timings(selected_chunks, time_path)

    log.info("QA dual-voice audio → %s", out_path)
    return out_path


# ── Helpers ───────────────────────────────────────────────────────────────────

class _VoiceCfg:
    """Lightweight cfg wrapper that overrides voice + speed for one role."""
    def __init__(self, base_cfg, voices: dict, speed: float | None):
        self._base  = base_cfg
        self._v     = voices
        self._speed = speed

    def __getattr__(self, name: str):
        if name == "KOKORO_VOICES" and self._v:
            return self._v
        if name == "KOKORO_SPEED" and self._speed is not None:
            return self._speed
        return getattr(self._base, name)


def _voice_cfg(base_cfg, voices: dict | None, speed: float | None):
    """Return a cfg that overrides voice/speed for a single role."""
    default_voices = getattr(base_cfg, "KOKORO_VOICES", {})
    merged_voices  = {**default_voices, **(voices or {})}
    merged_speed   = speed if speed is not None else getattr(base_cfg, "KOKORO_SPEED", 1.0)
    return _VoiceCfg(base_cfg, merged_voices, merged_speed)


def _inject_answer_pauses(chunks: list[dict],
                           per_segment_audio: list[dict],
                           pause_sec: float) -> None:
    """
    Prepend a short silence segment before each answer chunk so there is
    a natural beat between question ending and answer beginning.
    This is QA-specific — story mode doesn't need it.
    """
    sample_rate = 24000
    silence_samples = np.zeros(int(sample_rate * pause_sec), dtype=np.int16)

    spoken_idx = 0
    for chunk in chunks:
        if chunk.get("is_silent") or not chunk.get("text", "").strip():
            continue
        if chunk.get("is_answer") and per_segment_audio[spoken_idx] is not None:
            seg = per_segment_audio[spoken_idx]
            merged = np.concatenate([silence_samples, seg["samples"]])
            per_segment_audio[spoken_idx] = {
                **seg,
                "samples": merged,
            }
        spoken_idx += 1


def _dual_cache_key(q_texts: list[str], a_texts: list[str], cfg) -> str:
    q_voices = getattr(cfg, "QA_QUESTION_VOICE", {}) or {}
    a_voices = getattr(cfg, "QA_ANSWER_VOICE",   {}) or {}
    lang     = cfg.LANGUAGE
    payload  = "\n".join([
        "qa-dual-v1",
        cfg.TTS_BACKEND,
        lang,
        str(getattr(cfg, "AUDIO_FILTER", "")),
        str(getattr(cfg, "TTS_PAUSE_BETWEEN_SEGMENTS", "")),
        str(getattr(cfg, "TTS_ANSWER_PAUSE_EXTRA", "")),
        q_voices.get(lang, ""),
        a_voices.get(lang, ""),
        str(getattr(cfg, "QA_QUESTION_SPEED", "")),
        str(getattr(cfg, "QA_ANSWER_SPEED", "")),
        "Q:" + "\n".join(q_texts),
        "A:" + "\n".join(a_texts),
    ])
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def check_backend_available(cfg) -> None:
    """Verify the configured TTS backend is installed and ready."""
    _get_strategy(cfg.TTS_BACKEND).check_available(cfg)
