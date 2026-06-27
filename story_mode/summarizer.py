"""
story_mode/summarizer.py — Score segments by importance and select the
top ~N% (cfg.TARGET_RATIO).

Algorithm (fully offline, no LLM needed):
    1. Group consecutive segments into "chunks" (natural thought-units).
    2. Score each chunk on four criteria:
            a) Word-frequency importance  (TF-IDF style)
            b) Source confidence          (avg_logprob)
            c) Position bonus             (intro & outro preserved)
            d) Sentence completeness      (ends with punctuation)
    3. Greedily select highest-scoring chunks until TARGET_RATIO is reached.
    4. Always include the first and last KEEP_INTRO/OUTRO_SECONDS.
    5. Return selected chunks sorted chronologically + remap timestamps
       to the new summary timeline.

This is story_mode-specific because it's the only mode that ever
shortens content — qa_mode always keeps every question/answer as-is.
"""

import math
import re
from collections import Counter

from utils import get_logger
from core.lang.tokenize import tokenize

log = get_logger("story.summarizer")


def select_segments(segments: list[dict], total_duration: float, cfg) -> dict:
    """
    Main entry point.

    Parameters
    ----------
    segments       : output of the text-file loader
    total_duration : length of the narration in seconds (0.0 if not
                      yet known — see the total_duration<=0 guard below)
    cfg : the active StoryConfig instance

    Returns
    -------
    dict with keys: selected_segments, summary_duration,
    original_duration, kept_ratio, topic_groups
    """
    if not segments:
        raise ValueError("No segments provided to summarizer")

    chunks = [_make_chunk([seg]) for seg in segments]
    log.info("Grouped %d segments → %d chunks", len(segments), len(chunks))

    idf = _compute_idf(chunks)
    for chunk in chunks:
        chunk["score"] = _score_chunk(chunk, idf, total_duration, cfg)

    intro_chunks, body_chunks, outro_chunks = _split_intro_outro(chunks, total_duration, cfg)
    log.info("Intro chunks: %d  |  Body: %d  |  Outro: %d",
             len(intro_chunks), len(body_chunks), len(outro_chunks))

    forced_duration = (
        sum(_chunk_dur(c) for c in intro_chunks) +
        sum(_chunk_dur(c) for c in outro_chunks)
    )

    # Guard: if total_duration is unknown (0.0, true before TTS has run)
    # or TARGET_RATIO is "keep everything", don't compute a body budget
    # that could come out as 0 and silently drop every chunk.
    if total_duration <= 0 or cfg.TARGET_RATIO >= 1.0:
        body_target = float("inf")
    else:
        body_target = max(total_duration * cfg.TARGET_RATIO - forced_duration, 0)

    selected_body = _greedy_select(body_chunks, body_target, cfg)
    log.info("Selected %d / %d body chunks", len(selected_body), len(body_chunks))

    selected = sorted(intro_chunks + selected_body + outro_chunks, key=lambda c: c["start"])
    selected = _remap_timestamps(selected)
    topic_groups = _detect_topic_groups(selected)

    summary_duration = selected[-1]["new_end"] if selected else 0.0
    kept_ratio = summary_duration / total_duration if total_duration > 0 else 0

    log.info("Summary: %.1f s / %.1f s  (%.0f %%)", summary_duration, total_duration, kept_ratio * 100)

    return {
        "selected_segments": selected,
        "summary_duration": summary_duration,
        "original_duration": total_duration,
        "kept_ratio": kept_ratio,
        "topic_groups": topic_groups,
    }


# ─────────────────────────────────────────────────────────────
#  GROUPING
# ─────────────────────────────────────────────────────────────

def _group_segments(segments: list[dict], gap_threshold: float = 1.5, max_chunk_dur: float = 60.0) -> list[dict]:
    """Merge consecutive segments into chunks based on time gaps / max duration."""
    if not segments:
        return []

    chunks = []
    current_segs = [segments[0]]

    for seg in segments[1:]:
        prev_end = current_segs[-1]["end"]
        chunk_dur = seg["end"] - current_segs[0]["start"]
        gap = seg["start"] - prev_end

        if gap > gap_threshold or chunk_dur > max_chunk_dur:
            chunks.append(_make_chunk(current_segs))
            current_segs = [seg]
        else:
            current_segs.append(seg)

    if current_segs:
        chunks.append(_make_chunk(current_segs))

    return chunks


def _make_chunk(segs: list[dict]) -> dict:
    text = " ".join(s["text"].strip() for s in segs)
    avg_conf = sum(s["avg_logprob"] for s in segs) / len(segs)
    avg_nsp = sum(s["no_speech_prob"] for s in segs) / len(segs)
    return {
        "start": segs[0]["start"],
        "end": segs[-1]["end"],
        "text": text,
        "avg_logprob": avg_conf,
        "no_speech_prob": avg_nsp,
        "segments": segs,
    }


def _chunk_dur(chunk: dict) -> float:
    return chunk["end"] - chunk["start"]


# ─────────────────────────────────────────────────────────────
#  SCORING
# ─────────────────────────────────────────────────────────────

