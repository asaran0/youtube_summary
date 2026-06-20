"""
core/render/slideshow.py — Build a video from image slides plus generated TTS.

Mode-agnostic: works identically for story_mode and qa_mode. Each mode
passes its own cfg (background paths, video codec settings, output
dimensions) — this module has no mode-specific knowledge.
"""

import os
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from utils import ensure_dirs, get_logger

log = get_logger("slideshow")


def compile_slideshow_video(
    selected_chunks: list[dict],
    audio_path: str,
    output_path: str,
    video_width: int,
    video_height: int,
    font_path: str,
    cfg,
    title: str = "",
    topic_groups: list[tuple] | None = None,
) -> None:
    """
    Render image slides and mux them with the generated narration.

    If topic_groups is provided and cfg.BANNER_ENABLED is True, topic
    banners are composited on top of the assembled slideshow as a
    second pass (banners use moviepy's CompositeVideoClip, while the
    base slideshow itself is pure ffmpeg for speed).
    """
    ensure_dirs(cfg.TEMP_DIR, cfg.OUTPUT_DIR)

    slide_dir = os.path.join(cfg.TEMP_DIR, "slides")
    ensure_dirs(slide_dir)

    backgrounds = _load_backgrounds(video_width, video_height, cfg)
    slide_paths = []

    for index, chunk in enumerate(selected_chunks):
        duration = chunk.get("new_end", 0) - chunk.get("new_start", 0)
        if duration < 0.2:
            continue
        bg = backgrounds[index % len(backgrounds)].copy()
        slide = _render_slide(bg)
        path = os.path.abspath(os.path.join(slide_dir, f"slide_{index:04d}.jpg"))
        slide.save(path, "JPEG", quality=92, optimize=True)
        slide_paths.append((path, max(duration, 0.2)))

    if not slide_paths:
        raise RuntimeError("No slideshow slides were generated")

    list_file = os.path.join(cfg.TEMP_DIR, "slideshow_concat.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for path, duration in slide_paths:
            safe_path = path.replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")
            f.write(f"duration {duration:.3f}\n")
        safe_last = slide_paths[-1][0].replace("'", "'\\''")
        f.write(f"file '{safe_last}'\n")

    needs_banners = bool(topic_groups) and getattr(cfg, "BANNER_ENABLED", False)
    base_output = (
        os.path.join(cfg.TEMP_DIR, "slideshow_base.mp4") if needs_banners else output_path
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", os.path.abspath(list_file),
        "-i", os.path.abspath(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-vf", f"fps={cfg.OUTPUT_FPS},format=yuv420p",
        "-c:v", cfg.VIDEO_CODEC,
        "-crf", str(cfg.CRF),
        "-preset", "veryfast",
        "-c:a", cfg.AUDIO_CODEC,
        "-b:a", cfg.AUDIO_BITRATE,
        "-shortest",
        os.path.abspath(base_output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("ffmpeg slideshow failed:\n%s", result.stderr[-3000:])
        raise RuntimeError("ffmpeg slideshow step failed")

    if needs_banners:
        _composite_banners(base_output, output_path, topic_groups, video_width, video_height, font_path, cfg)

    log.info("Slideshow video complete -> %s", output_path)


def _composite_banners(
    base_video_path: str,
    output_path: str,
    topic_groups: list[tuple],
    video_width: int,
    video_height: int,
    font_path: str,
    cfg,
) -> None:
    """Overlay topic banners on top of the assembled slideshow video."""
    from moviepy import VideoFileClip, CompositeVideoClip
    from core.render.banners import make_banner_clips

    try:
        banner_clips = make_banner_clips(topic_groups, video_width, video_height, font_path, cfg)
    except Exception as exc:
        log.warning("Banner generation failed (%s) — continuing without banners.", exc)
        banner_clips = []

    if not banner_clips:
        # Nothing to composite — just copy the base video through.
        import shutil
        shutil.copyfile(base_video_path, output_path)
        return

    base_clip = VideoFileClip(base_video_path)
    try:
        final = CompositeVideoClip([base_clip, *banner_clips], size=(video_width, video_height))
        final.write_videofile(
            output_path,
            codec=cfg.VIDEO_CODEC,
            audio_codec=cfg.AUDIO_CODEC,
            bitrate=cfg.VIDEO_BITRATE,
            audio_bitrate=cfg.AUDIO_BITRATE,
            fps=cfg.OUTPUT_FPS,
            logger=None,
        )
    except Exception as exc:
        log.warning("Banner compositing failed (%s) — falling back to video without banners.", exc)
        import shutil
        shutil.copyfile(base_video_path, output_path)
    finally:
        base_clip.close()


def _load_backgrounds(width: int, height: int, cfg) -> list[Image.Image]:
    paths = _configured_background_paths(cfg)
    images = []
    for path in paths:
        try:
            images.append(_fit_image(Image.open(path).convert("RGB"), width, height))
        except Exception as exc:
            log.warning("Skipping background %s: %s", path, exc)

    if images:
        log.info("Using %d configured background images", len(images))
        return images

    log.info("No background images found; generating original slide backgrounds")
    return [_generate_background(width, height, seed) for seed in range(6)]


def _configured_background_paths(cfg) -> list[str]:
    paths = [p for p in cfg.BACKGROUND_IMAGE_PATHS if os.path.exists(p)]
    bg_dir = Path(cfg.BACKGROUND_DIR)
    if bg_dir.exists():
        for path in bg_dir.iterdir():
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                paths.append(str(path))
    return paths


def _fit_image(img: Image.Image, width: int, height: int) -> Image.Image:
    scale = max(width / img.width, height / img.height)
    new_size = (int(img.width * scale), int(img.height * scale))
    img = img.resize(new_size, Image.Resampling.LANCZOS)
    left = (img.width - width) // 2
    top = (img.height - height) // 2
    return img.crop((left, top, left + width, top + height))


def _generate_background(width: int, height: int, seed: int) -> Image.Image:
    rng = random.Random(seed)
    palettes = [
        ((24, 30, 35), (53, 84, 96), (202, 184, 118)),
        ((32, 36, 42), (83, 102, 86), (212, 139, 96)),
        ((27, 34, 48), (91, 74, 106), (116, 169, 173)),
        ((39, 43, 37), (92, 82, 61), (178, 181, 146)),
        ((25, 41, 45), (83, 117, 107), (218, 160, 107)),
        ((43, 36, 46), (104, 93, 123), (198, 180, 135)),
    ]
    c1, c2, accent = palettes[seed % len(palettes)]
    img = Image.new("RGB", (width, height), c1)
    draw = ImageDraw.Draw(img, "RGBA")

    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)

    for _ in range(7):
        x = rng.randint(-width // 4, width)
        y = rng.randint(-height // 4, height)
        radius = rng.randint(max(width, height) // 5, max(width, height) // 2)
        alpha = rng.randint(20, 42)
        draw.ellipse((x, y, x + radius, y + radius), fill=(*accent, alpha))

    return img.filter(ImageFilter.GaussianBlur(radius=18))


def _render_slide(bg: Image.Image) -> Image.Image:
    """Return a clean image-only slide; subtitles are rendered separately."""
    img = bg.convert("RGBA")
    shade = Image.new("RGBA", img.size, (0, 0, 0, 58))
    img = Image.alpha_composite(img, shade)
    return img.convert("RGB")
