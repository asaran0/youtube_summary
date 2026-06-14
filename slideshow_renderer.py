"""
slideshow_renderer.py - Build a new video from image slides plus generated TTS.

This avoids reusing the original YouTube video frames. If the user provides
background images in config.BACKGROUND_IMAGE_PATHS or config.BACKGROUND_DIR,
those are used as a slideshow. Otherwise, original simple background images
are generated locally.
"""

import os
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import config
from utils import ensure_dirs, get_logger

log = get_logger("slideshow")


def compile_slideshow_video(
    selected_chunks: list[dict],
    audio_path: str,
    output_path: str,
    video_width: int,
    video_height: int,
    font_path: str,
    title: str = "",
) -> None:
    """Render image slides and mux them with the generated narration."""
    ensure_dirs(config.TEMP_DIR, config.OUTPUT_DIR)

    slide_dir = os.path.join(config.TEMP_DIR, "slides")
    ensure_dirs(slide_dir)

    backgrounds = _load_backgrounds(video_width, video_height)
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

    list_file = os.path.join(config.TEMP_DIR, "slideshow_concat.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for path, duration in slide_paths:
            safe_path = path.replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")
            f.write(f"duration {duration:.3f}\n")
        safe_last = slide_paths[-1][0].replace("'", "'\\''")
        f.write(f"file '{safe_last}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", os.path.abspath(list_file),
        "-i", os.path.abspath(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-vf", f"fps={config.OUTPUT_FPS},format=yuv420p",
        "-c:v", config.VIDEO_CODEC,
        "-crf", str(config.CRF),
        "-preset", "veryfast",
        "-c:a", config.AUDIO_CODEC,
        "-b:a", config.AUDIO_BITRATE,
        "-shortest",
        os.path.abspath(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("ffmpeg slideshow failed:\n%s", result.stderr[-3000:])
        raise RuntimeError("ffmpeg slideshow step failed")

    log.info("Slideshow video complete -> %s", output_path)


def _load_backgrounds(width: int, height: int) -> list[Image.Image]:
    paths = _configured_background_paths()
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


def _configured_background_paths() -> list[str]:
    paths = [p for p in config.BACKGROUND_IMAGE_PATHS if os.path.exists(p)]
    bg_dir = Path(config.BACKGROUND_DIR)
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
