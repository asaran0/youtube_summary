"""
core/tts/pipeline.py — Public TTS entry point.

This is what story_mode and qa_mode actually call. It handles caching,
dispatches to whichever TTSStrategy the active mode config selected
(via cfg.TTS_BACKEND), and retimes chunk timestamps to match the
generated narration. The strategy itself never needs to know about
chunks, caching, or retiming — it only turns text into audio.
"""

import os
import json
import hashlib

from utils import get_logger, ensure_dirs
from core.tts.factory import get_strategy

log = get_logger("tts")


def generate_tts_audio(selected_chunks: list[dict], cfg) -> str:
    """
    Generate TTS audio for all selected chunks using whichever backend
    cfg.TTS_BACKEND specifies, then retime the chunks in place to match
    the generated narration's actual durations.

    Parameters
    ----------
    selected_chunks : list of chunk dicts (output of the mode's
                       segment selection step)
    cfg : the active mode config (StoryConfig or QAConfig instance)

    Returns
    -------
    Path to the final stitched WAV file.
    """
    ensure_dirs(cfg.TEMP_DIR)

    # Silent chunks (e.g. Q&A countdown / try-yourself slides) are
    # skipped here — they get manual silence inserted during retiming,
    # not real TTS audio.
    texts = [
        chunk["text"].strip()
        for chunk in selected_chunks
        if chunk["text"].strip() and not chunk.get("is_silent")
    ]

    cache_key = _tts_cache_key(texts, cfg)
    output_path = os.path.join(cfg.TEMP_DIR, f"tts_audio_{cache_key}.wav")
    timings_path = os.path.join(cfg.TEMP_DIR, f"tts_timings_{cache_key}.json")

    if os.path.exists(output_path) and os.path.exists(timings_path):
        log.info("TTS audio already generated, reusing cached file.")
        if _apply_cached_timings(selected_chunks, timings_path):
            return output_path

    log.info("Generating TTS for %d text segments …", len(texts))
    log.info("Backend: %s", cfg.TTS_BACKEND)

    strategy = get_strategy(cfg.TTS_BACKEND)
    strategy.check_available(cfg)
    durations = strategy.synthesize(texts, output_path, cfg)

    _retime_chunks_for_tts(selected_chunks, durations, cfg)
    _write_timings(selected_chunks, timings_path)
    log.info("TTS audio saved → %s", output_path)
    return output_path


def _tts_cache_key(texts: list[str], cfg) -> str:
    payload = "\n".join([
        "tts-cache-v4",
        cfg.TTS_BACKEND,
        cfg.LANGUAGE,
        getattr(cfg, "MACOS_TTS_VOICE", ""),
        str(getattr(cfg, "MACOS_TTS_RATE", "")),
        str(cfg.TTS_PAUSE_BETWEEN_SEGMENTS),
        str(getattr(cfg, "TTS_PAUSE_BETWEEN_PHRASES", "")),
        str(cfg.AUDIO_POST_PROCESSING),
        cfg.AUDIO_FILTER,
        "\n".join(texts),
    ])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _retime_chunks_for_tts(chunks: list[dict], timings: list, cfg) -> None:
    """
    Replace original timings with generated narration timings.

    If a chunk has is_answer=True (Q&A mode), an extra pause is
    inserted before it so the question fully lands before the answer
    begins. This setting is per-mode (cfg.TTS_ANSWER_PAUSE_EXTRA) so
    story_mode chunks (which never set is_answer) are unaffected.
    """
    current = 0.0
    pause = cfg.TTS_PAUSE_BETWEEN_SEGMENTS
    answer_pause_extra = getattr(cfg, "TTS_ANSWER_PAUSE_EXTRA", 0.0)
    timing_iter = iter(timings)

    for chunk in chunks:
        # ── Silent chunk (e.g. Q&A countdown): no TTS, fixed duration ──
        if chunk.get("is_silent"):
            dur = max(chunk.get("silent_duration", 1.0), 0.1)
            display = chunk.get("display_text", chunk.get("text", ""))
            chunk["source_new_start"] = chunk.get("new_start", chunk.get("start", 0.0))
            chunk["new_start"] = current
            chunk["new_end"] = current + dur
            chunk["segments"] = [{
                "id": chunk.get("id", 0),
                "start": chunk.get("start", 0.0),
                "end": chunk.get("end", 0.0),
                "text": display,
                "avg_logprob": chunk.get("avg_logprob", 0.0),
                "no_speech_prob": chunk.get("no_speech_prob", 0.0),
                "new_start": current,
                "new_end": current + dur,
                "style": chunk.get("style", "default"),
            }]
            current = chunk["new_end"] + pause
            continue

        if not chunk.get("text", "").strip():
            continue

        if chunk.get("is_answer"):
            current += answer_pause_extra

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

        display_text = chunk.get("display_text", chunk["text"])
        chunk["segments"] = [
            {
                "id": chunk.get("id", 0),
                "start": chunk.get("start", 0.0),
                "end": chunk.get("end", 0.0),
                "text": display_text if len(phrases) == 1 else phrase.get("text", chunk["text"]),
                "avg_logprob": chunk.get("avg_logprob", 0.0),
                "no_speech_prob": chunk.get("no_speech_prob", 0.0),
                "new_start": current + phrase.get("start", 0.0),
                "new_end": current + phrase.get("end", dur),
                "style": chunk.get("style", "default"),
            }
            for phrase in phrases
            if phrase.get("text")
        ]
        current = chunk["new_end"] + pause


def _write_timings(chunks: list[dict], timings_path: str) -> None:
    """Persist generated narration timings for cached TTS reuse."""
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
