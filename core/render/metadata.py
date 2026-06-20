"""
core/render/metadata.py — Generate YouTube-ready metadata from the transcript.

Produces:
    output/<safe_title>_metadata.txt   — copy-paste ready metadata file

Contents:
    TITLE:       ≤ 100 chars, keyword-rich
    DESCRIPTION: summary + chapter timestamps + hashtags
    TAGS:        comma-separated tags
    TIMESTAMPS:  chapter markers for YouTube's chapters feature

All processing is offline — no API calls. Uses word-frequency keyword
extraction (TF-style) + rule-based sentence selection.

Mode-agnostic: works for both story_mode and qa_mode. Unlike the
original version, this no longer assumes a source video (no
"uploader"/"original URL" fields) since both modes work from text
files, not downloaded videos.
"""

import os
import re
from collections import Counter

from utils import get_logger, human_duration
from core.lang.tokenize import tokenize

log = get_logger("metadata")


def generate_and_save(
    title_seed: str,
    selected_chunks: list[dict],
    topic_groups: list[tuple],
    summary_duration: float,
    output_dir: str,
    cfg,
) -> str:
    """
    Generate metadata and write it to a text file. Returns the file path.

    title_seed : a short string to base the title on (e.g. the
                 --title CLI argument, or the QA file's topic).
    """
    full_text = " ".join(c["text"] for c in selected_chunks)
    keywords = _extract_keywords(full_text, top_n=30)

    title = _build_title(title_seed, keywords, cfg)
    description = _build_description(title_seed, selected_chunks, topic_groups, summary_duration, keywords, cfg)
    tags = _build_tags(keywords, cfg)
    timestamps = _build_timestamps(topic_groups)

    content = _format_file(title, description, tags, timestamps, summary_duration, cfg)

    safe_title = _safe_filename(title)
    file_path = os.path.join(output_dir, f"{safe_title}_metadata.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    log.info("Metadata saved → %s", file_path)
    return file_path


def _build_title(title_seed: str, keywords: list[str], cfg) -> str:
    """Prefer the user-provided title seed; fall back to keyword-based title."""
    seed = (title_seed or "").strip()
    if seed:
        max_len = 90
        if len(seed) > max_len:
            seed = seed[:max_len].rstrip() + "…"
        suffix = "[Summary]" if cfg.LANGUAGE == "en" else "[सारांश]"
        return f"{seed} {suffix}"

    kw_title = " | ".join(keywords[:4])
    if cfg.LANGUAGE == "en":
        return f"{kw_title} - Key Points [Summary]"
    return f"{kw_title} – मुख्य बातें [सारांश]"


def _build_description(
    title_seed: str,
    chunks: list[dict],
    topic_groups: list[tuple],
    summary_dur: float,
    keywords: list[str],
    cfg,
) -> str:
    """Build a multi-paragraph YouTube description."""
    lines = []

    name = title_seed or ("this video" if cfg.LANGUAGE == "en" else "इस वीडियो")
    if cfg.LANGUAGE == "en":
        lines.append(f"{name}. Duration: {human_duration(summary_dur)}.")
    else:
        lines.append(f"{name}। कुल अवधि: {human_duration(summary_dur)}।")
    lines.append("")

    if topic_groups:
        topic_labels = [t for (_, t) in topic_groups[:6]]
        lines.append("Key topics:" if cfg.LANGUAGE == "en" else "📌 मुख्य विषय:")
        for label in topic_labels:
            lines.append(f"  • {label}")
        lines.append("")

    first_sentence = _pick_first_sentence(chunks)
    if first_sentence:
        lines.append(first_sentence)
        lines.append("")

    hashtags = " ".join(f"#{kw.replace(' ', '')}" for kw in keywords[:12])
    lines.append(hashtags)

    return "\n".join(lines)


def _build_tags(keywords: list[str], cfg) -> list[str]:
    """Build tag list from extracted keywords plus generic helpful tags."""
    tags = list(keywords[:20])

    generic = (
        ["English", "summary", "education", "knowledge", "explainer"]
        if cfg.LANGUAGE == "en"
        else ["हिंदी", "Hindi", "सारांश", "summary", "शिक्षा", "ज्ञान"]
    )
    for g in generic:
        if g not in tags:
            tags.append(g)

    return tags[:30]


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


def _extract_keywords(text: str, top_n: int = 25) -> list[str]:
    """Extract the most informative words by frequency after stop-word removal."""
    tokens = tokenize(text)
    freq = Counter(tokens)
    filtered = {w: c for w, c in freq.items() if len(w) > 2 and c > 1}
    sorted_kw = sorted(filtered, key=lambda w: filtered[w], reverse=True)
    return sorted_kw[:top_n]


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
    title: str,
    description: str,
    tags: list[str],
    timestamps: str,
    duration: float,
    cfg,
) -> str:
    """Format all metadata into a readable text file."""
    separator = "═" * 70
    tag_str = ", ".join(tags)

    return f"""{separator}
  YouTube Video Metadata — Auto-generated
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
  Target ratio     : {int(cfg.TARGET_RATIO * 100)} %
  Mode             : {cfg.MODE_NAME}

{separator}
"""


def _safe_filename(title: str, max_len: int = 50) -> str:
    """Convert a title to a safe filename."""
    safe = re.sub(r'[^\w\s\-]', '', title)
    safe = re.sub(r'\s+', '_', safe.strip())
    return safe[:max_len]
