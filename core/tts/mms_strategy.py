"""
core/tts/mms_strategy.py — Meta MMS-TTS strategy.

Quality: neural, natural-sounding Hindi, no voice cloning.
Speed: medium (uses Apple MPS on M-series Macs automatically).
Needs: pip install transformers torch.

Model is downloaded once (~500 MB) and cached locally; subsequent
runs are fully offline.
"""

import numpy as np

from utils import get_logger
from core.tts.base import TTSStrategy
from core.lang.transliterate import clean_text

log = get_logger("tts.mms")


class MMSStrategy(TTSStrategy):
    name = "mms"

    def check_available(self, cfg) -> None:
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                f"TTS_BACKEND is 'mms' but a required package is missing: {e}.\n"
                "Install with:  pip install transformers torch"
            )

    def synthesize_segments(self, texts: list[str], cfg,
                            is_answer_flags: list[bool] | None = None) -> list[dict]:
        import torch
        from transformers import VitsModel, AutoTokenizer

        log.info("Loading MMS-TTS model (first run downloads model files) …")
        model_id = cfg.MMS_TTS_MODEL_IDS.get(cfg.LANGUAGE, "facebook/mms-tts-hin")

        tokenizer = AutoTokenizer.from_pretrained(model_id)

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        log.info("TTS device: %s", device)

        model = VitsModel.from_pretrained(model_id).to(device)
        model.eval()

        sample_rate = model.config.sampling_rate
        results = []

        for i, text in enumerate(texts, 1):
            log.info("  TTS %d/%d: %s …", i, len(texts), text[:50])
            cleaned = clean_text(text, cfg)
            if not cleaned:
                results.append(_silent_segment(text, sample_rate))
                continue

            try:
                inputs = tokenizer(cleaned, return_tensors="pt").to(device)
                with torch.no_grad():
                    output = model(**inputs)

                waveform = output.waveform.squeeze().cpu().numpy()
                samples = _float_to_int16(waveform)
                dur = len(samples) / sample_rate
                results.append({
                    "samples": samples,
                    "sample_rate": sample_rate,
                    "phrases": [{"text": cleaned, "start": 0.0, "end": dur}],
                })

            except Exception as e:
                log.warning("TTS failed for segment %d: %s", i, e)
                results.append(_silent_segment(text, sample_rate))

        log.info("MMS-TTS generation complete.")
        return results


def _silent_segment(text: str, sample_rate: int, duration: float = 2.0) -> dict:
    n_samples = int(sample_rate * duration)
    return {
        "samples": np.zeros(n_samples, dtype=np.int16),
        "sample_rate": sample_rate,
        "phrases": [{"text": text, "start": 0.0, "end": duration}],
    }


def _float_to_int16(waveform: np.ndarray) -> np.ndarray:
    """Convert a float32 [-1, 1] waveform to normalized int16 PCM."""
    max_val = np.max(np.abs(waveform))
    if max_val > 0:
        waveform = waveform / max_val * 0.95
    return (waveform * 32767).astype(np.int16)
