# 🎬 Hindi YouTube Video Summarizer

A fully **offline** Python tool that downloads a Hindi YouTube video and produces:

| Output File | Description |
|---|---|
| `output/<title>_summary.mp4` | Summary video (≈75 % of original) with burned-in subtitles and animated topic banners |
| `output/<title>.srt` | Standard subtitle file (upload to YouTube or use in any media player) |
| `output/<title>_metadata.txt` | Ready-to-paste YouTube title, description, tags, and chapter timestamps |

---

## Quick Start

```bash
# 1. One-time setup (install everything)
bash setup.sh

# 2. Run on any Hindi YouTube video
python main.py https://www.youtube.com/watch?v=ur5LMCbyuEY
```

That's it. All AI processing runs locally — no API keys, no subscriptions.

---

## Requirements

| Requirement | Version | Notes |
|---|---|---|
| macOS (Apple Silicon) | M1 / M2 / M3 | Uses Metal GPU via MPS for faster Whisper |
| Python | ≥ 3.11 | `python --version` to check |
| Homebrew | any | https://brew.sh |
| ffmpeg | any | installed automatically by `setup.sh` |
| Disk space | ≥ 5 GB | for models + temporary video files |

---

## Project Structure

```
youtube_summarizer/
│
├── main.py              ← Entry point. CLI + pipeline orchestration.
├── config.py            ← ALL settings in one place. Edit here to customize.
│
├── downloader.py        ← Downloads video + extracts 16 kHz WAV audio.
├── transcriber.py       ← Runs Whisper to get timestamped Hindi transcript.
├── summarizer.py        ← Scores segments, selects the important 75%.
│
├── banner_maker.py      ← Creates animated topic-banner overlays (PIL).
├── subtitle_handler.py  ← Generates .srt + styled .ass, burns into video.
├── video_editor.py      ← Cuts clips, concatenates, resizes, composites.
├── metadata_writer.py   ← Extracts keywords, writes metadata.txt.
│
├── utils.py             ← Shared helpers (logging, font detection, time).
│
├── setup.sh             ← One-time installer (ffmpeg + Python packages + font).
├── requirements.txt     ← Python package list.
├── assets/              ← Fonts (downloaded by setup.sh).
├── temp/                ← Temporary files (auto-deleted after run).
└── output/              ← Final output files land here.
```

---

## How It Works (Pipeline)

```
YouTube URL
     │
     ▼
┌─────────────┐
│  STEP 1     │  yt-dlp downloads best quality MP4 (≤ 1080p)
│  Download   │  ffmpeg extracts 16 kHz mono WAV for Whisper
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  STEP 2     │  OpenAI Whisper (medium model, runs on M1 Metal GPU)
│  Transcribe │  Output: list of {start, end, text, confidence} segments
└──────┬──────┘
       │  📌 Transcript cached to temp/transcript.json
       │     (re-running the script skips this slow step)
       ▼
┌─────────────┐
│  STEP 3     │  Group segments → score by 4 criteria → greedy selection
│  Summarize  │  Always keeps intro + outro; selects best body chunks
└──────┬──────┘   until TARGET_RATIO is filled
       │
       ▼
┌─────────────┐
│  STEP 4     │  Writes output/<title>.srt (standard subtitles)
│  Subtitles  │  Writes temp/subtitles.ass (styled, for burning into video)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  STEP 5     │  ffmpeg cuts each selected chunk (stream-copy = fast)
│  Video Edit │  ffmpeg concatenates + re-encodes to uniform stream
└──────┬──────┘  moviepy composites topic-banner overlays
       │         ffmpeg burns ASS subtitles into final MP4
       ▼
┌─────────────┐
│  STEP 6     │  TF-IDF keyword extraction from transcript
│  Metadata   │  Writes title / description / tags / chapters to .txt
└─────────────┘
```

---

## Segment Scoring Algorithm

Each "chunk" (group of consecutive Whisper segments) gets a 0–1 importance score:

| Component | Weight | What it measures |
|---|---|---|
| Word frequency (TF-IDF) | 40 % | Information density — chunks with rare/important words score higher |
| Whisper confidence | 25 % | Model certainty — confident speech is kept; mumbling/music is dropped |
| Position bonus | 15 % | Intro and outro naturally score higher (context + conclusion) |
| Sentence completeness | 20 % | Chunks ending with `।` or `.` preferred over mid-sentence cuts |

Weights are in `config.py` — change them to shift the summarizer's behaviour.

---

## Configuration Guide (`config.py`)

Every project setting lives in `config.py`. The most useful ones:

### Change summary length
```python
TARGET_RATIO = 0.75   # 75 % of original
# Change to 0.50 for a shorter summary, 0.90 for near-complete
```

### Use a better (slower) Whisper model
```python
WHISPER_MODEL = "large-v3"   # best quality, ~3 GB RAM, 3× slower
# "medium" is the default — good quality, faster on M1
```

