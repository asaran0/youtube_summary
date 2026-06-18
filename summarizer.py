"""
summarizer.py — Score segments by importance and select the top ~75 %.

Algorithm (fully offline, no LLM needed):
    1.  Group consecutive Whisper segments into "chunks" (natural thought-units).
    2.  Score each chunk on four criteria:
            a) Word-frequency importance  (TF-IDF style)
            b) Whisper confidence         (avg_logprob)
            c) Position bonus             (intro & outro preserved)
            d) Sentence completeness      (ends with punctuation)
    3.  Greedily select highest-scoring chunks until we reach TARGET_RATIO.
    4.  Always include the first and last KEEP_INTRO/OUTRO_SECONDS.
    5.  Return selected chunks sorted chronologically + remap timestamps
        to the new summary timeline.
"""

import math
import re
from collections import Counter

import config
from utils import get_logger

log = get_logger("summarizer")

# Common Hindi stop-words (add more as needed)
HINDI_STOPWORDS = {
    "और", "में", "है", "के", "को", "से", "का", "की", "पर", "यह",
    "इस", "वह", "तो", "भी", "एक", "लेकिन", "जो", "हो", "होता",
    "हैं", "था", "थी", "थे", "जब", "तब", "कि", "ने", "हम", "आप",
    "मैं", "वो", "इन", "उन", "ये", "वे", "उस", "इसे", "उसे",
    "कोई", "कुछ", "सब", "सभी", "अब", "या", "नहीं", "नही", "बहुत",
    "अपने", "अपना", "अपनी", "जैसे", "जैसा", "ही", "रहा", "रही",
    "सकते", "सकता", "सकती", "करते", "करता", "करती", "करना",
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
    "of", "for", "to", "and", "or", "but", "not", "this", "that",
}


# ─────────────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────────────

def select_segments(segments: list[dict], total_duration: float) -> dict:
    """
    Main entry point.

    Parameters
    ----------
    segments       : output of transcriber.transcribe()
    total_duration : length of the original video in seconds

    Returns
    -------
    dict with keys:
        selected_segments   – list of segment dicts with added keys:
                                  new_start, new_end (remapped timeline)
        summary_duration    – total duration of summary in seconds
        original_duration   – total_duration passed in
        kept_ratio          – actual fraction kept
        topic_groups        – list of (group_start_time, banner_text) for banners
    """
    if not segments:
        raise ValueError("No segments provided to summarizer")

    # 1. Group into chunks
    chunks = _group_segments(segments)
    log.info("Grouped %d segments → %d chunks", len(segments), len(chunks))

    # 2. Score each chunk
    idf = _compute_idf(chunks)
    for chunk in chunks:
        chunk["score"] = _score_chunk(chunk, idf, total_duration)

    # 3. Separate forced intro/outro vs selectable body
    intro_chunks, body_chunks, outro_chunks = _split_intro_outro(chunks, total_duration)
    log.info("Intro chunks: %d  |  Body: %d  |  Outro: %d",
             len(intro_chunks), len(body_chunks), len(outro_chunks))

    # 4. Target duration for the body selection
    forced_duration = (
        sum(_chunk_dur(c) for c in intro_chunks) +
        sum(_chunk_dur(c) for c in outro_chunks)
    )
    if total_duration <= 0 or config.TARGET_RATIO >= 1.0:
        # Unknown duration (text/Q&A mode, before TTS runs) or explicit
        # "keep everything" mode — don't compute a body budget that could
        # come out as 0 and silently drop every chunk. Keep all of them.
        body_target = float("inf")
    else:
        body_target = total_duration * config.TARGET_RATIO - forced_duration
        body_target = max(body_target, 0)

    # 5. Greedy selection of body chunks by score
    selected_body = _greedy_select(body_chunks, body_target)
    log.info("Selected %d / %d body chunks", len(selected_body), len(body_chunks))

    # 6. Combine intro + selected body + outro  (chronological order)
    selected = sorted(
        intro_chunks + selected_body + outro_chunks,
        key=lambda c: c["start"]
    )

    # 7. Remap timestamps to new summary timeline
    selected = _remap_timestamps(selected)

    # 8. Extract topic-group banner positions
    topic_groups = _detect_topic_groups(selected)

    summary_duration = selected[-1]["new_end"] if selected else 0.0
    kept_ratio = summary_duration / total_duration if total_duration > 0 else 0

    log.info(
        "Summary: %.1f s / %.1f s  (%.0f %%)",
        summary_duration, total_duration, kept_ratio * 100
    )

    return {
        "selected_segments": selected,
        "summary_duration":   summary_duration,
        "original_duration":  total_duration,
        "kept_ratio":         kept_ratio,
        "topic_groups":       topic_groups,
    }


