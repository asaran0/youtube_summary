# Ebook Mode — Complete Architecture & Configuration Guide

This document covers the full pipeline, every config option, known issues (and their
fixes), and how to operate the system without a Pixabay API key.

---

## Table of Contents

1. [Project Layout](#1-project-layout)
2. [Pipeline — How a Video is Made](#2-pipeline--how-a-video-is-made)
3. [Input File Format](#3-input-file-format)
4. [Configuration Reference (`config.py`)](#4-configuration-reference-configpy)
   - Language
   - Output mode & resolution
   - TTS / Voice
   - Pacing & pauses
   - Background visuals
   - Pixabay integration
   - Typography & colours
   - Channel badge & waveform
   - Audio post-processing & background music
   - Encoding
5. [Known Issues & Fixes](#5-known-issues--fixes)
   - Pink tint on video images
   - Second code line not spoken (QA mode)
6. [Pixabay — Offline / Cache Mode](#6-pixabay--offline--cache-mode)
7. [Running the Pipeline](#7-running-the-pipeline)
8. [Output Files](#8-output-files)
9. [Quick Cheat Sheet](#9-quick-cheat-sheet)

---

## 1. Project Layout

```
ebook/
├── main.py                     ← entry point  (python main.py --mode ebook ...)
├── ebook_mode/
│   ├── config.py               ← ALL settings live here — start here
│   ├── loader.py               ← parses the .txt book file → typed chunks
│   ├── runner.py               ← orchestrates the 4-step pipeline
│   ├── video.py                ← frame-by-frame renderer + ffmpeg mux
│   ├── render.py               ← special frames: chapter card, quote, lesson
│   └── README.md               ← this file
├── core/
│   ├── pixabay.py              ← Pixabay API client + keyword extractor + cache
│   ├── fonts.py                ← font loading with Devanagari/RAQM shaping
│   ├── overlay_crawl.py        ← optional crawling ticker overlay
│   ├── lang/
│   │   ├── transliterate.py    ← Hindi romanisation for TTS
│   │   ├── tokenize.py         ← sentence tokeniser (handles दंड / ।)
│   │   ├── roman_hindi.py      ← Hinglish → Devanagari mapping
│   │   └── dictionary.py       ← phonetic overrides (EXTRA_PHONETIC_DICT)
│   ├── render/
│   │   ├── banners.py          ← chapter-title banner helper
│   │   ├── subtitles.py        ← SRT writer
│   │   ├── slideshow.py        ← Ken Burns / image-slideshow renderer
│   │   └── metadata.py         ← YouTube metadata writer
│   └── tts/
│       ├── pipeline.py         ← stitches TTS chunks + pause timing
│       ├── factory.py          ← picks the right strategy
│       ├── kokoro_strategy.py  ← Kokoro (best quality, default)
│       ├── macos_strategy.py   ← macOS `say` (zero setup)
│       ├── xtts_strategy.py    ← XTTS voice cloning
│       ├── mms_strategy.py     ← Meta MMS (offline, one fixed voice)
│       ├── veena_strategy.py   ← Veena (Indian voices)
│       └── indic_parler_strategy.py  ← Indic Parler
├── assets/
│   ├── pixabay_cache/          ← downloaded & resized background images
│   ├── NotoSansDevanagari-Regular.ttf
│   └── fonts/NotoSans-Bold.ttf
├── background/
│   ├── reel_bg.png             ← default static background (reels)
│   └── cinematic.mp3           ← optional background music
└── output/ebook/               ← final .mp4 + .srt + chapter index
```

---

## 2. Pipeline — How a Video is Made

```
.txt book file
    │
    ▼  STEP 1 — ebook_mode/loader.py
    Parse into typed chunks:
      chapter_card  → full-screen chapter title card
      lesson        → warm-yellow key-lesson panel
      quote         → gold left-bar blockquote callout
      narration     → word-by-word subtitle with progress bar
    │
    ▼  STEP 2 — core/tts/pipeline.py  (via runner._generate_tts)
    TTS: each chunk's text → WAV audio
    Pauses injected between chapter_card / lesson / quote
    Audio post-processed (EQ, compression, loudnorm)
    │
    ▼  STEP 3 — runner._retime_chunks
    Real timestamps from TTS output (new_start / new_end per chunk)
    │
    ▼  STEP 4 — ebook_mode/video.py  (+ optional Pixabay download)
    Step A: MoviePy VideoClip renders frames per chunk type
    Step B: ffmpeg overlays looping waveform animation (screen blend)
    Step C: ffmpeg muxes narration audio (+ optional background music)
    │
    ▼  OUTPUT
    output/ebook/<title>_ebook_summary.mp4
    output/ebook/<title>.srt
    output/ebook/<title>_chapters.txt   (YouTube timestamp index)
```

### Chunk types and their visual treatment

| chunk_type     | Visual                                              | Speaking        |
|----------------|-----------------------------------------------------|-----------------|
| `chapter_card` | Full dark screen, gold divider, chapter number      | Chapter title   |
| `lesson`       | Semi-transparent warm-yellow panel over background  | Lesson text     |
| `quote`        | Gold left bar + translucent dark box, word-reveal   | Quote text      |
| `narration`    | Word-by-word subtitle + progress bar, over bg       | Sentence text   |

---

## 3. Input File Format

```
# Book Title                          ← H1: parsed as book title (one line)
## Author: Robert Kiyosaki            ← metadata key: value
## Tagline: What the rich teach...    ← metadata key: value

## Chapter 1: Rich Dad, Poor Dad      ← H2 with number → chapter_card chunk
### Key Lesson                         ← H3 → lesson chunk (label only, not spoken again)
The rich don't work for money.         ← plain text → narration chunk(s)

One short sentence per line is best — each line becomes its own TTS chunk
and its own subtitle card on screen.

> "The poor and middle class work      ← lines starting > → quote chunk
>  for money. The rich have money      ← continuation lines joined automatically
>  work for them."

More narration here after the quote.

## Chapter 2: The Rich Don't Work for Money
...
```

**Rules:**
- `# Title` — exactly one, at the top.
- `## Author: ...` / `## Tagline: ...` — metadata, not spoken or shown as chapter.
- `## Chapter N: ...` — triggers a chapter card. N must be a number.
- `### Heading` — becomes a lesson card. If the heading text *is* the lesson
  label (e.g. "Key Lesson", "मुख्य सीख"), it is not prefixed again.
- `> "Quote text"` — one or multiple `>` lines are merged into one quote card.
- Everything else → narration (split into sentences automatically).

---

## 4. Configuration Reference (`config.py`)

### Language

```python
LANGUAGE = "hi"   # "en" | "hi" | "hig"
```

| Value | Effect |
|-------|--------|
| `"en"` | English. Latin font, English TTS voice, English chapter labels ("CHAPTER 1"). |
| `"hi"` | Hindi. Devanagari font, Hindi TTS voice, Hindi chapter labels ("अध्याय 1"). Audio EQ tuned for Hindi vocal range. |
| `"hig"` | Hinglish. Devanagari font (mixed script renders correctly), same voice set as `"hi"`, English-style chapter labels. |

**This one setting drives font selection, TTS voice, audio EQ, chapter labels, and sentence splitting.** You do not need to change anything else when switching languages.

---

### Output mode & resolution

```python
OUTPUT_MODE    = "full"   # "full" (YouTube landscape) | "reel" (Shorts/Reels vertical)
YOUTUBE_WIDTH  = 1920
YOUTUBE_HEIGHT = 1080
REEL_WIDTH     = 1080
REEL_HEIGHT    = 1920
OUTPUT_FPS     = 30
```

For Reels also set:
```python
PIXABAY_ORIENTATION = "vertical"   # downloads portrait-format photos
```

---

### TTS / Voice

```python
TTS_BACKEND = "kokoro"   # "kokoro" | "macos" | "xtts" | "mms" | "indic_parler" | "veena"
```

| Backend | Quality | Setup | Notes |
|---------|---------|-------|-------|
| `kokoro` | ★★★★★ | pip install | Best. Multiple male/female Hindi+English voices. **Recommended.** |
| `macos` | ★★★☆☆ | Zero — uses system `say` | Lekha for Hindi, Daniel/Samantha for English. Quick testing. |
| `xtts` | ★★★★☆ | Voice sample WAV needed | Clone any voice from a 10-30s clean recording. |
| `mms` | ★★★☆☆ | Downloads ~500 MB model | Offline after download. One fixed voice per language. |
| `indic_parler` | ★★★★☆ | pip install | Steered by a text description prompt. Good for emotional delivery. |
| `veena` | ★★★☆☆ | pip install | Indian accent, decent Hindi naturalness. |

```python
EBOOK_VOICE_GENDER = "male"   # "male" | "female"
```

Changing `EBOOK_VOICE_GENDER` automatically picks the right voice for the chosen
`TTS_BACKEND` — you don't need to manually update `KOKORO_VOICES` or `MACOS_TTS_VOICE`.

```python
KOKORO_SPEED = 0.90   # 0.80 = slow/authoritative  0.95 = near-natural pace
```

Kokoro voice options for reference:
- Hindi male: `hm_omega` (★ recommended), `hm_psi`
- Hindi female: `hf_alpha` (★ recommended), `hf_beta`
- English male: `am_adam` (deep), `am_michael` (warm), `am_onyx` (rich)
- English female: `af_heart` (emotive★), `af_bella`, `af_nicole`

For XTTS (voice cloning), put your clean WAV samples here:
```python
XTTS_VOICE_SAMPLE = "assets/clean_voice_story.wav"          # male
# female sample at:  assets/clean_voice_story_female.wav
```

---

### Pacing & pauses

```python
TTS_PAUSE_BETWEEN_SEGMENTS    = 0.55   # seconds between sentences
TTS_PAUSE_VARY_BY_PUNCTUATION = True   # longer pause after ? ! ...
TTS_PAUSE_BETWEEN_PHRASES     = 0.30   # pause between phrases within a sentence
```

Book-specific breathing room (seconds of silence inserted before/after special chunks):
```python
EBOOK_CHAPTER_PAUSE     = 1.5   # silence BEFORE a chapter card starts speaking
EBOOK_LESSON_PAUSE      = 1.0   # silence BEFORE a key lesson
EBOOK_QUOTE_PAUSE_AFTER = 0.5   # silence AFTER a quote finishes
```

Increase `EBOOK_CHAPTER_PAUSE` if chapter cards feel rushed. Decrease if they drag.

---

### Background visuals

```python
STORY_BG_MODE = "image"   # "gradient" | "image" | "video" | "pixabay"
```

| Mode | What it does |
|------|-------------|
| `"gradient"` | Animated colour gradient per chunk (default when nothing else configured). No external assets needed. |
| `"image"` | Static or cycling photos from `STORY_BG_IMAGE` / `STORY_BG_IMAGES` / `STORY_BG_DIR`. |
| `"video"` | Looping video from `STORY_BG_VIDEO` / `STORY_BG_VIDEOS`. Luma-key compositing for green-screen clips. |
| `"pixabay"` | Auto-downloads relevant photos from Pixabay per chapter. Falls back to cache or gradient if offline. |

**Single image background:**
```python
STORY_BG_MODE  = "image"
STORY_BG_IMAGE = "background/reel_bg.png"   # used for all chunks
```

**Multiple images (one per chapter, cycling):**
```python
STORY_BG_MODE   = "image"
STORY_BG_IMAGES = []        # fill this list, OR point STORY_BG_DIR to a folder
STORY_BG_DIR    = "background"   # all images in this folder are used in order
```

**Image appearance:**
```python
STORY_BG_BLUR = 0     # 0 = sharp  10 = heavy blur (good for busy photos)
STORY_BG_DIM  = 1.0   # 0.0 = fully black  1.0 = full brightness
               # 0.55 is typical for dark-text-on-photo legibility
```

---

### Pixabay integration

```python
STORY_BG_MODE            = "pixabay"     # must be set to "pixabay" to activate
PIXABAY_API_KEY          = "paste_key_here"   # free at pixabay.com/api
PIXABAY_IMAGES_PER_QUERY = 3             # images downloaded per chapter
PIXABAY_CACHE_DIR        = "assets/pixabay_cache"
PIXABAY_ORIENTATION      = "horizontal"  # "vertical" for reels
PIXABAY_SAFE_SEARCH      = True
```

**How to get a free API key:**
1. Go to https://pixabay.com/api/docs/
2. Create a free account
3. Your key is on that page — 500 requests/hour on the free tier, which is plenty

**How it works:**
1. Keywords are extracted per chapter (Hindi → English via a built-in translation map)
2. Images downloaded, resized to exact video dimensions, saved to `PIXABAY_CACHE_DIR`
3. Re-runs skip already-cached images — no re-download
4. If the API is unavailable, any images already in `PIXABAY_CACHE_DIR` are used automatically (see §6)
5. If cache is also empty, falls back to gradient

---

### Typography & colours

```python
# Font sizes
STORY_SUBTITLE_FONT_SIZE = 66   # narration subtitle text
EBOOK_CHAPTER_FONT_SIZE  = 78   # chapter card title
EBOOK_QUOTE_FONT_SIZE    = 60   # quote text
EBOOK_LESSON_FONT_SIZE   = 62   # key lesson text
# (all auto-reduced by ~10% for Hindi/Hinglish since Devanagari glyphs are larger)

# Narration text
STORY_TEXT_COLOR      = (255, 255, 255)   # white — readable on any background
STORY_HIGHLIGHT_COLOR = (255, 215, 0)     # gold — word-by-word highlight colour
STORY_STROKE_COLOR    = (0, 0, 0)         # black stroke around each word
STORY_STROKE_WIDTH    = 5                 # px; increase if text is hard to read on photos

# Chapter card
EBOOK_CHAPTER_BG_COLOR     = (10, 10, 30)    # deep navy — works behind any photo
EBOOK_CHAPTER_TEXT_COLOR   = (255, 255, 255)
EBOOK_CHAPTER_ACCENT_COLOR = (255, 215, 0)   # gold divider & chapter number

# Quote
EBOOK_QUOTE_TEXT_COLOR = (220, 220, 220)
EBOOK_QUOTE_BAR_COLOR  = (255, 215, 0)       # gold left bar
EBOOK_QUOTE_BG_COLOR   = (0, 0, 0)
EBOOK_QUOTE_BG_ALPHA   = 160                 # 0=transparent  255=solid black

# Key Lesson
EBOOK_LESSON_TEXT_COLOR = (255, 240, 100)    # warm yellow
EBOOK_LESSON_BG_COLOR   = (20, 10, 60)       # deep purple
EBOOK_LESSON_BG_ALPHA   = 180

# Progress bar (thin strip at top of every frame)
EBOOK_PROGRESS_BAR_HEIGHT   = 8
EBOOK_PROGRESS_BAR_COLOR    = (255, 215, 0)
EBOOK_PROGRESS_BAR_BG_COLOR = (40, 40, 40)
```

---

### Channel badge & waveform

```python
STORY_CHANNEL_NAME   = "Book Insights"   # shown in top-right corner pill
STORY_LOGO_FONT_SIZE = 28
STORY_LOGO_BG_COLOR  = (0, 0, 0)
STORY_LOGO_TEXT_COLOR = (255, 255, 255)

STORY_WAVEFORM_BARS         = 35         # number of equalizer bars
STORY_WAVEFORM_HEIGHT_RATIO = 0.07       # bar zone height as fraction of video height
STORY_WAVEFORM_COLOR        = (255, 215, 0)   # bar colour (matches gold accent)
STORY_WAVEFORM_BG_ALPHA     = 60         # translucency of the waveform strip background
```

---

### Audio post-processing & background music

```python
AUDIO_POST_PROCESSING = True   # EQ + compression + loudnorm on narration audio
# EQ profile is auto-selected based on LANGUAGE (Hindi/English have different curves)
```

Background music (ducked under narration):
```python
BACKGROUND_MUSIC_ENABLED    = False                         # set True to activate
BACKGROUND_MUSIC_PATH       = "background/cinematic.mp3"   # any mp3/wav/m4a
BACKGROUND_MUSIC_VOLUME_DB  = -24.0    # how loud the music is (negative = quieter)
BACKGROUND_MUSIC_DUCK_RATIO = 20.0     # how hard the music ducks when voice speaks
                                        # higher = music drops more under speech
```

When `BACKGROUND_MUSIC_ENABLED = True`, ffmpeg's `sidechaincompress` filter
automatically lowers the music whenever the narrator is speaking, then brings
it back up in silences — no manual mixing needed.

---

### Encoding

```python
OUTPUT_DIR    = "output/ebook"   # where final .mp4 is saved
TEMP_DIR      = "temp/ebook"     # intermediate files (deleted after run by default)
ASSETS_DIR    = "assets"

VIDEO_CODEC   = "libx264"        # h264 — universally compatible
AUDIO_CODEC   = "aac"
VIDEO_BITRATE = "6000k"          # for 1080p; reduce to "3000k" for smaller files
AUDIO_BITRATE = "192k"
CRF           = 20               # quality (18=nearly lossless, 28=small file)
```

---

## 5. Known Issues & Fixes

### Pink tint on video / image backgrounds

**Symptom:** A pink or magenta colour cast appears over background photos,
especially on lighter areas of the image where the waveform bars are animated.

**Cause:** The waveform overlay step was doing a `rgb24 → screen blend → yuv420p`
round-trip. The `screen` blend mode can produce out-of-gamut chroma values in
the RGB intermediate that become pink/magenta when converted to YUV colour space.

**Fix (already applied in `ebook_mode/video.py`):** The pipeline now stays in
`yuv420p` throughout the blend:

```python
# Before (causes pink tint):
"[0:v]format=rgb24[base];"
"[1:v]format=rgb24[wf];"
"[base][wf]blend=all_mode=screen[v];"
"[v]format=yuv420p[out]"

# After (fixed):
"[0:v]format=yuv420p[base];"
"[1:v]format=yuv420p[wf];"
"[base][wf]blend=all_mode=screen[out]"
```

If you see pink on a different mode (e.g. `story_mode`), look for the same
`rgb24` → `yuv420p` conversion in `story_mode/story_render.py` Step B and
apply the same fix.

---

## 6. Pixabay — Offline / Cache Mode

You do not need an API key to use Pixabay images if you already have images in
the cache directory.

**How the fallback works (now automatic):**

```
STORY_BG_MODE = "pixabay"
PIXABAY_API_KEY = ""       ← key missing or blank
                              ↓
              Check PIXABAY_CACHE_DIR for existing .jpg files
                              ↓
              Found images? → use them as STORY_BG_IMAGES
              No images?    → fall back to "gradient"
```

The same fallback fires if the API key is set but the network is unavailable
(office firewall, offline machine, rate limit hit, etc.).

**Setting up a manual image cache (no API key at all):**

1. Set in `config.py`:
   ```python
   STORY_BG_MODE     = "pixabay"     # activates the cache fallback path
   PIXABAY_API_KEY   = ""            # leave blank
   PIXABAY_CACHE_DIR = "assets/pixabay_cache"
   ```

2. Manually place any JPEG images (already cropped/resized to your video
   dimensions — 1920×1080 for full, 1080×1920 for reel) into
   `assets/pixabay_cache/`. Name them anything; they are loaded in alphabetical
   order.

3. Run the pipeline normally. The runner will detect the missing API key, find
   your files in the cache, and use them — no API call is made.

**How many images do you need?**
- One image per chapter is ideal. The pipeline cycles through all cached images
  in order, so if you have 11 images and 15 chapters, images 1–11 are used for
  chapters 1–11, then it wraps back to image 1 for chapter 12, etc.
- Having fewer images than chapters is fine — they just repeat.

**Downloading images once and reusing:**
If you run with a valid API key once, all downloaded images are saved to
`PIXABAY_CACHE_DIR` and reused on every subsequent run — even if you later
remove the API key or go offline.

---

## 7. Running the Pipeline

**Command line:**
```bash
python main.py --mode ebook --file my_book.txt --title "Rich Dad Poor Dad"
```

**Programmatic:**
```python
from ebook_mode.runner import run
result = run(
    "my_book.txt",
    title="Rich Dad Poor Dad",
    keep_temp=False,   # True to keep intermediate files for debugging
)
print(result["video_path"])
print(result["total_duration"])
```

**Changing settings without editing config.py:**
```python
from ebook_mode import config as cfg
import importlib

cfg.LANGUAGE          = "en"
cfg.EBOOK_VOICE_GENDER = "female"
cfg.STORY_BG_MODE     = "pixabay"
cfg.PIXABAY_API_KEY   = "my_key"

result = run("my_book.txt", cfg=cfg)
```

---

## 8. Output Files

| File | Contents |
|------|----------|
| `output/ebook/<title>_ebook_summary.mp4` | Final video (audio + video, all effects) |
| `output/ebook/<title>.srt` | Subtitle file for YouTube / VLC |
| `output/ebook/<title>_chapters.txt` | YouTube timestamp index — copy-paste into video description |

**Example `_chapters.txt`:**
```
Rich Dad Poor Dad by Robert Kiyosaki

Timestamps:
00:00  Chapter 1: Rich Dad, Poor Dad
03:22  Chapter 2: The Rich Don't Work for Money
07:11  Chapter 3: Why Teach Financial Literacy?
```

---

## 9. Quick Cheat Sheet

| I want to… | Change this |
|------------|-------------|
| Switch language to Hindi | `LANGUAGE = "hi"` |
| Use a female voice | `EBOOK_VOICE_GENDER = "female"` |
| Make the narration slower | `KOKORO_SPEED = 0.80` |
| Use my own background photo | `STORY_BG_MODE = "image"` + `STORY_BG_IMAGE = "background/my_photo.jpg"` |
| Use multiple photos (one per chapter) | `STORY_BG_MODE = "image"` + add photos to `STORY_BG_DIR = "background"` |
| Auto-download relevant photos | `STORY_BG_MODE = "pixabay"` + `PIXABAY_API_KEY = "..."` |
| Use cached photos offline | `STORY_BG_MODE = "pixabay"` + `PIXABAY_API_KEY = ""` + put JPEGs in `assets/pixabay_cache/` |
| Add background music | `BACKGROUND_MUSIC_ENABLED = True` + `BACKGROUND_MUSIC_PATH = "background/music.mp3"` |
| Make video vertical (Reels) | `OUTPUT_MODE = "reel"` + `PIXABAY_ORIENTATION = "vertical"` |
| Reduce file size | `VIDEO_BITRATE = "3000k"` + `CRF = 24` |
| Fix pink tint on photos | Already fixed in `video.py`. If it appears elsewhere, see §5. |
| Longer pause between chapters | `EBOOK_CHAPTER_PAUSE = 2.5` |
| Change channel name on badge | `STORY_CHANNEL_NAME = "My Channel"` |
| Add phonetic override for a word | `EXTRA_PHONETIC_DICT = {"API": "ए पी आई"}` |
