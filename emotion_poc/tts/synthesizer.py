"""
emotion_poc/tts/synthesizer.py — Stage 3: Emotion-aware TTS synthesis.

Input:  list of {"text", "emotion", "description"} from emotion injector
Output: path to a merged WAV file

Supported backends: kokoro | indic_parler | macos | mms | mock

MEMORY NOTE for M1 8 GB:
  If LLM_BACKEND = "ollama" or "llama_cpp", Gemma is still in RAM.
  Call release_llm() before loading indic_parler to avoid OOM.
  kokoro and macos don't need this — they're tiny.
"""

import os
import gc
import struct
import wave
import numpy as np


# ── Memory management ─────────────────────────────────────────────────────────

def release_llm():
    """
    Nudge Python + MPS to release GPU memory after LLM stage.
    Call this before loading a large TTS model (indic_parler) on M1 8 GB.
    """
    try:
        import torch
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:
        pass
    gc.collect()
    print("[tts] GPU memory released (called before TTS model load)")


# ── WAV helpers ───────────────────────────────────────────────────────────────

def _samples_to_wav(path: str, samples: np.ndarray, sample_rate: int):
    """Write int16 numpy array to a WAV file."""
    if samples.dtype != np.int16:
        max_val = np.max(np.abs(samples)) or 1
        samples = (samples / max_val * 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())


def _merge_wavs(paths: list[str], out_path: str, gap_ms: int = 200):
    """Merge multiple WAV files, inserting a short silence between each."""
    if not paths:
        raise ValueError("No WAV files to merge")

    # Read first file to get params
    with wave.open(paths[0], "r") as wf:
        sr   = wf.getframerate()
        sw   = wf.getsampwidth()
        nch  = wf.getnchannels()

    gap_samples = int(sr * gap_ms / 1000)
    silence     = b'\x00' * gap_samples * sw * nch

    with wave.open(out_path, "w") as out:
        out.setnchannels(nch)
        out.setsampwidth(sw)
        out.setframerate(sr)
        for i, path in enumerate(paths):
            with wave.open(path, "r") as wf:
                out.writeframes(wf.readframes(wf.getnframes()))
            if i < len(paths) - 1:
                out.writeframes(silence)


def _silent_wav(path: str, duration: float = 1.0, sample_rate: int = 22050):
    samples = np.zeros(int(sample_rate * duration), dtype=np.int16)
    _samples_to_wav(path, samples, sample_rate)


# ── Backend: kokoro ───────────────────────────────────────────────────────────

def _synthesize_kokoro(tagged: list[dict], cfg, temp_dir: str) -> list[str]:
    try:
        from kokoro import KPipeline
    except ImportError:
        raise RuntimeError(
            "kokoro not installed.\n"
            "Install: pip install kokoro  (also: brew install espeak-ng)"
        )

    voice      = cfg.KOKORO_VOICES.get(cfg.LANGUAGE, "hm_omega")
    speed      = getattr(cfg, "KOKORO_SPEED", 0.88)
    sample_rate = 24000

    print(f"[tts/kokoro] voice={voice}  speed={speed}")
    pipeline = KPipeline(lang_code=cfg.LANGUAGE[:2])

    paths = []
    for i, item in enumerate(tagged):
        out_path = os.path.join(temp_dir, f"seg_{i:03d}.wav")
        try:
            generator = pipeline(item["text"], voice=voice, speed=speed)
            chunks    = [chunk.numpy() for _, _, chunk in generator]
            if chunks:
                audio = np.concatenate(chunks)
                _samples_to_wav(out_path, audio, sample_rate)
            else:
                _silent_wav(out_path, 0.5, sample_rate)
        except Exception as e:
            print(f"[tts/kokoro] segment {i} failed: {e}")
            _silent_wav(out_path, 0.5, sample_rate)
        paths.append(out_path)
        print(f"[tts/kokoro]   {i+1}/{len(tagged)} [{item['emotion']}] {item['text'][:50]}")
    return paths


# ── Backend: indic_parler ─────────────────────────────────────────────────────

