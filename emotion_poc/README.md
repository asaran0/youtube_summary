# Gemma → Emotion → TTS → Video POC

Hindi story / motivational speech / book summary generator with emotion-aware narration.

## Architecture

```
config.py          ← edit this only
   │
   ▼
llm/generator.py   Stage 1: Gemma 3 4B generates Hindi script
   │
   ▼
emotion/injector.py Stage 2: Tags each sentence with emotion (CALM / INTENSE / HOPEFUL …)
   │
   ▼
tts/synthesizer.py  Stage 3: Synthesizes audio, emotion guides voice style
   │
   ▼
pipeline/video.py   Stage 4: Coloured slideshow + background music → MP4
```

Each stage is a single file. Swap a stage by changing one line in config.py.

---

## Setup — M1 MacBook Air 8 GB

### 1. Install Ollama + Gemma (recommended — no coding needed)
```bash
brew install ollama
ollama serve         # in a separate terminal
ollama pull gemma3:4b
```

### 2. Install Python dependencies
```bash
pip install kokoro soundfile numpy   # fast TTS, no GPU needed
brew install ffmpeg espeak-ng        # video + kokoro phonemizer
```

### 3. Run
```bash
cd emotion_poc
python run.py --dry-run   # check plan first
python run.py             # full pipeline
```

---

## Swapping stages

### Use Indic Parler-TTS instead of Kokoro (better Hindi quality, slower)
```bash
pip install git+https://github.com/huggingface/parler-tts.git
```
Then in config.py:
```python
TTS_BACKEND = "indic_parler"
```
⚠️ On M1 8 GB: Gemma will be unloaded automatically before TTS loads.
Expect ~45s per sentence. Run stages separately to avoid memory spikes:
```bash
python run.py --stage llm      # generate text (Gemma in RAM)
python run.py --stage emotion  # tag emotions  (no model needed)
python run.py --stage tts      # Gemma unloaded, Parler loads fresh
python run.py --stage video    # no ML at all
```

### Use llama.cpp instead of Ollama
```bash
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/metal
# Download GGUF: https://huggingface.co/google/gemma-3-4b-it-GGUF
```
Then in config.py:
```python
LLM_BACKEND          = "llama_cpp"
LLAMA_CPP_MODEL_PATH = "models/gemma-3-4b-it-q4_k_m.gguf"
```

### Generate English content
```python
LANGUAGE      = "en"
CONTENT_TYPE  = "speech"
TOPIC         = "Overcoming failure to find success"
```

### Add background music
```python
BACKGROUND_MUSIC_PATH   = "assets/music/calm_loop.mp3"
BACKGROUND_MUSIC_VOLUME = 0.12   # 12% volume
```

### Skip video, audio only
```python
VIDEO_BACKEND = "none"
```

---

## Output files
```
output/
  story_video.mp4          ← final video
temp/
  llm_out.txt              ← generated script (Stage 1)
  emotion_out.json         ← tagged sentences (Stage 2)
  merged_audio.wav         ← TTS audio (Stage 3)
  seg_000.wav … seg_N.wav  ← per-sentence audio
```

## Expected timings on M1 8 GB (Kokoro TTS)

| Stage        | Time       |
|--------------|------------|
| Gemma (Ollama) 150 words | ~15–25s |
| Emotion injection | <1s |
| Kokoro TTS 10 sentences | ~30–60s |
| Video assembly (ffmpeg) | ~10s |
| **Total** | **~1–2 min** |

With Indic Parler-TTS: ~10–15 min for 10 sentences on M1 (MPS).
