"""
core/tts/veena_strategy.py — Maya Research "Veena" TTS strategy.

Quality: very natural, expressive Hindi/English/code-mixed speech. It's a
3B-parameter Llama-architecture autoregressive model — heavier than the
other backends here (xtts ~similar, mms/kokoro/indic_parler much lighter).

Hardware reality check: Veena's reference implementation expects a CUDA
GPU (4-bit bitsandbytes quantization, .cuda() calls). bitsandbytes 4-bit
quantization is NOT available on Apple Silicon. On an M1 Mac this strategy
will fall back to loading the full model on MPS/CPU without quantization,
which is heavy (3B params, ~12-15GB+ RAM) and likely too slow or to OOM on
a MacBook Air. check_available() warns about this rather than blocking —
try it, but expect it may not be practical until you have CUDA (e.g. a
rented GPU box) to test on properly.

Install (NOT in requirements.txt by default — uncomment there, or):
    pip install transformers torch snac soundfile
    pip install bitsandbytes      # CUDA only — skip on Apple Silicon

To remove this backend entirely: delete this file and its one line in
core/tts/factory.py — nothing else references it.
"""

import numpy as np

from utils import get_logger
from core.tts.base import TTSStrategy
from core.lang.transliterate import clean_text

log = get_logger("tts.veena")

_DEFAULT_MODEL_ID = "maya-research/veena-tts"
_SNAC_MODEL_ID = "hubertsiuzdak/snac_24khz"

# Fixed control token IDs (from the Veena model card) — not configurable.
_START_OF_SPEECH_TOKEN = 128257
_END_OF_SPEECH_TOKEN = 128258
_START_OF_HUMAN_TOKEN = 128259
_END_OF_HUMAN_TOKEN = 128260
_START_OF_AI_TOKEN = 128261
_END_OF_AI_TOKEN = 128262
_AUDIO_CODE_BASE_OFFSET = 128266

_VALID_SPEAKERS = {"kavya", "agastya", "maitri", "vinaya"}


