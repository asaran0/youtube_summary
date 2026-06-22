"""
core/tts/xtts_strategy.py — Coqui XTTS-v2 voice cloning strategy.

Compatibility patches for PyTorch/torchaudio 2.6:
  1. torch.load defaults to weights_only=True  → patch to False
  2. torchaudio.load defaults to torchcodec    → patch to use soundfile backend
"""

import os
import traceback
from contextlib import contextmanager

import numpy as np

from utils import get_logger
from core.tts.base import TTSStrategy
from core.lang.transliterate import clean_text

log = get_logger("tts.xtts")


@contextmanager
def _compat_patches():
    """
    Apply two monkey-patches needed for Coqui XTTS on PyTorch/torchaudio 2.6:

    1. torch.load: default changed to weights_only=True — breaks XttsConfig
       checkpoint loading. Patch to always use weights_only=False.

    2. torchaudio.load: now routes through torchcodec which isn't installed
       with Coqui. Patch to use the soundfile backend directly instead.

    Both patches are scoped to the with-block and immediately reverted.
    """
    import torch
    import torchaudio

    # ── Patch 1: torch.load weights_only ─────────────────────────────────
    _orig_torch_load = torch.load

    def _patched_torch_load(f, *args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return _orig_torch_load(f, *args, **kwargs)

    torch.load = _patched_torch_load

    # ── Patch 2: torchaudio.load → soundfile backend ──────────────────────
    # torchaudio 2.6 tries torchcodec first; fall back to soundfile/sox.
    _orig_torchaudio_load = torchaudio.load

    def _patched_torchaudio_load(filepath, *args, **kwargs):
        # Try the old backend kwarg first (torchaudio < 2.6 style)
        for backend in ("soundfile", "sox_io", "sox"):
            try:
                return torchaudio.load(filepath, *args, backend=backend, **kwargs)
            except Exception:
                pass
        # Last resort: read with soundfile directly and return a tensor
        try:
            import soundfile as sf
            data, sr = sf.read(str(filepath), dtype="float32", always_2d=True)
            tensor = torch.from_numpy(data.T)   # (channels, samples)
            return tensor, sr
        except Exception:
            pass
        # Absolute fallback: scipy
        try:
            from scipy.io import wavfile
            sr, data = wavfile.read(str(filepath))
            if data.dtype != np.float32:
                data = data.astype(np.float32) / np.iinfo(data.dtype).max
            if data.ndim == 1:
                data = data[np.newaxis, :]
            else:
                data = data.T
            return torch.from_numpy(data), sr
        except Exception as e:
            raise RuntimeError(
                f"Could not load audio file {filepath!r}. "
                "Install soundfile:  pip install soundfile\n"
                f"Original error: {e}"
            )

    # Only replace if the installed torchaudio actually tries torchcodec
    _needs_torchaudio_patch = False
    try:
        import torchaudio._torchcodec  # noqa: F401
        _needs_torchaudio_patch = True
    except ImportError:
        pass

    if _needs_torchaudio_patch:
        torchaudio.load = _patched_torchaudio_load
        log.info("torchaudio.load patched (torchcodec bypass → soundfile)")

    try:
        yield
    finally:
        torch.load = _orig_torch_load
        if _needs_torchaudio_patch:
            torchaudio.load = _orig_torchaudio_load


class XTTSStrategy(TTSStrategy):
    name = "xtts"

    def check_available(self, cfg) -> None:
        try:
            import TTS  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "TTS_BACKEND is 'xtts' but the Coqui TTS package isn't installed.\n"
                "Install with:  pip install TTS"
            )
        sample = getattr(cfg, "XTTS_VOICE_SAMPLE", None)
        if not sample or not os.path.exists(sample):
            raise RuntimeError(
                f"TTS_BACKEND is 'xtts' but no voice sample was found at: {sample!r}.\n"
                "Set cfg.XTTS_VOICE_SAMPLE to a WAV of your own voice "
                "(10-30 seconds, quiet room)."
            )

    def synthesize_segments(self, texts: list[str], cfg) -> list[dict]:
        import torch

        try:
            from TTS.api import TTS
        except ImportError:
            raise RuntimeError("Coqui TTS is not installed. Run:  pip install TTS")

        voice_sample = cfg.XTTS_VOICE_SAMPLE
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        log.info("Loading Coqui XTTS-v2 model (first run downloads ~2 GB) …")
        log.info("TTS device: %s", device)

        with _compat_patches():
            tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

            sample_rate   = 24000
            xtts_language = "hi" if cfg.LANGUAGE in ("hi", "hig") else "en"
            results       = []

            for i, text in enumerate(texts, 1):
                log.info("  XTTS %d/%d: %s …", i, len(texts), text[:60])
                cleaned = clean_text(text, cfg)
                if not cleaned:
                    log.warning("  Segment %d cleaned to empty — inserting silence", i)
                    results.append(_silent_segment(text, sample_rate))
                    continue

                try:
                    wav_list = tts.tts(
                        text=cleaned,
                        speaker_wav=voice_sample,
                        language=xtts_language,
                    )
                    waveform = np.array(wav_list, dtype=np.float32)
                    if waveform.size == 0 or np.max(np.abs(waveform)) == 0:
                        raise ValueError(f"XTTS returned silent/empty audio for segment {i}")

                    samples = _float_to_int16(waveform)
                    dur = len(samples) / sample_rate
                    log.info("  Segment %d: %.2fs (max_amp=%.4f)", i, dur,
                             float(np.max(np.abs(waveform))))
                    results.append({
                        "samples":     samples,
                        "sample_rate": sample_rate,
                        "phrases":     [{"text": cleaned, "start": 0.0, "end": dur}],
                    })

                except Exception as e:
                    log.error(
                        "XTTS synthesis failed for segment %d (%r):\n%s",
                        i, text[:60], traceback.format_exc(),
                    )
                    raise RuntimeError(
                        f"XTTS failed on segment {i}: {e}\n"
                        "See full traceback in logs above.\n"
                        "Quick fixes:\n"
                        "  pip install soundfile          ← most likely fix\n"
                        "  pip install torchcodec         ← alternative\n"
                        "  pip install --upgrade torchaudio\n"
                        "  or switch to TTS_BACKEND='macos' in config"
                    ) from e

        log.info("XTTS-v2 generation complete (%d segments).", len(results))
        return results


def _silent_segment(text: str, sample_rate: int, duration: float = 2.0) -> dict:
    return {
        "samples":     np.zeros(int(sample_rate * duration), dtype=np.int16),
        "sample_rate": sample_rate,
        "phrases":     [{"text": text, "start": 0.0, "end": duration}],
    }


def _float_to_int16(waveform: np.ndarray) -> np.ndarray:
    max_val = np.max(np.abs(waveform))
    if max_val > 0:
        waveform = waveform / max_val * 0.95
    return (waveform * 32767).astype(np.int16)
