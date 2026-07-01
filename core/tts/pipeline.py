"""
core/tts/pipeline.py — Public TTS entry point.

This is what story_mode and qa_mode actually call. It handles caching,
dispatches to whichever TTSStrategy the active mode config selected
(via cfg.TTS_BACKEND), and builds both the final audio file and the
chunk timeline (new_start/new_end used by subtitles + slideshow) in a
SINGLE pass — _build_audio_and_timeline below. This is deliberate:
the previous version computed the timeline and the audio file in two
separate passes that could silently drift apart (silent Q&A slides
got a timestamp gap but no actual silence in the audio, so every
subsequent line of speech played earlier than its subtitle). Doing
both in one loop makes that class of bug structurally impossible —
there is exactly one place that decides "how long is this chunk", and
both the audio samples and the timestamps are derived from it.
"""

import os
import json
import hashlib
import wave

import numpy as np

from utils import get_logger, ensure_dirs
from core.tts.factory import get_strategy

log = get_logger("tts")


def generate_tts_audio(selected_chunks: list[dict], cfg) -> str:
    """
    Generate TTS audio for all selected chunks using whichever backend
    cfg.TTS_BACKEND specifies, then build the final audio file and the
    chunk timeline together in one pass.

    Parameters
    ----------
    selected_chunks : list of chunk dicts (output of the mode's
                       segment selection step)
    cfg : the active mode config (StoryConfig or QAConfig instance)

    Returns
    -------
    Path to the final stitched WAV file (spoken audio + real silence,
    exactly matching selected_chunks' new_start/new_end timestamps).
    """
    ensure_dirs(cfg.TEMP_DIR)

    # Silent chunks are never sent to the TTS strategy.
    # We also pass chunk metadata (is_answer flag) so dual-voice backends
    # can use a different voice for questions vs answers.
    spoken_chunks = [
        chunk for chunk in selected_chunks
        if chunk.get("text", "").strip() and not chunk.get("is_silent")
    ]
    texts    = [c["text"].strip() for c in spoken_chunks]
    is_answer_flags = [bool(c.get("is_answer")) for c in spoken_chunks]

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
    per_segment_audio = strategy.synthesize_segments(
        texts, cfg, is_answer_flags=is_answer_flags
    )

    _build_audio_and_timeline(selected_chunks, per_segment_audio, output_path, cfg)
    _write_timings(selected_chunks, timings_path)

    log.info("TTS audio saved → %s", output_path)
    return output_path