# ─────────────────────────────────────────────────────────────
#  GROUPING
# ─────────────────────────────────────────────────────────────

def _group_segments(segments: list[dict],
                    gap_threshold: float = 1.5,
                    max_chunk_dur: float = 60.0) -> list[dict]:
    """
    Merge consecutive segments into chunks.

    A new chunk starts when:
        •  the gap between consecutive segments is > gap_threshold seconds, OR
        •  the running chunk would exceed max_chunk_dur seconds.
    """
    if not segments:
        return []

    chunks = []
    current_segs = [segments[0]]

    for seg in segments[1:]:
        prev_end   = current_segs[-1]["end"]
        chunk_dur  = seg["end"] - current_segs[0]["start"]
        gap        = seg["start"] - prev_end

        if gap > gap_threshold or chunk_dur > max_chunk_dur:
            chunks.append(_make_chunk(current_segs))
            current_segs = [seg]
        else:
            current_segs.append(seg)

    if current_segs:
        chunks.append(_make_chunk(current_segs))

    return chunks


def _make_chunk(segs: list[dict]) -> dict:
    """Merge a list of segments into one chunk dict."""
    text = " ".join(s["text"].strip() for s in segs)
    avg_conf = sum(s["avg_logprob"] for s in segs) / len(segs)
    avg_nsp  = sum(s["no_speech_prob"] for s in segs) / len(segs)
    return {
        "start":          segs[0]["start"],
        "end":            segs[-1]["end"],
        "text":           text,
        "avg_logprob":    avg_conf,
        "no_speech_prob": avg_nsp,
        "segments":       segs,       # keep originals for subtitle generation
    }


def _chunk_dur(chunk: dict) -> float:
    return chunk["end"] - chunk["start"]


# ─────────────────────────────────────────────────────────────
#  SCORING
# ─────────────────────────────────────────────────────────────

def _compute_idf(chunks: list[dict]) -> dict:
    """Compute IDF (inverse document frequency) for every word."""
    N = len(chunks)
    doc_freq: Counter = Counter()
    for chunk in chunks:
        words = set(_tokenize(chunk["text"]))
        doc_freq.update(words)

    idf = {}
    for word, df in doc_freq.items():
        idf[word] = math.log((N + 1) / (df + 1)) + 1.0   # smoothed
    return idf


def _score_chunk(chunk: dict, idf: dict, total_dur: float) -> float:
    """
    Compute a 0–1 importance score for one chunk.
    Four weighted components (weights defined in config.py).
    """
    # ── Component 1: word-frequency importance (TF-IDF density) ──────────
    words   = _tokenize(chunk["text"])
    tf      = Counter(words)
    n_words = max(len(words), 1)

    tfidf_sum = sum((tf[w] / n_words) * idf.get(w, 1.0) for w in tf)
    # Normalise to 0–1 range (empirical: most chunks score 0.2–0.8)
    word_score = min(tfidf_sum / 3.0, 1.0)

    # ── Component 2: Whisper confidence ──────────────────────────────────
    # avg_logprob is typically –1.5 (bad) to –0.1 (good)
    conf_score = min(max((chunk["avg_logprob"] + 1.5) / 1.4, 0.0), 1.0)

    # ── Component 3: position bonus (intro / outro matter more) ──────────
    mid_point = (chunk["start"] + chunk["end"]) / 2.0
    rel_pos   = mid_point / total_dur if total_dur > 0 else 0.5
    # U-shaped: score high near 0 and 1, low in the middle
    pos_score = 1.0 - 4.0 * (rel_pos - 0.5) ** 2   # parabola, max at ends
    pos_score = max(pos_score, 0.0)

    # ── Component 4: sentence completeness ───────────────────────────────
    ends_cleanly  = chunk["text"].strip().endswith(("।", ".", "?", "!", "…"))
    completeness  = 1.0 if ends_cleanly else 0.3

    score = (
        config.WEIGHT_WORD_FREQ    * word_score    +
        config.WEIGHT_CONFIDENCE   * conf_score    +
        config.WEIGHT_POSITION     * pos_score     +
        config.WEIGHT_COMPLETENESS * completeness
    )
    return round(score, 4)


