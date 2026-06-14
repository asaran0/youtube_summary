"""
transcriber.py — Transcribe Hindi audio using OpenAI Whisper (runs 100 % locally).

On M1 Mac the model will use the Metal GPU (MPS) automatically for faster inference.

Output:
    list of segment dicts, each containing:
        {
            "id":           int,
            "start":        float,   # seconds
            "end":          float,   # seconds
            "text":         str,     # Hindi text
            "avg_logprob":  float,   # Whisper confidence  (higher = better)
            "no_speech_prob": float, # probability this is silence/noise (lower = better)
        }
"""

import os
import json

import config
from utils import get_logger

log = get_logger("transcriber")


# ─────────────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────────────

def transcribe(audio_path: str) -> list[dict]:
    """
    Run Whisper on the given audio file and return timestamped segments.

    The result is also cached to  temp/transcript.json  so that repeated
    runs of the pipeline skip the (slow) transcription step.
    """
    cache_path = os.path.join(
        config.TEMP_DIR,
        f"transcript_{config.LANGUAGE}_{config.WHISPER_MODEL}.json",
    )

    if os.path.exists(cache_path):
        log.info("Loading cached transcript …")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    log.info("Loading Whisper model: %s …", config.WHISPER_MODEL)
    model = _load_model()

    log.info("Transcribing audio (this may take a few minutes) …")
    transcribe_kwargs = {
        "task": "translate" if config.LANGUAGE == "en" else "transcribe",
        "word_timestamps": False,
        "verbose": False,
    }
    if config.LANGUAGE != "en":
        transcribe_kwargs["language"] = config.LANGUAGE

    result = model.transcribe(audio_path, **transcribe_kwargs)

    segments = _clean_segments(result["segments"])
    log.info("Transcription complete: %d segments", len(segments))

    # Cache for later runs
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    return segments


def get_full_text(segments: list[dict]) -> str:
    """Concatenate all segment texts into one string."""
    return " ".join(seg["text"].strip() for seg in segments)


# ─────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────

def _load_model():
    """Load Whisper model, preferring M1 MPS acceleration."""
    import whisper
    import torch

    # Pick the best available device
    if torch.backends.mps.is_available():
        device = "mps"
        log.info("Using Apple MPS (Metal GPU) acceleration ✓")
    elif torch.cuda.is_available():
        device = "cuda"
        log.info("Using CUDA GPU acceleration ✓")
    else:
        device = "cpu"
        log.info("Using CPU (no GPU acceleration found)")

    model = whisper.load_model(config.WHISPER_MODEL, device=device)
    log.info("Model loaded on device: %s", device)
    return model


def _clean_segments(raw_segments: list) -> list[dict]:
    """
    Convert Whisper's raw segment dicts to a clean, minimal format.
    Filters out pure-silence / very low-confidence segments.
    """
    clean = []
    for seg in raw_segments:
        text = seg.get("text", "").strip()

        # Skip blank or near-blank segments
        if len(text) < 3:
            continue

        # Skip segments Whisper flagged as likely silence
        if seg.get("no_speech_prob", 0.0) > 0.80:
            log.debug("Skipping silent segment [%.1f–%.1f]: %s",
                      seg["start"], seg["end"], text[:40])
            continue

        clean.append({
            "id":             seg["id"],
            "start":          round(seg["start"], 3),
            "end":            round(seg["end"],   3),
            "text":           text,
            "avg_logprob":    round(seg.get("avg_logprob",    -0.5), 4),
            "no_speech_prob": round(seg.get("no_speech_prob",  0.1), 4),
        })

    log.info("Kept %d / %d segments after cleaning", len(clean), len(raw_segments))
    return clean
