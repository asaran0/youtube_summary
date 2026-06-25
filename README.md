# Hindi/English/Hinglish Video Generator — Story & Q&A modes

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

python -m  main.py --mode qa --file assets/sample_interview_qa.txt --title "जावा इंटरव्यू"

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
