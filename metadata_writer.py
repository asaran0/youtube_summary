"""
metadata_writer.py — Generate YouTube-ready metadata from the transcript.

Produces:
    output/<safe_title>_metadata.txt   – copy-paste ready metadata file

Contents of the metadata file:
    TITLE:       ≤ 100 chars, keyword-rich
    DESCRIPTION: 2–3 paragraph summary + timestamps + hashtags
    TAGS:        15–25 comma-separated tags
    TIMESTAMPS:  Chapter markers for YouTube chapters feature

All processing is offline — no API calls.
Algorithm uses TF-IDF keyword extraction + rule-based sentence selection.
"""

import os
import re
from collections import Counter

import config
from utils import get_logger, human_duration
from summarizer import _tokenize, HINDI_STOPWORDS   # reuse the same tokeniser

log = get_logger("metadata")


# ─────────────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────────────

def generate_and_save(
    original_metadata: dict,        # from downloader (title, description …)
    selected_chunks:   list[dict],  # selected summary chunks
    topic_groups:      list[tuple], # [(new_start_sec, banner_text), …]
    summary_duration:  float,
    output_dir:        str,
) -> str:
    """
    Generate metadata and write it to a text file.

    Returns the path to the written file.
    """
    full_text = " ".join(c["text"] for c in selected_chunks)
    keywords  = _extract_keywords(full_text, top_n=30)

    # ── Build each section ──────────────────────────────────────────────
    title       = _build_title(original_metadata, full_text, keywords)
    description = _build_description(
        original_metadata, selected_chunks, topic_groups,
        summary_duration, keywords
    )
    tags        = _build_tags(original_metadata, keywords)
    timestamps  = _build_timestamps(topic_groups)

    # ── Format the final file ───────────────────────────────────────────
    content = _format_file(title, description, tags, timestamps,
                           original_metadata, summary_duration)

    # ── Save ────────────────────────────────────────────────────────────
    safe_title = _safe_filename(title)
    file_path  = os.path.join(output_dir, f"{safe_title}_metadata.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    log.info("Metadata saved → %s", file_path)
    return file_path


# ─────────────────────────────────────────────────────────────
#  TITLE
# ─────────────────────────────────────────────────────────────

def _build_title(meta: dict, text: str, keywords: list[str]) -> str:
    """
    Prefer the original video title + "[सारांश]" suffix.
    Falls back to a keyword-based title if the original is missing.
    """
    original = meta.get("title", "").strip()

    # If original title exists, annotate it
    if original:
        # Truncate so the suffix fits within 100 chars
        max_len = 90
        if len(original) > max_len:
            original = original[:max_len].rstrip() + "…"
        suffix = "[Summary]" if config.LANGUAGE == "en" else "[सारांश]"
        return f"{original} {suffix}"

    # Fallback: use top keywords
    kw_title = " | ".join(keywords[:4])
    if config.LANGUAGE == "en":
        return f"{kw_title} - Key Points [Summary]"
    return f"{kw_title} – मुख्य बातें [सारांश]"


# ─────────────────────────────────────────────────────────────
#  DESCRIPTION
# ─────────────────────────────────────────────────────────────

def _build_description(
    meta:            dict,
    chunks:          list[dict],
    topic_groups:    list[tuple],
    summary_dur:     float,
    keywords:        list[str],
) -> str:
    """Build a multi-paragraph YouTube description."""
    lines = []

    # ── Paragraph 1: what this video is ─────────────────────────────────
    orig_title = meta.get("title", "this video" if config.LANGUAGE == "en" else "इस वीडियो")
    if config.LANGUAGE == "en":
        lines.append(
            f"This is a {int(config.TARGET_RATIO * 100)}% summary of "
            f"'{orig_title}'. Duration: {human_duration(summary_dur)}."
        )
    else:
        lines.append(
            f"यह वीडियो '{orig_title}' का {int(config.TARGET_RATIO * 100)}% "
            f"संक्षिप्त सारांश है। "
            f"कुल अवधि: {human_duration(summary_dur)}।"
        )
    lines.append("")

    # ── Paragraph 2: key topics covered ─────────────────────────────────
    if topic_groups:
        topic_labels = [t for (_, t) in topic_groups[:6]]
        lines.append("Key topics:" if config.LANGUAGE == "en" else "📌 मुख्य विषय:")
        for label in topic_labels:
            lines.append(f"  • {label}")
        lines.append("")

    # ── Paragraph 3: first important sentence from transcript ────────────
    first_sentence = _pick_first_sentence(chunks)
    if first_sentence:
        lines.append(first_sentence)
        lines.append("")

    # ── Hashtags (keywords as hashtags) ─────────────────────────────────
    hashtags = " ".join(f"#{kw.replace(' ', '')}" for kw in keywords[:12])
    lines.append(hashtags)
    lines.append("")

    # ── Original video credit ────────────────────────────────────────────
    uploader = meta.get("uploader", "")
    if uploader:
        lines.append(f"Original channel: {uploader}" if config.LANGUAGE == "en" else f"📺 मूल चैनल: {uploader}")
    url = meta.get("url", "")
    if url:
        lines.append(f"Original video: {url}" if config.LANGUAGE == "en" else f"🔗 मूल वीडियो: {url}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
#  TAGS
# ─────────────────────────────────────────────────────────────

def _build_tags(meta: dict, keywords: list[str]) -> list[str]:
    """Merge original video tags with extracted keywords."""
    tags = list(keywords[:20])

    # Add original tags (if any) – limit to first 10
    for t in meta.get("tags", [])[:10]:
        if t not in tags:
            tags.append(t)

    # Add generic helpful tags
    generic = (
        ["English", "summary", "education", "knowledge", "explainer"]
        if config.LANGUAGE == "en"
        else ["हिंदी", "Hindi", "सारांश", "summary", "शिक्षा", "ज्ञान"]
    )
    for g in generic:
        if g not in tags:
            tags.append(g)

    return tags[:30]   # YouTube allows up to ~500 chars in tags


# ─────────────────────────────────────────────────────────────
#  TIMESTAMPS  (YouTube chapters)
# ─────────────────────────────────────────────────────────────

def _build_timestamps(topic_groups: list[tuple]) -> str:
    """Format topic groups as YouTube chapter timestamps."""
    if not topic_groups:
        return ""

    lines = ["⏱ Chapters:"]
    for (start_sec, label) in topic_groups:
        m = int(start_sec // 60)
        s = int(start_sec % 60)
        lines.append(f"{m:02d}:{s:02d} – {label}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
#  KEYWORD EXTRACTION  (offline TF-IDF)
# ─────────────────────────────────────────────────────────────

def _extract_keywords(text: str, top_n: int = 25) -> list[str]:
    """
    Extract the most informative words/phrases from the transcript.
    Uses word frequency after stop-word removal.
    Returns a list of keyword strings sorted by importance.
    """
    tokens = _tokenize(text)
    freq   = Counter(tokens)

    # Filter out very short words and very common ones
    filtered = {w: c for w, c in freq.items() if len(w) > 2 and c > 1}

    # Sort by frequency
    sorted_kw = sorted(filtered, key=lambda w: filtered[w], reverse=True)
    return sorted_kw[:top_n]


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

def _pick_first_sentence(chunks: list[dict]) -> str:
    """Return the first clean sentence from the transcript."""
    for chunk in chunks:
        text = chunk["text"].strip()
        for delim in ("।", ".", "?", "!"):
            if delim in text:
                sent = text.split(delim)[0].strip() + delim
                if len(sent) > 20:
                    return sent
    return ""


def _format_file(
    title:      str,
    description: str,
    tags:       list[str],
    timestamps: str,
    meta:       dict,
    duration:   float,
) -> str:
    """Format all metadata into a readable text file."""
    separator = "═" * 70
    tag_str   = ", ".join(tags)

    return f"""{separator}
  YouTube Video Metadata  —  Auto-generated by Hindi Video Summarizer
{separator}

📌 TITLE (copy this):
{title}

{separator}

📝 DESCRIPTION (copy this):
{description}

{timestamps}

{separator}

🏷  TAGS (copy this):
{tag_str}

{separator}

ℹ  STATS:
  Summary duration : {human_duration(duration)}
  Target ratio     : {int(config.TARGET_RATIO * 100)} %
  Original title   : {meta.get('title', '—')}
  Uploader         : {meta.get('uploader', '—')}
  Source URL       : {meta.get('url', '—')}

{separator}
"""


def _safe_filename(title: str, max_len: int = 50) -> str:
    """Convert a title to a safe filename."""
    safe = re.sub(r'[^\w\s\-]', '', title)
    safe = re.sub(r'\s+', '_', safe.strip())
    return safe[:max_len]