def _synthesize_indic_parler(tagged: list[dict], cfg, temp_dir: str) -> list[str]:
    """
    Each sentence gets a description string built from:
        INDIC_PARLER_BASE_DESCRIPTION + emotion description fragment
    """
    try:
        import torch
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer
    except ImportError:
        raise RuntimeError(
            "parler-tts not installed.\n"
            "Install: pip install git+https://github.com/huggingface/parler-tts.git"
        )

    device = ("mps" if torch.backends.mps.is_available()
               else "cuda" if torch.cuda.is_available()
               else "cpu")
    print(f"[tts/indic_parler] device={device}  loading model (may take 30–60s)…")

    model_id  = getattr(cfg, "INDIC_PARLER_MODEL_ID", "ai4bharat/indic-parler-tts")
    model     = ParlerTTSForConditionalGeneration.from_pretrained(model_id).to(device)
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    desc_tok  = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)
    sr        = model.config.sampling_rate

    base_desc = getattr(cfg, "INDIC_PARLER_BASE_DESCRIPTION", {}).get(
        cfg.LANGUAGE, "Rohit speaks clearly and naturally."
    )

    paths = []
    for i, item in enumerate(tagged):
        out_path = os.path.join(temp_dir, f"seg_{i:03d}.wav")
        # Build per-sentence description (base + emotion)
        description = f"{base_desc} The speaker {item['description']}."
        try:
            desc_ids   = desc_tok(description, return_tensors="pt").input_ids.to(device)
            prompt_ids = tokenizer(item["text"], return_tensors="pt").input_ids.to(device)
            with torch.no_grad():
                gen = model.generate(input_ids=desc_ids, prompt_input_ids=prompt_ids)
            waveform = gen.cpu().numpy().squeeze()
            _samples_to_wav(out_path, waveform, sr)
        except Exception as e:
            print(f"[tts/indic_parler] segment {i} failed: {e}")
            _silent_wav(out_path, 1.0, sr)
        paths.append(out_path)
        print(f"[tts/indic_parler]   {i+1}/{len(tagged)} [{item['emotion']}] "
              f"{item['text'][:50]}")
    return paths


# ── Backend: macos ────────────────────────────────────────────────────────────

def _synthesize_macos(tagged: list[dict], cfg, temp_dir: str) -> list[str]:
    import subprocess, shutil
    voice = getattr(cfg, "MACOS_VOICE", "Lekha")
    paths = []
    for i, item in enumerate(tagged):
        aiff_path = os.path.join(temp_dir, f"seg_{i:03d}.aiff")
        out_path  = os.path.join(temp_dir, f"seg_{i:03d}.wav")
        subprocess.run(
            ["say", "-v", voice, "-o", aiff_path, item["text"]],
            check=True, capture_output=True,
        )
        # Convert aiff → wav via ffmpeg if available
        if shutil.which("ffmpeg"):
            subprocess.run(
                ["ffmpeg", "-y", "-i", aiff_path, "-ar", "22050", out_path],
                check=True, capture_output=True,
            )
        else:
            os.rename(aiff_path, out_path)
        paths.append(out_path)
        print(f"[tts/macos]   {i+1}/{len(tagged)} [{item['emotion']}] {item['text'][:50]}")
    return paths


# ── Backend: mock ─────────────────────────────────────────────────────────────

def _synthesize_mock(tagged: list[dict], cfg, temp_dir: str) -> list[str]:
    paths = []
    for i, item in enumerate(tagged):
        out_path = os.path.join(temp_dir, f"seg_{i:03d}.wav")
        words = len(item["text"].split())
        _silent_wav(out_path, duration=max(1.0, words * 0.4))
        paths.append(out_path)
        print(f"[tts/mock]   {i+1}/{len(tagged)} [{item['emotion']}] (silence)")
    return paths


# ── Public entry point ────────────────────────────────────────────────────────

def synthesize(tagged: list[dict], cfg, temp_dir: str) -> str:
    """
    Run stage 3: synthesize TTS for each tagged sentence.
    Returns path to merged WAV file.
    """
    os.makedirs(temp_dir, exist_ok=True)
    backend = cfg.TTS_BACKEND.lower()

    print(f"[tts] backend={backend}  {len(tagged)} segments")

    # For large TTS models on M1 8 GB — release LLM memory first
    if backend == "indic_parler":
        release_llm()

    if backend == "kokoro":
        seg_paths = _synthesize_kokoro(tagged, cfg, temp_dir)
    elif backend == "indic_parler":
        seg_paths = _synthesize_indic_parler(tagged, cfg, temp_dir)
    elif backend == "macos":
        seg_paths = _synthesize_macos(tagged, cfg, temp_dir)
    elif backend == "mock":
        seg_paths = _synthesize_mock(tagged, cfg, temp_dir)
    else:
        raise ValueError(f"Unknown TTS_BACKEND: {backend!r}. "
                         "Choose: kokoro | indic_parler | macos | mms | mock")

    # Merge all segments into one WAV
    merged_path = os.path.join(temp_dir, "merged_audio.wav")
    _merge_wavs(seg_paths, merged_path, gap_ms=250)
    print(f"[tts] merged audio → {merged_path}")
    return merged_path
