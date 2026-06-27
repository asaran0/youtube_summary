"""
run.py — Main entry point for the Gemma → Emotion → TTS → Video POC.

Usage:
    python run.py                    # full pipeline
    python run.py --stage llm        # generate text only  → saves llm_out.txt
    python run.py --stage emotion    # emotion tag only    → reads llm_out.txt
    python run.py --stage tts        # TTS only            → reads emotion_out.json
    python run.py --stage video      # video only          → reads audio + emotion_out.json
    python run.py --dry-run          # print plan, don't run anything

Edit config.py to change models, language, topic, and backends.
"""

import sys
import os
import json
import time
import argparse

# Make sure emotion_poc is importable regardless of where run.py is called from
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import config as cfg


# ── Persistence helpers (resume interrupted runs) ─────────────────────────────

_LLM_OUT     = os.path.join(cfg.TEMP_DIR, "llm_out.txt")
_EMOTION_OUT = os.path.join(cfg.TEMP_DIR, "emotion_out.json")
_AUDIO_OUT   = os.path.join(cfg.TEMP_DIR, "merged_audio.wav")


def _save(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if path.endswith(".json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)
    print(f"  → saved: {path}")


def _load(path: str):
    if not os.path.exists(path):
        return None
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── Stage runners ─────────────────────────────────────────────────────────────

def run_llm() -> str:
    print("\n━━ STAGE 1 / 4 — LLM text generation ━━")
    t = time.time()
    from llm.generator import generate
    text = generate(cfg)
    _save(_LLM_OUT, text)
    print(f"  ✓ done in {time.time()-t:.1f}s")
    return text


def run_emotion(text: str) -> list[dict]:
    print("\n━━ STAGE 2 / 4 — Emotion injection ━━")
    t = time.time()
    from emotion.injector import inject
    tagged = inject(text, cfg)
    _save(_EMOTION_OUT, tagged)
    print(f"  ✓ done in {time.time()-t:.1f}s")
    return tagged


def run_tts(tagged: list[dict]) -> str:
    print("\n━━ STAGE 3 / 4 — TTS synthesis ━━")
    t = time.time()
    from tts.synthesizer import synthesize
    audio_path = synthesize(tagged, cfg, cfg.TEMP_DIR)
    print(f"  ✓ done in {time.time()-t:.1f}s  →  {audio_path}")
    return audio_path


def run_video(tagged: list[dict], audio_path: str) -> str:
    print("\n━━ STAGE 4 / 4 — Video assembly ━━")
    t = time.time()
    from pipeline.video import assemble
    video_path = assemble(tagged, audio_path, cfg, cfg.TEMP_DIR)
    print(f"  ✓ done in {time.time()-t:.1f}s  →  {video_path}")
    return video_path


# ── Dry run ───────────────────────────────────────────────────────────────────

def dry_run():
    print("\n┌─ POC Plan ──────────────────────────────────────────┐")
    print(f"│  Content type  : {cfg.CONTENT_TYPE}")
    print(f"│  Topic         : {cfg.TOPIC[:55]}")
    print(f"│  Language      : {cfg.LANGUAGE}")
    print(f"│  Target words  : {cfg.TARGET_WORDS}")
    print(f"│")
    print(f"│  Stage 1  LLM           → {cfg.LLM_BACKEND}")
    print(f"│  Stage 2  Emotion       → {cfg.EMOTION_BACKEND}")
    print(f"│  Stage 3  TTS           → {cfg.TTS_BACKEND}")
    print(f"│  Stage 4  Video         → {cfg.VIDEO_BACKEND}")
    print(f"│")
    print(f"│  Output dir    : {cfg.OUTPUT_DIR}")
    print(f"│  Temp dir      : {cfg.TEMP_DIR}")
    print(f"│")

    # M1 memory warning
    if cfg.TTS_BACKEND == "indic_parler" and cfg.LLM_BACKEND in ("ollama", "llama_cpp"):
        print(f"│  ⚠ M1 8 GB WARNING: Gemma + Indic Parler together")
        print(f"│    may cause OOM. The pipeline will unload Gemma")
        print(f"│    before loading TTS. Consider TTS_BACKEND='kokoro'")
        print(f"│    for faster, safer runs.")
    print(f"└─────────────────────────────────────────────────────┘")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gemma → Emotion → TTS → Video POC")
    parser.add_argument(
        "--stage",
        choices=["llm", "emotion", "tts", "video", "all"],
        default="all",
        help="Run only one stage (others must have run already)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print plan, don't run")
    args = parser.parse_args()

    if args.dry_run:
        dry_run()
        return

    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    os.makedirs(cfg.TEMP_DIR,   exist_ok=True)

    wall = time.time()

    if args.stage in ("all", "llm"):
        text = run_llm()
    else:
        text = _load(_LLM_OUT)
        if not text:
            sys.exit(f"[run] llm_out.txt not found at {_LLM_OUT}. Run stage 'llm' first.")

    if args.stage in ("all", "emotion"):
        tagged = run_emotion(text)
    else:
        tagged = _load(_EMOTION_OUT)
        if not tagged:
            sys.exit(f"[run] emotion_out.json not found at {_EMOTION_OUT}. Run stage 'emotion' first.")

    if args.stage in ("all", "tts"):
        audio_path = run_tts(tagged)
    else:
        audio_path = _AUDIO_OUT
        if not os.path.exists(audio_path):
            sys.exit(f"[run] merged_audio.wav not found at {audio_path}. Run stage 'tts' first.")

    if args.stage in ("all", "video"):
        video_path = run_video(tagged, audio_path)

    total = time.time() - wall
    m, s  = divmod(int(total), 60)
    print(f"\n✅  Complete in {m}m {s}s")

    if args.stage == "all":
        print(f"   Output → {cfg.OUTPUT_DIR}")
        print(f"\n   To re-run only TTS (e.g. to try indic_parler):")
        print(f"     1. Edit config.py → TTS_BACKEND = 'indic_parler'")
        print(f"     2. python run.py --stage tts")
        print(f"     3. python run.py --stage video")


if __name__ == "__main__":
    main()
