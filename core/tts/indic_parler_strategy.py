"""
core/tts/indic_parler_strategy.py — AI4Bharat Indic Parler-TTS strategy.

Quality: natural-sounding, supports 21 Indic languages + English, voice
style is controlled by a plain-English *description* prompt (e.g. "A
female speaker delivers a slightly expressive speech...") rather than a
voice-sample file — no voice cloning, but easy to steer tone/gender/speed.

Install (NOT in requirements.txt by default — uncomment there, or):
    pip install git+https://github.com/huggingface/parler-tts.git
    pip install soundfile

First run downloads the model (~1-2 GB) and caches it locally.

To remove this backend entirely: delete this file and its one line in
core/tts/factory.py — nothing else references it.
"""

import numpy as np

from utils import get_logger
from core.tts.base import TTSStrategy
from core.lang.transliterate import clean_text

log = get_logger("tts.indic_parler")

_DEFAULT_MODEL_ID = "ai4bharat/indic-parler-tts"

_DEFAULT_DESCRIPTIONS = {
    "hi": "Rohit's voice is clear and natural, with a moderate speed and pitch. The recording is of very high quality, with no background noise.",
    "en": "A female speaker delivers a clear, natural speech with a moderate speed and pitch. The recording is of very high quality, with no background noise.",
    "hig": "Rohit's voice is clear and natural, with a moderate speed and pitch. The recording is of very high quality, with no background noise.",
}


class IndicParlerStrategy(TTSStrategy):
    name = "indic_parler"

    def check_available(self, cfg) -> None:
        try:
            import parler_tts  # noqa: F401
            import torch  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                f"TTS_BACKEND is 'indic_parler' but a required package is missing: {e}.\n"
                "Install with:\n"
                "  pip install git+https://github.com/huggingface/parler-tts.git\n"
                "  pip install soundfile"
            )

    def synthesize_segments(self, texts: list[str], cfg,
                            is_answer_flags: list[bool] | None = None) -> list[dict]:
        import torch
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        model_id = getattr(cfg, "INDIC_PARLER_MODEL_ID", _DEFAULT_MODEL_ID)
        description = getattr(cfg, "INDIC_PARLER_DESCRIPTION", None) or \
            _DEFAULT_DESCRIPTIONS.get(cfg.LANGUAGE, _DEFAULT_DESCRIPTIONS["en"])

        device = "cuda" if torch.cuda.is_available() else (
            "mps" if torch.backends.mps.is_available() else "cpu"
        )
        log.info("Loading Indic Parler-TTS model on %s (first run downloads ~1-2 GB) …", device)

        model = ParlerTTSForConditionalGeneration.from_pretrained(model_id).to(device)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        description_tokenizer = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)
        sample_rate = model.config.sampling_rate

        description_ids = description_tokenizer(description, return_tensors="pt").input_ids.to(device)

        results = []
        for i, text in enumerate(texts, 1):
            log.info("  TTS %d/%d: %s …", i, len(texts), text[:50])
            cleaned = clean_text(text, cfg)
            if not cleaned:
                results.append(_silent_segment(text, sample_rate))
                continue

            try:
                prompt_ids = tokenizer(cleaned, return_tensors="pt").input_ids.to(device)
                with torch.no_grad():
                    generation = model.generate(input_ids=description_ids, prompt_input_ids=prompt_ids)

                waveform = generation.cpu().numpy().squeeze()
                samples = _float_to_int16(waveform)
                dur = len(samples) / sample_rate
                results.append({
                    "samples": samples,
                    "sample_rate": sample_rate,
                    "phrases": [{"text": cleaned, "start": 0.0, "end": dur}],
                })

            except Exception as e:
                log.warning("Indic Parler-TTS failed for segment %d: %s", i, e)
                results.append(_silent_segment(text, sample_rate))

        log.info("Indic Parler-TTS generation complete.")
        return results


def _silent_segment(text: str, sample_rate: int, duration: float = 2.0) -> dict:
    n_samples = int(sample_rate * duration)
    return {
        "samples": np.zeros(n_samples, dtype=np.int16),
        "sample_rate": sample_rate,
        "phrases": [{"text": text, "start": 0.0, "end": duration}],
    }


def _float_to_int16(waveform: np.ndarray) -> np.ndarray:
    max_val = np.max(np.abs(waveform))
    if max_val > 0:
        waveform = waveform / max_val * 0.95
    return (waveform * 32767).astype(np.int16)
