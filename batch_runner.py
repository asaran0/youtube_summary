"""
batch_runner.py — Generate one video per N questions from a Q&A file.

Usage:
    python batch_runner.py

All settings come from batch_config.py — edit that file, not this one.

What it does:
    1. Reads QUESTIONS_FILE and parses every Q&A pair.
    2. Splits them into chunks of QUESTIONS_PER_PART.
    3. For each chunk:
         • runs the full QA pipeline  (TTS → video)
         • writes  <BATCH_TITLE>_part<N>_qa.mp4
         • writes  <BATCH_TITLE>_part<N>_metadata.txt  with the exact
           question list used in that part in the description
    4. Prints a summary table when all parts are done.
"""

import os
import sys
import re
import time
import importlib

# ── Resolve project root so imports work however this script is called ────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import batch_config as BC


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_qa_file(path: str) -> list[tuple[str, str]]:
    """
    Parse a Q&A text file into a list of (question, answer) tuples.
    Handles the ```text ... ``` wrapper that some files have.
    """
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    # Strip optional ``` fences
    raw = re.sub(r"^```\w*\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())

    pattern = re.compile(r"Q:\s*(.+?)\s*A:\s*(.+?)(?=\n\s*Q:|\Z)", re.DOTALL)
    pairs = pattern.findall(raw)
    if not pairs:
        raise ValueError(f"No 'Q: ... A: ...' pairs found in: {path}")

    # Normalise whitespace within each field
    return [
        (" ".join(q.split()), " ".join(a.split()))
        for q, a in pairs
    ]


def _apply_batch_overrides(cfg) -> None:
    """Push batch_config overrides onto the live qa_mode config module."""
    cfg.OUTPUT_DIR = BC.OUTPUT_DIR
    if BC.LANGUAGE is not None:
        cfg.LANGUAGE = BC.LANGUAGE
    if BC.OUTPUT_MODE is not None:
        cfg.OUTPUT_MODE = BC.OUTPUT_MODE
    if BC.TTS_BACKEND is not None:
        cfg.TTS_BACKEND = BC.TTS_BACKEND
    if BC.XTTS_VOICE_SAMPLE is not None:
        cfg.XTTS_VOICE_SAMPLE = BC.XTTS_VOICE_SAMPLE
    if BC.MACOS_TTS_VOICE is not None:
        cfg.MACOS_TTS_VOICE = BC.MACOS_TTS_VOICE


def _build_question_list_text(pairs: list[tuple[str, str]], part: int, total_parts: int) -> str:
    """Return a formatted string listing the questions for a part."""
    lines = [
        f"Part {part} of {total_parts}  —  {len(pairs)} questions\n",
        "Questions covered in this video:",
        "",
    ]
    for i, (q, _) in enumerate(pairs, start=1):
        lines.append(f"  {i:2d}. {q}")
    return "\n".join(lines)


def _write_part_metadata(
    part: int,
    total_parts: int,
    pairs: list[tuple[str, str]],
    batch_title: str,
    result: dict,
    output_dir: str,
) -> str:
    """
    Write a metadata txt file for one part that includes the question list
    in the description, then return its path.

    We append to the auto-generated metadata from the pipeline so the
    question list appears at the top of the description.
    """
    question_block = _build_question_list_text(pairs, part, total_parts)

    # Read whatever the pipeline already wrote
    pipeline_meta = ""
    if result.get("meta_path") and os.path.exists(result["meta_path"]):
        with open(result["meta_path"], encoding="utf-8") as f:
            pipeline_meta = f.read()

    sep = "═" * 70
    content = (
        f"{sep}\n"
        f"  Batch Video Metadata  —  {batch_title}  Part {part}/{total_parts}\n"
        f"{sep}\n\n"
        f"📋 QUESTIONS IN THIS VIDEO:\n\n"
        f"{question_block}\n\n"
        f"{sep}\n\n"
        + pipeline_meta
    )

    safe = re.sub(r"[^\w\s\-]", "", batch_title)
    safe = re.sub(r"\s+", "_", safe.strip())[:35]
    filename = f"{safe}_part{part}_metadata.txt"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


def _separator(char="─", width=62):
    print(char * width)


def _step(msg: str):
    _separator()
    print(f"  {msg}")
    _separator()


def _hms(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    batch_start = time.time()

    # ── Validate config ───────────────────────────────────────────────────
    qa_file = os.path.join(ROOT, BC.QUESTIONS_FILE)
    if not os.path.exists(qa_file):
        sys.exit(f"[batch_runner] ERROR: QUESTIONS_FILE not found: {qa_file}")
    if BC.QUESTIONS_PER_PART < 1:
        sys.exit("[batch_runner] ERROR: QUESTIONS_PER_PART must be >= 1")

    # ── Parse all Q&A pairs ───────────────────────────────────────────────
    print(f"\n[batch_runner] Reading: {qa_file}")
    all_pairs = _parse_qa_file(qa_file)
    total_q   = len(all_pairs)

    chunks = [
        all_pairs[i : i + BC.QUESTIONS_PER_PART]
        for i in range(0, total_q, BC.QUESTIONS_PER_PART)
    ]
    total_parts = len(chunks)

    print(f"[batch_runner] {total_q} questions  →  {total_parts} parts  "
          f"({BC.QUESTIONS_PER_PART} questions/part)\n")

    # ── Ensure output dir exists ──────────────────────────────────────────
    os.makedirs(BC.OUTPUT_DIR, exist_ok=True)

    # ── Write each part's questions to a temp file, run pipeline ─────────
    from qa_mode import config as qa_cfg
    from qa_mode.runner import run as qa_run

    results_summary = []

    for part, chunk in enumerate(chunks, start=1):
        part_title = f"{BC.BATCH_TITLE}_part{part}"
        _step(f"PART {part}/{total_parts}  —  {part_title}  "
              f"({len(chunk)} questions)")

        # Print which questions are in this part
        for i, (q, _) in enumerate(chunk, start=1):
            print(f"    Q{i}: {q[:80]}{'…' if len(q)>80 else ''}")
        print()

        # Write chunk to a temp Q&A file
        temp_qa_path = os.path.join(BC.OUTPUT_DIR, f"_batch_temp_part{part}.txt")
        with open(temp_qa_path, "w", encoding="utf-8") as f:
            for q, a in chunk:
                f.write(f"Q: {q}\nA: {a}\n\n")

        # Apply overrides fresh for each part (runner may mutate cfg)
        importlib.reload(qa_cfg)
        _apply_batch_overrides(qa_cfg)

        part_start = time.time()
        try:
            result = qa_run(
                qa_path=temp_qa_path,
                title=part_title,
                cfg=qa_cfg,
                keep_temp=BC.KEEP_TEMP,
            )
            part_dur = time.time() - part_start

            # Write enhanced metadata with question list
            meta_path = _write_part_metadata(
                part=part,
                total_parts=total_parts,
                pairs=chunk,
                batch_title=BC.BATCH_TITLE,
                result=result,
                output_dir=BC.OUTPUT_DIR,
            )

            results_summary.append({
                "part":       part,
                "title":      part_title,
                "video":      result.get("video_path", "?"),
                "metadata":   meta_path,
                "duration":   result.get("summary_duration", 0),
                "elapsed":    part_dur,
                "status":     "✅ done",
            })
            print(f"\n  ✅  Part {part} done in {_hms(part_dur)}"
                  f"  →  {result.get('video_path', '?')}\n")

        except Exception as exc:
            part_dur = time.time() - part_start
            results_summary.append({
                "part":    part,
                "title":   part_title,
                "video":   "—",
                "metadata":"—",
                "duration": 0,
                "elapsed":  part_dur,
                "status":  f"❌ FAILED: {exc}",
            })
            print(f"\n  ❌  Part {part} FAILED after {_hms(part_dur)}: {exc}\n",
                  file=sys.stderr)

        finally:
            # Remove the temp Q&A file
            if os.path.exists(temp_qa_path):
                os.remove(temp_qa_path)

    # ── Final summary table ───────────────────────────────────────────────
    total_elapsed = time.time() - batch_start
    _separator("═")
    print(f"  BATCH COMPLETE  —  {BC.BATCH_TITLE}")
    print(f"  {total_parts} parts  •  {total_q} questions  •  {_hms(total_elapsed)} total")
    _separator("═")
    print()

    for r in results_summary:
        video_name = os.path.basename(r["video"]) if r["video"] != "—" else "—"
        print(f"  Part {r['part']:2d}  {r['status']}")
        print(f"          Video    : {video_name}")
        if r["metadata"] != "—":
            print(f"          Metadata : {os.path.basename(r['metadata'])}")
        print(f"          Duration : {_hms(r['duration'])}  (render: {_hms(r['elapsed'])})")
        print()

    _separator("═")

    failed = [r for r in results_summary if "FAILED" in r["status"]]
    if failed:
        print(f"\n  ⚠️  {len(failed)} part(s) failed. Check errors above.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
