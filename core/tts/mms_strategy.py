"""
core/tts/mms_strategy.py — Meta MMS-TTS strategy.

Quality: neural, natural-sounding Hindi, no voice cloning.
Speed: medium (uses Apple MPS on M-series Macs automatically).
Needs: pip install transformers torch.

Model is downloaded once (~500 MB) and cached locally; subsequent
runs are fully offline.
"""

import os

import numpy as np

from utils import get_logger
from core.tts.base import TTSStrategy
from core.tts.audio_utils import (
    normalize_and_write_wav, resample_wav, polish_audio,
)
from core.lang.transliterate import clean_text

log = get_logger("tts.mms")


class MMSStrategy(TTSStrategy):
    name = "mms"

    def check_available(self, cfg) -> None:
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
            import scipy  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                f"TTS_BACKEND is 'mms' but a required package is missing: {e}.\n"
                "Install with:  pip install transformers torch scipy"
            )

    def synthesize(self, texts: list[str], output_path: str, cfg) -> list[dict]:
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
        pause_samples = int(sample_rate * cfg.TTS_PAUSE_BETWEEN_SEGMENTS)

        all_audio = []
        timings = []

        for i, text in enumerate(texts, 1):
            log.info("  TTS %d/%d: %s …", i, len(texts), text[:50])
            text = clean_text(text, cfg)
            if not text:
                continue

            try:
                inputs = tokenizer(text, return_tensors="pt").to(device)
                with torch.no_grad():
                    output = model(**inputs)

                waveform = output.waveform.squeeze().cpu().numpy()
                all_audio.append(waveform)
                dur = len(waveform) / sample_rate
                timings.append({
                    "duration": dur,
                    "phrases": [{"text": text, "start": 0.0, "end": dur}],
                })
                all_audio.append(np.zeros(pause_samples, dtype=np.float32))

            except Exception as e:
                log.warning("TTS failed for segment %d: %s", i, e)
                silence = np.zeros(int(sample_rate * 2), dtype=np.float32)
                all_audio.append(silence)
                timings.append({
                    "duration": 2.0,
                    "phrases": [{"text": text, "start": 0.0, "end": 2.0}],
                })

        tmp_wav = os.path.join(cfg.TEMP_DIR, "tts_raw_mms.wav")
        normalize_and_write_wav(all_audio, sample_rate, tmp_wav)

        resampled_wav = os.path.join(cfg.TEMP_DIR, "tts_mms_resampled.wav")
        resample_wav(tmp_wav, resampled_wav, target_rate=44100)
        polish_audio(resampled_wav, output_path, cfg)
        log.info("MMS-TTS generation complete.")
        return timings