# ─────────────────────────────────────────────────────────────
#  SELECTION
# ─────────────────────────────────────────────────────────────

def _split_intro_outro(chunks, total_dur):
    """
    Force-include intro and outro chunks.

    Guard: if total_dur is unknown (0.0 — happens in text/Q&A modes
    where duration isn't known until after TTS runs), skip intro/outro
    forcing entirely. Otherwise outro_start would go negative and every
    chunk would match both windows, duplicating the whole transcript.
    """
    if total_dur <= 0:
        return [], list(chunks), []

    intro_end   = config.KEEP_INTRO_SECONDS
    outro_start = total_dur - config.KEEP_OUTRO_SECONDS

    intro  = [c for c in chunks if c["start"] < intro_end]
    outro  = [c for c in chunks if c["end"]   > outro_start and c not in intro]
    body   = [c for c in chunks if c not in intro and c not in outro]
    return intro, body, outro


def _greedy_select(chunks: list[dict], target_dur: float) -> list[dict]:
    """
    Select chunks greedily by descending score until target_dur is filled.

    If TARGET_RATIO >= 1.0 (keep everything) or target_dur is infinite/
    unbounded, every chunk is returned — no scoring/filtering applied.
    This is what makes text-file and Q&A modes pass every sentence
    through untouched instead of risking an empty selection.
    """
    if config.TARGET_RATIO >= 1.0 or target_dur == float("inf"):
        return list(chunks)

    sorted_chunks = sorted(chunks, key=lambda c: c["score"], reverse=True)
    selected = []
    total    = 0.0
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
    """
    Add new_start / new_end fields representing position in summary video.
    Also remap each child segment's timestamps.
    """
    current = 0.0
    remapped = []
    for chunk in chunks:
        dur  = _chunk_dur(chunk)
        offset = chunk["start"]          # original start

        # Remap child segments
        new_segs = []
        for seg in chunk.get("segments", []):
            new_segs.append({
                **seg,
                "new_start": current + (seg["start"] - offset),
                "new_end":   current + (seg["end"]   - offset),
            })

        remapped.append({
            **chunk,
            "new_start": current,
            "new_end":   current + dur,
            "segments":  new_segs,
        })
        current += dur
    return remapped


# ─────────────────────────────────────────────────────────────
#  TOPIC GROUP DETECTION  (for banners)
# ─────────────────────────────────────────────────────────────

def _detect_topic_groups(chunks: list[dict]) -> list[tuple]:
    """
    Identify topic-change points by large gaps between consecutive chunks
    in the *original* timeline.  Returns list of (new_start, banner_text).
    """
    groups = []
    if not chunks:
        return groups

    # First chunk always gets a banner
    groups.append((0.0, _extract_banner_text(chunks[0]["text"])))

    for i in range(1, len(chunks)):
        gap = chunks[i]["start"] - chunks[i - 1]["end"]
        if gap > 3.0:   # > 3 second gap in original = new topic
            banner_text = _extract_banner_text(chunks[i]["text"])
            groups.append((chunks[i]["new_start"], banner_text))

    return groups


def _extract_banner_text(text: str, max_words: int = 7) -> str:
    """Extract a short label from a chunk's text for the banner overlay."""
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Take the first sentence if it's short enough
    for delim in ("।", ".", "?", "!"):
        if delim in text:
            first = text.split(delim)[0].strip()
            if 3 <= len(first.split()) <= max_words:
                return first + delim
            break
    # Otherwise take first N words
    words = text.split()
    return " ".join(words[:max_words]) + (" …" if len(words) > max_words else "")


# ─────────────────────────────────────────────────────────────
#  TOKENIZER  (simple whitespace + punctuation strip)
# ─────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Lower-case, remove punctuation, split on whitespace, drop stop-words."""
    text  = re.sub(r"[।\.!\?,;:\-\"\'\(\)\[\]\/\\]", " ", text)
    words = [w.strip() for w in text.split() if len(w.strip()) > 1]
    return [w for w in words if w not in HINDI_STOPWORDS]