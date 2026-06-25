"""
core/tts/xtts_strategy.py — Coqui XTTS-v2 voice cloning strategy.

Compatibility patches for PyTorch/torchaudio 2.6:
  1. torch.load       — weights_only=True breaks XttsConfig
  2. torchaudio.load  — torchcodec not installed → soundfile fallback

Quality improvements:
  - Long text is pre-split into sentence chunks before XTTS sees it.
    XTTS has a ~400-token context limit; feeding it long text causes
    rushed/distorted audio at chunk boundaries (especially the last sentence).
  - Each sentence chunk is synthesised individually and concatenated,
    giving clean, natural-sounding output throughout.
"""

import os
import re
import sys
import traceback
from contextlib import contextmanager

import numpy as np

from utils import get_logger
from core.tts.base import TTSStrategy
from core.lang.transliterate import clean_text

log = get_logger("tts.xtts")

# Maximum characters per XTTS chunk. Devanagari text is dense — each
# character is one Unicode scalar (not 3 bytes) so 220 creates too many
# micro-chunks with jarring pauses. 350 chars gives ~2-3 natural sentences
# in Hindi, which XTTS-v2 handles cleanly.
XTTS_MAX_CHARS = 350


def _split_into_chunks(text: str, max_chars: int = XTTS_MAX_CHARS) -> list[str]:
    """
    Split text into chunks of at most max_chars, breaking at sentence
    boundaries (।  .  ?  !) first, then at clause boundaries (, ; —),
    and finally by word if nothing else fits.
    Returns a list of non-empty stripped strings.
    """
    # If short enough, return as-is
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []

    # Split on sentence-ending punctuation.
    # Hindi uses the danda (।) as primary boundary; \s* (not \s+) also
    # splits after। with no trailing space, which is common in Hindi text.
    sentence_endings = re.compile(r'(?<=[।.?!])\s*')
    sentences = sentence_endings.split(text)

    chunks = []
    current = ""

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        # If adding this sentence stays within limit, accumulate
        candidate = (current + " " + sent).strip() if current else sent
        if len(candidate) <= max_chars:
            current = candidate
        else:
            # Flush current chunk
            if current:
                chunks.append(current)
            # Sentence itself too long — split on clause boundaries
            if len(sent) > max_chars:
                sub_chunks = _split_on_clauses(sent, max_chars)
                if sub_chunks:
                    chunks.extend(sub_chunks[:-1])
                    current = sub_chunks[-1]
                else:
                    current = sent
            else:
                current = sent

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]


def _split_on_clauses(text: str, max_chars: int) -> list[str]:
    """Split on clause punctuation (, ; — :) when sentence is too long."""
    clause_re = re.compile(r'(?<=[,;:—])\s+')
    parts = clause_re.split(text)
    chunks, current = [], ""
    for part in parts:
        part = part.strip()
        candidate = (current + " " + part).strip() if current else part
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # Still too long — split by words
            if len(part) > max_chars:
                words = part.split()
                current = ""
                for w in words:
                    trial = (current + " " + w).strip() if current else w
                    if len(trial) <= max_chars:
                        current = trial
                    else:
                        if current:
                            chunks.append(current)
                        current = w
            else:
                current = part
    if current:
        chunks.append(current)
    return chunks


def _load_audio_via_soundfile(filepath, *args, **kwargs):
    """Drop-in replacement for torchaudio.load() using soundfile."""
    import torch
    import soundfile as sf
    data, sr = sf.read(str(filepath), dtype="float32", always_2d=True)
    tensor = torch.from_numpy(data.T.copy())
    return tensor, sr