def _compute_idf(chunks: list[dict]) -> dict:
    N = len(chunks)
    doc_freq: Counter = Counter()
    for chunk in chunks:
        words = set(tokenize(chunk["text"]))
        doc_freq.update(words)

    idf = {}
    for word, df in doc_freq.items():
        idf[word] = math.log((N + 1) / (df + 1)) + 1.0
    return idf


def _score_chunk(chunk: dict, idf: dict, total_dur: float, cfg) -> float:
    """Compute a 0-1 importance score for one chunk (4 weighted components)."""
    words = tokenize(chunk["text"])
    tf = Counter(words)
    n_words = max(len(words), 1)

    tfidf_sum = sum((tf[w] / n_words) * idf.get(w, 1.0) for w in tf)
    word_score = min(tfidf_sum / 3.0, 1.0)

    conf_score = min(max((chunk["avg_logprob"] + 1.5) / 1.4, 0.0), 1.0)

    mid_point = (chunk["start"] + chunk["end"]) / 2.0
    rel_pos = mid_point / total_dur if total_dur > 0 else 0.5
    pos_score = 1.0 - 4.0 * (rel_pos - 0.5) ** 2
    pos_score = max(pos_score, 0.0)

    ends_cleanly = chunk["text"].strip().endswith(("।", ".", "?", "!", "…"))
    completeness = 1.0 if ends_cleanly else 0.3

    score = (
        cfg.WEIGHT_WORD_FREQ * word_score +
        cfg.WEIGHT_CONFIDENCE * conf_score +
        cfg.WEIGHT_POSITION * pos_score +
        cfg.WEIGHT_COMPLETENESS * completeness
    )
    return round(score, 4)


# ─────────────────────────────────────────────────────────────
#  SELECTION
# ─────────────────────────────────────────────────────────────

def _split_intro_outro(chunks, total_dur, cfg):
    """
    Force-include intro and outro chunks.

    Guard: if total_dur is unknown (0.0 — true before TTS has run),
    skip intro/outro forcing entirely. Otherwise outro_start would go
    negative and every chunk would match both windows, duplicating the
    whole transcript.
    """
    if total_dur <= 0:
        return [], list(chunks), []

    intro_end = cfg.KEEP_INTRO_SECONDS
    outro_start = total_dur - cfg.KEEP_OUTRO_SECONDS

    intro = [c for c in chunks if c["start"] < intro_end]
    outro = [c for c in chunks if c["end"] > outro_start and c not in intro]
    body = [c for c in chunks if c not in intro and c not in outro]
    return intro, body, outro


def _greedy_select(chunks: list[dict], target_dur: float, cfg) -> list[dict]:
    """
    Select chunks greedily by descending score until target_dur is filled.

    If TARGET_RATIO >= 1.0 (keep everything) or target_dur is
    infinite/unbounded, every chunk is returned — no filtering applied.
    """
    if cfg.TARGET_RATIO >= 1.0 or target_dur == float("inf"):
        return list(chunks)

    sorted_chunks = sorted(chunks, key=lambda c: c["score"], reverse=True)
    selected = []
    total = 0.0
    for chunk in sorted_chunks:
        dur = _chunk_dur(chunk)
        if total + dur <= target_dur:
            selected.append(chunk)
            total += dur
        if total >= target_dur:
            break
    return selected


# ─────────────────────────────────────────────────────────────
#  TIMESTAMP REMAPPING
# ─────────────────────────────────────────────────────────────

def _remap_timestamps(chunks: list[dict]) -> list[dict]:
    """Add new_start / new_end fields representing position in summary video."""
    current = 0.0
    remapped = []
    for chunk in chunks:
        dur = _chunk_dur(chunk)
        offset = chunk["start"]

        new_segs = []
        for seg in chunk.get("segments", []):
            new_segs.append({
                **seg,
                "new_start": current + (seg["start"] - offset),
                "new_end": current + (seg["end"] - offset),
            })

        remapped.append({
            **chunk,
            "new_start": current,
            "new_end": current + dur,
            "segments": new_segs,
        })
        current += dur
    return remapped


# ─────────────────────────────────────────────────────────────
#  TOPIC GROUP DETECTION  (for banners)
# ─────────────────────────────────────────────────────────────

def _detect_topic_groups(chunks: list[dict]) -> list[tuple]:
    """Identify topic-change points by large gaps between consecutive chunks."""
    groups = []
    if not chunks:
        return groups

    groups.append((0.0, _extract_banner_text(chunks[0]["text"])))

    for i in range(1, len(chunks)):
        gap = chunks[i]["start"] - chunks[i - 1]["end"]
        if gap > 3.0:
            banner_text = _extract_banner_text(chunks[i]["text"])
            groups.append((chunks[i]["new_start"], banner_text))

    return groups


def _extract_banner_text(text: str, max_words: int = 7) -> str:
    """Extract a short label from a chunk's text for the banner overlay."""
    text = re.sub(r"\s+", " ", text).strip()
    for delim in ("।", ".", "?", "!"):
        if delim in text:
            first = text.split(delim)[0].strip()
            if 3 <= len(first.split()) <= max_words:
                return first + delim
            break
    words = text.split()
    return " ".join(words[:max_words]) + (" …" if len(words) > max_words else "")
