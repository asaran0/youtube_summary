# Hindi/English/Hinglish Video Generator — Story & Q&A modes
uvicorn api.main:app --reload --port 8000
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/redoc
## Structure

```
core/                   shared, mode-agnostic infrastructure
  tts/                  TTS strategy pattern
    base.py             abstract TTSStrategy interface
    xtts_strategy.py    Coqui XTTS-v2 (voice cloning, best realism)
    mms_strategy.py     Meta MMS-TTS (neural, no cloning)
    macos_strategy.py   macOS built-in 'say' (zero setup)
    factory.py          strategy registry — add a new backend here
    pipeline.py         generate_tts_audio() entry point, caching, retiming
    audio_utils.py       resample / polish / concat helpers
  lang/                 hi / en / hig language handling
    dictionary.py       English -> Hindi phonetic word list
    transliterate.py    clean_text() — applies dictionary per LANGUAGE
    tokenize.py         shared tokenizer + stopwords (used by summarizer)
  render/               subtitle / slideshow / banner / metadata rendering
    subtitles.py        generate_subtitle_files(), burn_subtitles()
    slideshow.py        compile_slideshow_video()
    banners.py          topic banner overlays (story mode)
    metadata.py         YouTube title/description/tags generator

story_mode/             everything specific to story mode
  config.py             story mode's own settings (TTS backend, ratio, etc.)
  loader.py             load_text_file() — plain text -> segments
  summarizer.py         scoring + selection (the only mode that shortens)
  narration.py          storytelling intro/transition phrases
  styles.py             trivial style resolver (no special styling)
  runner.py             run() — the full story pipeline

qa_mode/                everything specific to Q&A / interview-prep mode
  config.py             qa mode's own settings (TTS backend, styling, etc.)
  loader.py             load_qa_file() — Q&A pairs -> question/think/countdown/answer chunks
  styles.py             question/answer/countdown/try_yourself style resolver
  runner.py             run() — the full qa pipeline (no summarizer — always keeps everything)

main.py                 CLI entry point: --mode story|qa
utils.py                shared logging/font/directory helpers
requirements.txt
```

## Why this structure

Each mode has its own config, loader, and styling — tuning Q&A's
subtitle sizes or pacing can never accidentally affect story mode, and
vice versa. The only code shared between them is genuine
infrastructure: TTS engines, the language/transliteration pipeline,
and the rendering primitives (drawing text, building slideshows).

`core/render/` knows nothing about "question" or "answer" — each mode
supplies its own `style_resolver` callback. This is what lets a future
third mode be added by writing a new `xyz_mode/` package, without
touching `core/` at all.

## Usage

```bash
# Story mode
python main.py --mode story --file assets/sample_story.txt --title "नेपोलियन हिल"

# Q&A / interview-prep mode
python main.py --mode qa --file assets/sample_interview_qa.txt --title "जावा इंटरव्यू"

# Override settings per-run without editing config files
python main.py --mode story --file story.txt --output-mode reel --language hig
python main.py --mode qa --file qa.txt --tts-backend xtts --voice-sample my_voice.wav
```

## Language modes

Set `LANGUAGE` in either mode's `config.py`, or pass `--language` on the CLI:

- `hi`  — pure Hindi. English loanwords/acronyms (brand names, technical
  terms) are still transliterated to Hindi phonetics.
- `en`  — pure English. No transliteration applied.
- `hig` — Hinglish, genuinely mixed Hindi/English sentences. Same
  transliteration behavior as `hi`.

## Adding a new TTS backend

1. Create `core/tts/your_strategy.py`, subclass `TTSStrategy` from `base.py`
2. Implement `synthesize()` (and optionally `check_available()`)
3. Register it in `core/tts/factory.py`'s `_STRATEGIES` dict

Either mode can then use it by setting `TTS_BACKEND = "your_new_name"`
in its own `config.py` — nothing else needs to change.

## Adding a new mode

1. Create `your_mode/` with `config.py`, `loader.py`, `styles.py`, `runner.py`
2. Your `loader.py` turns input into chunk dicts (text, optional
   `display_text`, optional `style` tag, optional `is_silent`)
3. Your `styles.py` defines a `resolve_style(style, cfg)` function
4. Your `runner.py` calls into `core/tts/pipeline.py` and `core/render/*`
   the same way `story_mode/runner.py` / `qa_mode/runner.py` do
5. Wire it into `main.py`'s `--mode` choices

`core/` never needs to change for this.

## Per-mode independence

Both `story_mode/config.py` and `qa_mode/config.py` independently set:
- `TTS_BACKEND` (xtts / mms / macos)
- `OUTPUT_MODE` (reel / full)
- `LANGUAGE` (hi / en / hig)
- All subtitle/banner/audio styling and pacing

Changing one mode's settings can never silently affect the other.



Two ways, matching the two batch endpoints.

**1. Batch via JSON (`qa_pairs` inline)**

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/qa-videos/batch' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "java_interview",
    "questions_per_part": 5,
    "language": "en",
    "output_mode": "reel",
    "tts_backend": "xtts",
    "voice_sample": "assets/clean_voice.wav",
    "qa_pairs": [
      {"question": "What is JVM?", "answer": "JVM is the engine that runs Java bytecode."},
      {"question": "What is JDK?", "answer": "JDK is the full development kit including JRE plus compiler and debugger."},
      {"question": "What is JRE?", "answer": "JRE is the runtime environment needed to run Java applications."},
      {"question": "What is garbage collection?", "answer": "It is automatic memory management that reclaims unused objects."},
      {"question": "What is a class loader?", "answer": "It is the JVM component that loads class files at runtime."},
      {"question": "What is multithreading?", "answer": "It is running multiple threads concurrently within a program."}
    ]
  }'
```

With `questions_per_part: 5` and 6 questions, that creates **2 jobs**: `java_interview_part1` (first 5) and `java_interview_part2` (last 1).

Response gives you the `batch_id` plus each part's `job_id`.

**2. Batch via file upload** (this is the "give a file name" path you originally asked for)

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/qa-videos/batch/upload' \
  -F 'file=@assets/sample_interview_qa.txt' \
  -F 'name=java_interview' \
  -F 'questions_per_part=5' \
  -F 'language=en' \
  -F 'output_mode=reel' \
  -F 'tts_backend=xtts' \
  -F 'voice_sample=assets/clean_voice.wav'
```

`file` must contain plain `Q: ...` / `A: ...` text, same format as your existing `--file` CLI input.

**3. Check batch status**

```bash
curl 'http://127.0.0.1:8000/api/v1/qa-videos/batch/<batch_id>'
```

Returns each part's individual status (`queued`/`running`/`done`/`failed`) plus an `overall_status`. Once a part is `done`, grab its `job_id` from this response and download with the regular single-video endpoints:

```bash
curl -OJ 'http://127.0.0.1:8000/api/v1/qa-videos/<job_id>/video'
```

As before, both are also doable through `/docs` if you'd rather avoid escaping text by hand — the file-upload one especially is much easier there since it gives you an actual file picker.