@contextmanager
def _compat_patches():
    """Patch torch.load and torchaudio.load for PyTorch/torchaudio 2.6."""
    import torch
    import torchaudio

    # Patch 1: torch.load weights_only
    _orig_torch_load = torch.load
    def _patched_torch_load(f, *args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return _orig_torch_load(f, *args, **kwargs)
    torch.load = _patched_torch_load
    sys.modules["torch"].load = _patched_torch_load

    # Patch 2: torchaudio.load → soundfile
    _needs_patch = _torchcodec_is_broken()
    _orig_torchaudio_load = torchaudio.load
    if _needs_patch:
        log.info("Patching torchaudio.load → soundfile (torchcodec unavailable)")
        torchaudio.load = _load_audio_via_soundfile
        sys.modules["torchaudio"].load = _load_audio_via_soundfile
        _xtts_mod = sys.modules.get("TTS.tts.models.xtts")
        if _xtts_mod and hasattr(_xtts_mod, "torchaudio"):
            _xtts_mod.torchaudio.load = _load_audio_via_soundfile

    try:
        yield
    finally:
        torch.load = _orig_torch_load
        sys.modules["torch"].load = _orig_torch_load
        if _needs_patch:
            torchaudio.load = _orig_torchaudio_load
            sys.modules["torchaudio"].load = _orig_torchaudio_load
            _xtts_mod = sys.modules.get("TTS.tts.models.xtts")
            if _xtts_mod and hasattr(_xtts_mod, "torchaudio"):
                _xtts_mod.torchaudio.load = _orig_torchaudio_load


def _torchcodec_is_broken() -> bool:
    try:
        from torchcodec.decoders import AudioDecoder  # noqa: F401
        return False
    except ImportError:
        pass
    try:
        import torchaudio._torchcodec  # noqa: F401
        return True
    except ImportError:
        return False


class XTTSStrategy(TTSStrategy):
    name = "xtts"

    def check_available(self, cfg) -> None:
        try:
            import TTS  # noqa: F401
        except ImportError:
            raise RuntimeError("TTS_BACKEND='xtts' but Coqui TTS not installed.\npip install TTS")
        sample = getattr(cfg, "XTTS_VOICE_SAMPLE", None)
        if not sample or not os.path.exists(sample):
            raise RuntimeError(
                f"No voice sample at: {sample!r}\n"
                "Set cfg.XTTS_VOICE_SAMPLE to a 10-30s clean WAV."
            )

    def synthesize_segments(self, texts: list[str], cfg) -> list[dict]:
        import torch

        try:
            from TTS.api import TTS
        except ImportError:
            raise RuntimeError("Coqui TTS not installed. pip install TTS")

        voice_sample   = cfg.XTTS_VOICE_SAMPLE
        device         = "mps" if torch.backends.mps.is_available() else "cpu"
        xtts_language  = "hi" if cfg.LANGUAGE in ("hi", "hig") else "en"
        sample_rate    = 24000
        results        = []

        log.info("Loading Coqui XTTS-v2 model …  device=%s", device)

        with _compat_patches():
            tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

            for seg_idx, text in enumerate(texts, 1):
                log.info("  Segment %d/%d: %s …", seg_idx, len(texts), text[:60])
                cleaned = clean_text(text, cfg)
                if not cleaned:
                    results.append(_silent_segment(text, sample_rate))
                    continue

                # ── Pre-split into XTTS-safe chunks ──────────────────────
                chunks = _split_into_chunks(cleaned, XTTS_MAX_CHARS)
                log.info("    → %d chunk(s) (max %d chars each)", len(chunks), XTTS_MAX_CHARS)

                seg_waves = []
                try:
                    for c_idx, chunk in enumerate(chunks, 1):
                        log.info("    Chunk %d/%d (%d chars): %s",
                                 c_idx, len(chunks), len(chunk), chunk[:50])
                        # Quality parameters tuned for Hindi narration:
                        #   temperature=0.65  — lower = more stable/clear, less mumbling
                        #   speed=0.9         — slightly slower = better Hindi clarity
                        #   top_k=50, top_p=0.85 — tighter sampling = less hallucination
                        #   enable_text_splitting=False — we do our own splitting above;
                        #     letting XTTS re-split fights with our chunks and causes
                        #     repeated words / truncation at boundaries
                        wav = tts.tts(
                            text=chunk,
                            speaker_wav=voice_sample,
                            language=xtts_language,
                            temperature=0.65,
                            speed=0.9,
                            top_k=50,
                            top_p=0.85,
                            enable_text_splitting=False,
                        )
                        arr = np.array(wav, dtype=np.float32)
                        if arr.size == 0:
                            log.warning("    Chunk %d returned empty audio", c_idx)
                            continue
                        seg_waves.append(arr)

                        # Natural pause between chunks — 0.25s for Hindi sentence
                        # boundaries (danda); feels more like a real narrator pause
                        if c_idx < len(chunks):
                            pause = np.zeros(int(sample_rate * 0.25), dtype=np.float32)
                            seg_waves.append(pause)

                except Exception as e:
                    log.error("XTTS segment %d failed:\n%s", seg_idx, traceback.format_exc())
                    raise RuntimeError(f"XTTS failed on segment {seg_idx}: {e}") from e

                if not seg_waves:
                    results.append(_silent_segment(text, sample_rate))
                    continue

                # Concatenate all chunks for this segment
                waveform = np.concatenate(seg_waves)

                # Normalise to -1 dB peak
                peak = np.max(np.abs(waveform))
                if peak > 0:
                    waveform = waveform / peak * 0.891  # -1 dB

                samples = (waveform * 32767).astype(np.int16)
                dur     = len(samples) / sample_rate
                log.info("    Segment %d done: %.2fs", seg_idx, dur)

                results.append({
                    "samples":     samples,
                    "sample_rate": sample_rate,
                    "phrases":     [{"text": cleaned, "start": 0.0, "end": dur}],
                })

        log.info("XTTS-v2 complete (%d segments).", len(results))
        return results


def _silent_segment(text, sample_rate, duration=2.0):
    return {
        "samples":     np.zeros(int(sample_rate * duration), dtype=np.int16),
        "sample_rate": sample_rate,
        "phrases":     [{"text": text, "start": 0.0, "end": duration}],
    }