def _build_audio_and_timeline(
    chunks: list[dict],
    per_segment_audio: list[dict],
    output_path: str,
    cfg,
) -> None:
    """
    Single pass that builds BOTH the final audio file and the
    new_start/new_end timestamps on each chunk. This is the only place
    in the codebase that decides chunk duration — there is no second
    implementation of this loop anywhere, so audio and subtitles/
    slideshow cannot drift apart.

    per_segment_audio : list of dicts, one per spoken (non-silent)
        chunk, in order, each shaped:
            {"samples": np.int16 array, "sample_rate": int,
             "phrases": [{"text": str, "start": float, "end": float}, ...]}
    """
    sample_rate = per_segment_audio[0]["sample_rate"] if per_segment_audio else 44100
    base_pause = cfg.TTS_PAUSE_BETWEEN_SEGMENTS
    answer_pause_extra = getattr(cfg, "TTS_ANSWER_PAUSE_EXTRA", 0.0)
    vary_pause = getattr(cfg, "TTS_PAUSE_VARY_BY_PUNCTUATION", False)

    def pause_for(text: str) -> float:
        """Shorter pause after a plain full stop, longer for suspense (...) or
        a question — makes back-to-back narration feel less mechanically even.
        Off by default (vary_pause=False) so existing modes are unaffected."""
        if not vary_pause:
            return base_pause
        t = (text or "").rstrip().rstrip("\"'\u201d\u2019)")
        if t.endswith("..."):
            return base_pause * 1.3
        if t.endswith("?"):
            return base_pause * 1.15
        if t.endswith("!"):
            return base_pause * 1.1
        return base_pause * 0.7  # plain '।' / '.' — keep the story moving

    audio_parts: list[np.ndarray] = []
    current = 0.0
    seg_iter = iter(per_segment_audio)

    def add_silence(duration: float) -> None:
        n_samples = max(int(round(duration * sample_rate)), 0)
        if n_samples > 0:
            audio_parts.append(np.zeros(n_samples, dtype=np.int16))

    for chunk in chunks:
        # ── Silent chunk (e.g. Q&A countdown / try-yourself) ──
        if chunk.get("is_silent"):
            dur = max(chunk.get("silent_duration", 1.0), 0.1)
            display = chunk.get("display_text", chunk.get("text", ""))
            pause = pause_for(display)

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

            add_silence(dur)
            current += dur
            add_silence(pause)
            current += pause
            continue

        if not chunk.get("text", "").strip():
            continue

        if chunk.get("is_answer") and answer_pause_extra > 0:
            add_silence(answer_pause_extra)
            current += answer_pause_extra

        segment = next(seg_iter, None)
        if segment is None:
            log.warning("No generated audio for chunk %r — inserting 2s silence.", chunk.get("text", "")[:40])
            dur = 2.0
            phrases = [{"text": chunk["text"], "start": 0.0, "end": dur}]
            add_silence(dur)
        else:
            samples = segment["samples"]
            dur = len(samples) / float(segment["sample_rate"])
            phrases = segment.get("phrases") or [{"text": chunk["text"], "start": 0.0, "end": dur}]
            audio_parts.append(samples)

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

        current = chunk["new_end"]
        pause = pause_for(chunk.get("text", ""))
        add_silence(pause)
        current += pause

    if not audio_parts:
        raise RuntimeError("No audio content generated — empty chunk list or all TTS calls failed")

    combined = np.concatenate(audio_parts)
    raw_path = output_path.replace(".wav", "_raw.wav")
    with wave.open(raw_path, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(combined.tobytes())

    # Polish once, on the complete stitched track (resample, EQ,
    # compression, loudness normalization) — applying this once at the
    # end gives more consistent loudness than polishing each spoken
    # segment separately before silence is even in the picture.
    from core.tts.audio_utils import resample_wav, polish_audio, add_background_music
    resampled_path = output_path.replace(".wav", "_resampled.wav")
    resample_wav(raw_path, resampled_path, target_rate=44100)
    polish_audio(resampled_path, output_path, cfg)

    # Optional background music bed, with sidechain ducking so it never
    # competes with speech. Entirely opt-in via config — off unless a
    # mode sets BACKGROUND_MUSIC_ENABLED = True and a valid
    # BACKGROUND_MUSIC_PATH. Lives here (not per-mode code) so any mode
    # gets it identically just by setting the two config flags.
    if getattr(cfg, "BACKGROUND_MUSIC_ENABLED", False):
        music_path = getattr(cfg, "BACKGROUND_MUSIC_PATH", "")
        if music_path and os.path.exists(music_path):
            mixed_path = output_path.replace(".wav", "_mixed.wav")
            try:
                add_background_music(
                    output_path,
                    music_path,
                    mixed_path,
                    music_volume_db=getattr(cfg, "BACKGROUND_MUSIC_VOLUME_DB", -22.0),
                    duck_ratio=getattr(cfg, "BACKGROUND_MUSIC_DUCK_RATIO", 20.0),
                )
                os.replace(mixed_path, output_path)
                log.info("Background music mixed in → %s", music_path)
            except Exception as exc:
                log.warning("Background music mix failed (%s) — continuing with voice-only audio.", exc)
        else:
            log.warning("BACKGROUND_MUSIC_ENABLED is True but BACKGROUND_MUSIC_PATH is missing/invalid: %r", music_path)

    for tmp in (raw_path, resampled_path):
        if os.path.exists(tmp):
            os.remove(tmp)


def _tts_cache_key(texts: list[str], cfg) -> str:
    # Include dual-voice settings so switching voices invalidates the cache
    q_voices = getattr(cfg, "QA_QUESTION_VOICE", {}) or {}
    a_voices = getattr(cfg, "QA_ANSWER_VOICE",   {}) or {}
    payload = "\n".join([
        "tts-cache-v5",
        cfg.TTS_BACKEND,
        cfg.LANGUAGE,
        getattr(cfg, "MACOS_TTS_VOICE", ""),
        str(getattr(cfg, "MACOS_TTS_RATE", "")),
        str(cfg.TTS_PAUSE_BETWEEN_SEGMENTS),
        str(getattr(cfg, "TTS_PAUSE_BETWEEN_PHRASES", "")),
        str(cfg.AUDIO_POST_PROCESSING),
        cfg.AUDIO_FILTER,
        str(getattr(cfg, "KOKORO_SPEED", "")),
        str(getattr(cfg, "QA_QUESTION_SPEED", "")),
        str(getattr(cfg, "QA_ANSWER_SPEED", "")),
        q_voices.get(cfg.LANGUAGE, ""),
        a_voices.get(cfg.LANGUAGE, ""),
        "\n".join(texts),
    ])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


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