### Subtitle appearance
```python
SUBTITLE_FONT_SIZE = 34        # increase for larger subtitles
SUBTITLE_BG_ALPHA  = 170       # 0 = transparent, 255 = black box
SUBTITLE_MARGIN_Y  = 60        # distance from bottom in pixels
```

### Banner appearance
```python
BANNER_ENABLED     = True
BANNER_FONT_SIZE   = 48
BANNER_BG_COLOR    = (15, 20, 60)      # dark navy background
BANNER_TEXT_COLOR  = (255, 220, 50)    # golden yellow text
BANNER_HOLD_SECONDS= 3.0               # seconds to show banner
```

### Output quality vs file size
```python
CRF           = 23    # lower = higher quality + larger file (18–28 range)
VIDEO_BITRATE = "4000k"
AUDIO_BITRATE = "192k"
```

---

## Command-Line Options

```
python main.py <url> [options]

Positional:
  url              YouTube video URL

Options:
  --ratio FLOAT    Summary length ratio (default: 0.75)
  --model NAME     Whisper model: tiny / base / small / medium / large-v3
  --no-banners     Disable animated topic banners
  --keep-temp      Keep temp/ files after run (useful for debugging)
  --output-dir DIR Where to save output files (default: output/)
  --verbose        Show debug-level logs
```

**Examples:**

```bash
# Standard run
python main.py https://youtu.be/abc123

# Shorter summary (60%) with best Whisper model
python main.py https://youtu.be/abc123 --ratio 0.60 --model large-v3

# Quick test run with tiny model, keep temp files for inspection
python main.py https://youtu.be/abc123 --model tiny --keep-temp
```

---

## Output Files

After a successful run, the `output/` folder contains:

```
output/
├── Video_Title_summary.mp4       ← Final summary video
├── Video_Title.srt               ← Subtitle file (upload to YouTube)
└── Video_Title_metadata.txt      ← Title, description, tags, chapters
```

### How to upload to YouTube
1. Upload `_summary.mp4` as the video
2. Open `_metadata.txt` — copy the **TITLE**, **DESCRIPTION**, **TAGS**
3. Upload `_summary.srt` via YouTube Studio → Subtitles
4. The description already contains chapter timestamps — paste them in and YouTube will auto-create chapters

---

## Troubleshooting

### "No Hindi font found"
```bash
# Re-run setup to download the font
bash setup.sh
# Or manually copy any Devanagari .ttf:
cp /path/to/font.ttf assets/NotoSansDevanagari-Regular.ttf
```

### Subtitles not visible
- Increase `SUBTITLE_FONT_SIZE` in `config.py`
- Decrease `SUBTITLE_BG_ALPHA` to make the background darker (closer to 255)

### Out of memory with large-v3
- Switch to `medium` model: `python main.py <url> --model medium`

### Transcription is slow
- Whisper uses Apple Metal GPU automatically on M1
- If it seems slow, confirm with `--verbose` that it says "Using Apple MPS"

### Video already downloaded but pipeline re-runs download
- The script checks for `temp/video.mp4` and `temp/audio.wav`
- Use `--keep-temp` on first run, subsequent runs will reuse them

### Subtitles are out of sync
- This can happen if ffmpeg stream-copy produces clips with timestamp drift
- In `video_editor.py`, change `-c copy` to re-encode:
  ```python
  "-c:v", "libx264", "-c:a", "aac"   # instead of "-c", "copy"
  ```

---

## How to Extend / Modify

### Add a new scoring criterion
Edit `summarizer.py` → `_score_chunk()`:
```python
# Add a new component
keyword_bonus = 0.5 if "important_hindi_word" in chunk["text"] else 0.0
# Add to weighted sum
score += 0.10 * keyword_bonus   # adjust weight as needed
```
Remember to also add the new weight to `config.py` and reduce other weights so they still sum to 1.0.

### Change subtitle position to top of screen
In `config.py`:
```python
SUBTITLE_MARGIN_Y = 60   # this positions from bottom by default
```
In `subtitle_handler.py` → `_write_ass()`, change `Alignment` in the ASS style line:
- `2` = bottom centre (current)
- `8` = top centre

### Add intro/outro title card
In `video_editor.py`, before `_ffmpeg_concat()`, create a title card MP4 using ffmpeg's `lavfi` source:
```bash
ffmpeg -f lavfi -i color=c=black:size=1920x1080:duration=3 \
       -vf "drawtext=text='My Title':fontcolor=white:fontsize=72:x=(w-tw)/2:y=(h-th)/2" \
       temp/title_card.mp4
```
Then prepend it to `clip_paths`.

---

## Models Used

| Task | Model | Runs locally? | Paid? |
|---|---|---|---|
| Audio transcription | OpenAI Whisper `medium` | ✅ Yes | ✅ Free |
| Segment scoring | TF-IDF (pure Python) | ✅ Yes | ✅ Free |
| Video editing | ffmpeg + moviepy | ✅ Yes | ✅ Free |
| Subtitle rendering | libass (via ffmpeg) | ✅ Yes | ✅ Free |

**Everything runs 100 % locally. No internet connection needed after setup.**

---

## License
MIT — free to use, modify, and distribute.
