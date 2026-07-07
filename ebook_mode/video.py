"""
ebook_mode/video.py — compile_ebook_video()

Extends the story_mode pipeline to handle chunk_type-aware rendering:

    narration   → story_render._render_sentence_frame  (word-by-word highlight)
    chapter_card→ ebook_mode.render.render_chapter_card (full-screen title card)
    quote       → ebook_mode.render.render_quote_frame  (gold left-bar callout)
    lesson      → ebook_mode.render.render_lesson_frame (warm-yellow panel)

Progress bar is drawn onto every frame via render.draw_progress_bar().
Waveform, audio, background music ducking — all reuse story_render's Steps
B and C unchanged.
"""

import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from utils import get_logger
from ebook_mode import render as ebook_render
from story_mode.story_render import (
    _load_font,
    _prepare_image_bg,
    _gradient_bg,
    _resolve_bg_assets,
    _waveform_loop_path,
    _render_sentence_frame,
    _draw_badge,
    _line_h,
    _text_w,
    _ease_in,
    _ease_out,
    PALETTES,
)

log = get_logger("ebook.video")


def compile_ebook_video(
    chunks: list[dict],
    audio_path: str,
    output_path: str,
    video_width: int,
    video_height: int,
    font_path: str,
    cfg,
    book_title: str = "",
) -> None:
    """
    Build the full ebook summary video.

    Steps:
      A — Render per-frame video (MoviePy VideoClip), chunk-type aware
      B — Overlay waveform animation (ffmpeg screen-blend)
      C — Mux audio (with optional background music ducking)
    """
    from moviepy.editor import AudioFileClip, VideoClip

    lang        = getattr(cfg, "LANGUAGE", "en")
    fade_dur    = float(getattr(cfg, "STORY_SENTENCE_FADE", 0.20))
    sub_size    = int(getattr(cfg, "STORY_SUBTITLE_FONT_SIZE", 72))
    text_color  = tuple(getattr(cfg, "STORY_TEXT_COLOR",      (255, 255, 255)))
    hi_color    = tuple(getattr(cfg, "STORY_HIGHLIGHT_COLOR", (255, 215, 0)))
    stroke_col  = tuple(getattr(cfg, "STORY_STROKE_COLOR",    (0, 0, 0)))
    stroke_w    = int(getattr(cfg,   "STORY_STROKE_WIDTH",    5))
    channel     = getattr(cfg, "STORY_CHANNEL_NAME", "")
    n_bars      = int(getattr(cfg, "STORY_WAVEFORM_BARS", 35))
    bar_ratio   = float(getattr(cfg, "STORY_WAVEFORM_HEIGHT_RATIO", 0.07))
    center_y    = int(video_height * 0.46)
    max_text_w  = int(video_width * 0.84)

    font        = _load_font(sub_size, lang, font_path)

    # Background setup
    bg_mode         = getattr(cfg, "STORY_BG_MODE", "gradient").lower()
    bg_blur         = int(getattr(cfg,   "STORY_BG_BLUR", 0))
    bg_dim          = float(getattr(cfg, "STORY_BG_DIM",  0.55))
    bg_image_assets = _resolve_bg_assets(cfg, "image")
    bg_video_assets = _resolve_bg_assets(cfg, "video")

    if bg_mode == "image" and not bg_image_assets:
        log.warning("STORY_BG_MODE=image but no images found; falling back to gradient.")
        bg_mode = "gradient"
    if bg_mode == "video" and not bg_video_assets:
        log.warning("STORY_BG_MODE=video but no videos found; falling back to gradient.")
        bg_mode = "gradient"

    # Image/video bg → no palette colour cycling on text
    use_palette_accents = (bg_mode == "gradient")

    single_image_bg = None
    if bg_mode == "image" and len(bg_image_assets) == 1:
        single_image_bg = _prepare_image_bg(
            bg_image_assets[0], video_width, video_height, bg_blur, bg_dim
        )

    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    # ── Build render-ready chunk list ────────────────────────────────────
    render_chunks = []
    for idx, chunk in enumerate(chunks):
        text       = chunk.get("text",         "").strip()
        disp_text  = chunk.get("display_text", text).strip()
        t_start    = float(chunk.get("new_start", chunk.get("start", 0.0)))
        t_end      = float(chunk.get("new_end",   chunk.get("end",   t_start + 1.0)))
        chunk_type = chunk.get("chunk_type", "narration")
        chap_num   = int(chunk.get("chapter_num",    0))
        total_chap = int(chunk.get("total_chapters", 1))

        if t_end - t_start < 0.05 or not text:
            continue

        palette      = PALETTES[idx % len(PALETTES)]
        chunk_accent = palette[2] if use_palette_accents else hi_color

        # Background frame for this chunk
        if bg_mode == "image":
            if single_image_bg is not None:
                bg = single_image_bg.copy()
            else:
                img_idx  = idx % max(len(bg_image_assets), 1)
                bg       = _prepare_image_bg(
                    bg_image_assets[img_idx], video_width, video_height, bg_blur, bg_dim
                )
        else:
            bg = _gradient_bg(video_width, video_height, palette[0], palette[1])

        words = disp_text.split()

        # Wrap cache for narration/quote word-by-word reveal
        wrap_cache = {0: [""]}
        cur_lines, cur_line = [], ""
        for n, w in enumerate(words, start=1):
            trial = (cur_line + " " + w).strip()
            if cur_line and _text_w(dummy_draw, trial, font) > max_text_w:
                cur_lines.append(cur_line)
                cur_line = w
            else:
                cur_line = trial
            wrap_cache[n] = cur_lines + [cur_line]

        render_chunks.append({
            "t_start":      t_start,
            "t_end":        t_end,
            "bg":           bg,
            "words":        words,
            "n_words":      len(words),
            "accent":       chunk_accent,
            "wrap_cache":   wrap_cache,
            "chunk_type":   chunk_type,
            "display_text": disp_text,
            "chapter_num":  chap_num,
            "total_chapters": total_chap,
        })

    if not render_chunks:
        raise RuntimeError("No ebook chunks to render")

    # ── Waveform loop ────────────────────────────────────────────────────
    accent_for_wf = render_chunks[0]["accent"]
    wf_loop = _waveform_loop_path(
        accent_for_wf, video_width, video_height, n_bars, bar_ratio, cfg
    )

    # ── make_frame ────────────────────────────────────────────────────────
    def make_frame(t: float) -> np.ndarray:
        # Find active chunk
        chunk = None
        for c in render_chunks:
            if c["t_start"] <= t < c["t_end"]:
                chunk = c
                break
        if chunk is None:
            chunk = render_chunks[-1]

        dur     = max(chunk["t_end"] - chunk["t_start"], 0.001)
        elapsed = t - chunk["t_start"]

        # Fade alpha
        if elapsed < fade_dur:
            alpha = _ease_out(elapsed / fade_dur)
        elif elapsed > dur - fade_dur:
            alpha = _ease_in((chunk["t_end"] - t) / fade_dur)
        else:
            alpha = 1.0
        alpha = max(0.0, min(1.0, alpha))

        ctype      = chunk["chunk_type"]
        chap_num   = chunk["chapter_num"]
        total_chap = chunk["total_chapters"]

        # ── Chapter card ─────────────────────────────────────────────────
        if ctype == "chapter_card":
            img = ebook_render.render_chapter_card(
                bg=chunk["bg"],
                chapter_num=chap_num,
                chapter_title=chunk["display_text"],
                total_chapters=total_chap,
                fade_alpha=alpha,
                font_path=font_path,
                cfg=cfg,
            )
            return np.array(img)

        # ── Key Lesson ────────────────────────────────────────────────────
        if ctype == "lesson":
            img = ebook_render.render_lesson_frame(
                bg=chunk["bg"],
                lesson_text=chunk["display_text"],
                chapter_num=chap_num,
                total_chapters=total_chap,
                fade_alpha=alpha,
                font_path=font_path,
                cfg=cfg,
            )
            return np.array(img)

        # ── Quote callout ─────────────────────────────────────────────────
        if ctype == "quote":
            n_words   = chunk["n_words"]
            progress  = elapsed / dur
            active_w  = -1
            if n_words > 0:
                words   = chunk["words"]
                lengths = [max(1, len(w)) for w in words]
                total   = sum(lengths)
                target  = progress * total
                cumul   = 0
                for wi, ln in enumerate(lengths):
                    if cumul + ln >= target:
                        active_w = wi
                        break
                    cumul += ln
                active_w = min(active_w, n_words - 1)

            img = ebook_render.render_quote_frame(
                bg=chunk["bg"],
                quote_text=chunk["display_text"],
                chapter_num=chap_num,
                total_chapters=total_chap,
                active_word=active_w,
                fade_alpha=alpha,
                font_path=font_path,
                cfg=cfg,
            )
            return np.array(img)

        # ── Narration (default) ───────────────────────────────────────────
        progress  = elapsed / dur
        n_words   = chunk["n_words"]
        pop_progress = 1.0
        active_w  = -1

        if n_words > 0:
            words   = chunk["words"]
            lengths = [max(1, len(w)) for w in words]
            total   = sum(lengths)
            target  = progress * total
            cumul   = 0
            for wi, ln in enumerate(lengths):
                if cumul + ln >= target:
                    active_w = wi
                    # Pop animation progress
                    word_frac  = lengths[wi] / total
                    word_dur_s = word_frac * dur
                    into_word  = max(0.0, (target - cumul) / max(lengths[wi], 1)) * word_dur_s
                    pop_dur    = min(0.16, max(word_dur_s * 0.6, 0.04))
                    pop_progress = max(0.0, min(1.0, into_word / pop_dur))
                    break
                cumul += ln
            if active_w < 0:
                active_w = n_words - 1

        visible_n = max(active_w + 1, 0)
        lines = chunk["wrap_cache"].get(visible_n, chunk["wrap_cache"][n_words])

        img = _render_sentence_frame(
            chunk["bg"], lines, font, active_w,
            text_color, chunk["accent"], stroke_col, stroke_w,
            center_y, fade_alpha=alpha, pop_progress=pop_progress,
        )

        # Progress bar on narration frames too
        ebook_render.draw_progress_bar(img, chap_num, total_chap, cfg)

        if channel:
            _draw_badge(img, channel, font_path, cfg, chunk["accent"])

        return np.array(img)

    # ── Step A: render subtitle/card video ───────────────────────────────
    audio_clip = AudioFileClip(audio_path)
    total_dur  = min(render_chunks[-1]["t_end"], audio_clip.duration)
    audio_clip.close()

    tmp_nowave = output_path.replace(".mp4", "_nowave.mp4")
    video_clip = VideoClip(make_frame, duration=total_dur)
    video_clip.write_videofile(
        tmp_nowave,
        fps=cfg.OUTPUT_FPS,
        codec=cfg.VIDEO_CODEC,
        bitrate=cfg.VIDEO_BITRATE,
        audio=False,
        logger="bar",
    )
    video_clip.close()
    log.info("Ebook frame render done → %s", tmp_nowave)

    # ── Step B: waveform overlay ──────────────────────────────────────────
    tmp_waved = output_path.replace(".mp4", "_waved.mp4")
    wf_cmd = [
        "ffmpeg", "-y",
        "-i", tmp_nowave,
        "-stream_loop", "-1",
        "-i", wf_loop,
        "-filter_complex",
        "[0:v]format=yuv420p[base];"
        "[1:v]format=yuv420p[wf];"
        "[base][wf]blend=all_mode=screen[out]",
        "-map", "[out]",
        "-c:v", cfg.VIDEO_CODEC,
        "-preset", "fast", "-crf", "18",
        "-t", str(total_dur),
        tmp_waved,
    ]
    r = subprocess.run(wf_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log.warning("Waveform overlay failed, continuing without: %s", r.stderr[-300:])
        tmp_waved = tmp_nowave

    # ── Step C: mux audio (+ optional ducked background music) ───────────
    bg_music     = getattr(cfg, "BACKGROUND_MUSIC_PATH", None)
    music_enabled = bool(getattr(cfg, "BACKGROUND_MUSIC_ENABLED", False))
    music_vol_db  = float(getattr(cfg, "BACKGROUND_MUSIC_VOLUME_DB", -24.0))
    duck_ratio    = float(getattr(cfg, "BACKGROUND_MUSIC_DUCK_RATIO", 20.0))

    muxed = False
    if music_enabled and bg_music and os.path.exists(bg_music):
        log.info("Mixing background music: %s", bg_music)
        audio_filter = (
            f"[2:a]volume={music_vol_db}dB,aloop=loop=-1:size=2e9,atrim=0:{total_dur}[music];"
            f"[1:a]asplit=2[narr1][narr2];"
            f"[music][narr1]sidechaincompress=threshold=0.02:ratio={duck_ratio}:"
            f"attack=5:release=400[ducked];"
            f"[narr2][ducked]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        mux_cmd = [
            "ffmpeg", "-y",
            "-i", tmp_waved,
            "-i", audio_path,
            "-i", bg_music,
            "-filter_complex", audio_filter,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", cfg.AUDIO_CODEC, "-b:a", cfg.AUDIO_BITRATE,
            "-shortest", output_path,
        ]
        r = subprocess.run(mux_cmd, capture_output=True, text=True)
        if r.returncode == 0:
            muxed = True
        else:
            log.warning("Music mux failed, falling back to voice-only: %s", r.stderr[-400:])

    if not muxed:
        subprocess.run([
            "ffmpeg", "-y",
            "-i", tmp_waved,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", cfg.AUDIO_CODEC, "-b:a", cfg.AUDIO_BITRATE,
            "-shortest", output_path,
        ], check=True, capture_output=True)

    # Cleanup
    for tmp in [tmp_nowave, tmp_waved]:
        if tmp != output_path and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

    log.info("Ebook video → %s", output_path)
