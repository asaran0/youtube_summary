"""
emotion_poc/config.py — Master config for the Gemma → Emotion → TTS pipeline POC.

HOW TO USE:
  1. Edit settings below.
  2. Run:  python run.py  (full pipeline)
      or:  python run.py --stage llm        (just text generation)
           python run.py --stage emotion     (just emotion injection, reads llm_out.json)
           python run.py --stage tts         (just TTS, reads emotion_out.json)
           python run.py --stage video       (just video, reads tts audio)

TO SWAP A STAGE: change the *_BACKEND values below — nothing else to touch.
TO DISABLE A STAGE: set it to "passthrough" or "none".
"""

# ─────────────────────────────────────────────────────────────────
#  INPUT
# ─────────────────────────────────────────────────────────────────

# What you want to generate. One of:
#   "story"       — Hindi motivational story
#   "speech"      — motivational speech (Hindi or English)
#   "book_summary"— audio book summary
CONTENT_TYPE = "story"

# The topic / prompt (Hindi or English — Gemma handles both)
TOPIC = "Romantic story in rain of a couple kissing"  # "A farmer who never gives up"

# Target language for TTS output
# "hi" = Hindi  |  "en" = English  |  "hig" = Hinglish
LANGUAGE = "hi"

# Rough target length in words for the generated script
TARGET_WORDS = 150

# ─────────────────────────────────────────────────────────────────
#  STAGE 1 — LLM (text generation)
# ─────────────────────────────────────────────────────────────────

# "ollama"    — Gemma 3 via Ollama (recommended for M1, zero setup after install)
# "llama_cpp" — Gemma 3 via llama-cpp-python (manual GGUF download needed)
# "openai"    — OpenAI-compatible API (GPT-4o etc.)
# "mock"      — returns hardcoded sample text (for testing without GPU)
LLM_BACKEND = "ollama"

# Ollama settings (used when LLM_BACKEND = "ollama")
OLLAMA_MODEL   = "gemma3:4b"   # run: ollama pull gemma3:4b
OLLAMA_BASE_URL = "http://localhost:11434"

# llama-cpp settings (used when LLM_BACKEND = "llama_cpp")
LLAMA_CPP_MODEL_PATH = "models/gemma-3-4b-it-q4_k_m.gguf"
LLAMA_CPP_N_GPU_LAYERS = -1   # -1 = all layers on Metal (MPS)
LLAMA_CPP_N_CTX = 4096

# OpenAI settings (used when LLM_BACKEND = "openai")
OPENAI_API_KEY  = ""           # or set env var OPENAI_API_KEY
OPENAI_MODEL    = "gpt-4o-mini"
OPENAI_BASE_URL = ""           # leave empty for default OpenAI; set for local servers

# ─────────────────────────────────────────────────────────────────
#  STAGE 2 — EMOTION INJECTOR
# ─────────────────────────────────────────────────────────────────

# "rule_based"  — fast, deterministic, uses punctuation + keywords  (default)
# "llm_based"   — asks Gemma to tag each sentence (slower, richer)
# "passthrough" — skip emotion injection entirely
EMOTION_BACKEND = "rule_based"

# Emotions the injector can assign. Map to Parler-TTS description fragments.
# Add/remove emotions here — TTS stage reads this automatically.
EMOTION_MAP = {
    "CALM":     "speaks in a calm, gentle tone with a steady pace",
    "INTENSE":  "speaks with intensity and strong emphasis",
    "HOPEFUL":  "speaks with warmth and optimism in their voice",
    "SAD":      "speaks softly with a hint of sadness",
    "EXCITED":  "speaks with high energy and excitement",
    "NEUTRAL":  "speaks clearly at a moderate pace",
}

# ─────────────────────────────────────────────────────────────────
#  STAGE 3 — TTS
# ─────────────────────────────────────────────────────────────────

# "kokoro"       — fastest on M1, ~350 MB, good Hindi (RECOMMENDED)
# "indic_parler" — best quality Hindi, ~1.4 GB, slow on M1 (~45s/sentence)
# "macos"        — zero setup, uses macOS Say command, limited Hindi
# "mms"          — offline neural, moderate quality
# "mock"         — writes silence (for testing video stage without TTS)
TTS_BACKEND = "kokoro"

# Kokoro voices (used when TTS_BACKEND = "kokoro")
KOKORO_VOICES = {
    "hi":  "hm_omega",   # Hindi male    (try "hf_alpha" for female)
    "en":  "am_adam",    # English male  (try "af_heart" for female)
    "hig": "hm_omega",
}
KOKORO_SPEED = 0.95  # slightly slower for emotional delivery

# Indic Parler voice descriptions (used when TTS_BACKEND = "indic_parler")
# These are overridden per-sentence by the emotion injector.
INDIC_PARLER_MODEL_ID  = "ai4bharat/indic-parler-tts"
INDIC_PARLER_BASE_DESCRIPTION = {
    "hi":  "Rohit's voice is clear and natural. The recording is of very high quality, with no background noise.",
    "en":  "A clear natural speaker with moderate speed.",
    "hig": "Rohit's voice is clear and natural.",
}

# macOS TTS voice (used when TTS_BACKEND = "macos")
MACOS_VOICE = "Lekha"   # Hindi voice on macOS. Run: say -v ? | grep hi

# ─────────────────────────────────────────────────────────────────
#  STAGE 4 — VIDEO / AUDIO ASSEMBLY
# ─────────────────────────────────────────────────────────────────

# "slideshow"   — generates a simple colour-background slideshow video
# "none"        — audio only, no video
VIDEO_BACKEND = "slideshow"

# Background music (set to "" to disable)
BACKGROUND_MUSIC_PATH = ""      # e.g. "assets/music/lofi_calm.mp3"
BACKGROUND_MUSIC_VOLUME = 0.12  # 0.0 – 1.0

# Output resolution
OUTPUT_MODE = "reel"   # "reel" = 1080x1920 vertical | "full" = 1920x1080 landscape
OUTPUT_FPS  = 30

# ─────────────────────────────────────────────────────────────────
#  PATHS
# ─────────────────────────────────────────────────────────────────
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_HERE, "output")
TEMP_DIR   = os.path.join(_HERE, "temp")