class VeenaStrategy(TTSStrategy):
    name = "veena"

    def check_available(self, cfg) -> None:
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
            import snac  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                f"TTS_BACKEND is 'veena' but a required package is missing: {e}.\n"
                "Install with:  pip install transformers torch snac soundfile"
            )
        import torch
        if not torch.cuda.is_available():
            log.warning(
                "Veena is designed for CUDA + 4-bit quantization. No CUDA GPU "
                "detected — falling back to an unquantized load on MPS/CPU, "
                "which needs a lot of RAM (3B params) and will be slow. "
                "This is expected/known on Apple Silicon, not a bug."
            )

    def synthesize_segments(self, texts: list[str], cfg) -> list[dict]:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from snac import SNAC

        model_id = getattr(cfg, "VEENA_MODEL_ID", _DEFAULT_MODEL_ID)
        speaker = getattr(cfg, "VEENA_SPEAKER", "kavya")
        if speaker not in _VALID_SPEAKERS:
            log.warning("Unknown VEENA_SPEAKER '%s', falling back to 'kavya'", speaker)
            speaker = "kavya"
        temperature = getattr(cfg, "VEENA_TEMPERATURE", 0.4)
        top_p = getattr(cfg, "VEENA_TOP_P", 0.9)

        use_cuda = torch.cuda.is_available()
        device = "cuda" if use_cuda else ("mps" if torch.backends.mps.is_available() else "cpu")
        log.info("Loading Veena model on %s …", device)

        load_kwargs = {"trust_remote_code": True}
        if use_cuda:
            from transformers import BitsAndBytesConfig
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
            )
            load_kwargs["device_map"] = "auto"
        else:
            load_kwargs["torch_dtype"] = torch.float32

        model = AutoModelForCausalLM.from_pretrained(model_id, **load_kwargs)
        if not use_cuda:
            model = model.to(device)
        model.eval()

        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        snac_model = SNAC.from_pretrained(_SNAC_MODEL_ID).eval().to(device)
        sample_rate = 24000

        results = []
        for i, text in enumerate(texts, 1):
            log.info("  TTS %d/%d: %s …", i, len(texts), text[:50])
            cleaned = clean_text(text, cfg)
            if not cleaned:
                results.append(_silent_segment(text, sample_rate))
                continue

            try:
                waveform = self._synthesize_one(
                    cleaned, speaker, model, tokenizer, snac_model, device, temperature, top_p,
                )
                samples = _float_to_int16(waveform)
                dur = len(samples) / sample_rate
                results.append({
                    "samples": samples,
                    "sample_rate": sample_rate,
                    "phrases": [{"text": cleaned, "start": 0.0, "end": dur}],
                })
            except Exception as e:
                log.warning("Veena TTS failed for segment %d: %s", i, e)
                results.append(_silent_segment(text, sample_rate))

        log.info("Veena generation complete.")
        return results

    def _synthesize_one(self, text, speaker, model, tokenizer, snac_model, device, temperature, top_p):
        import torch

        prompt = f"<spk_{speaker}> {text}"
        prompt_tokens = tokenizer.encode(prompt, add_special_tokens=False)
        input_tokens = [
            _START_OF_HUMAN_TOKEN, *prompt_tokens, _END_OF_HUMAN_TOKEN,
            _START_OF_AI_TOKEN, _START_OF_SPEECH_TOKEN,
        ]
        input_ids = torch.tensor([input_tokens], device=device)

        max_tokens = min(int(len(text) * 1.3) * 7 + 21, 700)

        with torch.no_grad():
            output = model.generate(
                input_ids,
                use_cache=True,
                max_new_tokens=max_tokens,
                do_sample=True,
                temperature=temperature,
                top_p=top_p,
                repetition_penalty=1.05,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=[_END_OF_SPEECH_TOKEN, _END_OF_AI_TOKEN],
            )

        generated_ids = output[0][len(input_tokens):].tolist()
        snac_tokens = [
            t for t in generated_ids
            if _AUDIO_CODE_BASE_OFFSET <= t < _AUDIO_CODE_BASE_OFFSET + 7 * 4096
        ]
        # Truncate to a whole number of 7-token SNAC frames
        snac_tokens = snac_tokens[: len(snac_tokens) - (len(snac_tokens) % 7)]
        if not snac_tokens:
            raise RuntimeError("Model produced no audio tokens")

        return _decode_snac(snac_tokens, snac_model, device)


def _decode_snac(snac_tokens: list[int], snac_model, device) -> np.ndarray:
    """De-interleave Veena's 7-tokens-per-frame SNAC codes into the 3
    hierarchical levels SNAC expects, then decode to a waveform. Logic
    follows the reference de-interleaving from the Veena model card."""
    import torch

    llm_codebook_offsets = [_AUDIO_CODE_BASE_OFFSET + i * 4096 for i in range(7)]
    codes_lvl = [[] for _ in range(3)]

    for i in range(0, len(snac_tokens), 7):
        codes_lvl[0].append(snac_tokens[i] - llm_codebook_offsets[0])
        codes_lvl[1].append(snac_tokens[i + 1] - llm_codebook_offsets[1])
        codes_lvl[1].append(snac_tokens[i + 4] - llm_codebook_offsets[4])
        codes_lvl[2].append(snac_tokens[i + 2] - llm_codebook_offsets[2])
        codes_lvl[2].append(snac_tokens[i + 3] - llm_codebook_offsets[3])
        codes_lvl[2].append(snac_tokens[i + 5] - llm_codebook_offsets[5])
        codes_lvl[2].append(snac_tokens[i + 6] - llm_codebook_offsets[6])

    hierarchical_codes = [
        torch.tensor(lvl, dtype=torch.int32, device=device).unsqueeze(0)
        for lvl in codes_lvl
    ]

    with torch.no_grad():
        audio = snac_model.decode(hierarchical_codes)

    return audio.squeeze().cpu().float().numpy()


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
