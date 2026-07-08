"""
core/slideshow.py — Pre-render a beautiful background slideshow video.

Uses ffmpeg's zoompan filter (Ken Burns effect) + xfade transitions to
produce a cinema-quality slideshow from a directory of images.

Why ffmpeg instead of PIL per-frame:
  PIL per-frame at 30fps for a 30-min video = ~54,000 resize calls.
  ffmpeg handles this in hardware-accelerated C — 10-20× faster and
  the zoompan + xfade output is smoother than anything PIL can produce.

Usage (called automatically from ebook_mode/runner.py):
    from core.slideshow import build_slideshow_video
    path = build_slideshow_video(image_paths, out, duration, w, h, cfg)
"""

import os
import re
import math
import random
import subprocess
import tempfile
from utils import get_logger

log = get_logger("core.slideshow")

# ── Ken Burns effect presets ─────────────────────────────────────────────────
# Each preset is (zoom_expr, x_expr, y_expr).
# These are ffmpeg zoompan filter expressions evaluated per-frame.
# 'zoom' and 'on' (frame number) are built-in zoompan variables.
# We use a gentle 1.0→1.06 zoom so it reads as "alive" not zoomed-in.

_KB_PRESETS = [
    # Slow zoom in from centre
    ("min(zoom+0.0009,1.06)",
     "iw/2-(iw/zoom/2)",
     "ih/2-(ih/zoom/2)"),
    # Slow zoom in + drift right
    ("min(zoom+0.0009,1.06)",
     "iw/2-(iw/zoom/2)+on*0.15",
     "ih/2-(ih/zoom/2)"),
    # Slow zoom in + drift left
    ("min(zoom+0.0009,1.06)",
     "iw/2-(iw/zoom/2)-on*0.15",
     "ih/2-(ih/zoom/2)"),
    # Slow zoom out from centre (start zoomed in)
    ("if(eq(on\\,1)\\,1.06\\,max(zoom-0.0009\\,1.0))",
     "iw/2-(iw/zoom/2)",
     "ih/2-(ih/zoom/2)"),
    # Slow zoom in + drift up
    ("min(zoom+0.0009,1.06)",
     "iw/2-(iw/zoom/2)",
     "ih/2-(ih/zoom/2)-on*0.10"),
    # Slow zoom in + drift down-right (diagonal)
    ("min(zoom+0.0009,1.06)",
     "iw/2-(iw/zoom/2)+on*0.10",
     "ih/2-(ih/zoom/2)+on*0.07"),
]

# xfade transition variety — all look smooth, randomised per boundary
_XFADE_TRANSITIONS = [
    "fade", "fade", "fade",          # weighted heavier — always safe
    "slideleft", "slideright",
    "wipeleft", "wiperight",
    "dissolve",
]


def build_slideshow_video(
    image_paths: list,
    output_path: str,
    total_duration: float,
    video_w: int,
    video_h: int,
    cfg=None,
    fps: int = 30,
    slot_dur: float = 7.0,
    xfade_dur: float = 1.8,
    shuffle: bool = True,
    seed: int = 42,
) -> str:
    """
    Render a smooth, beautiful slideshow video to *output_path*.

    Each image gets a Ken Burns effect (random slow zoom + drift).
    Images transition with a smooth xfade.  The slideshow loops
    seamlessly so a short image set covers any video length.

    Returns *output_path* on success, or "" on failure (caller should
    fall back to static image or gradient).
    """
    if not image_paths:
        log.error("[Slideshow] No images provided")
        return ""

    # ── Read config overrides ────────────────────────────────────────
    if cfg is not None:
        slot_dur  = float(getattr(cfg, "SLIDESHOW_SLOT_DUR",   slot_dur))
        xfade_dur = float(getattr(cfg, "SLIDESHOW_XFADE_DUR",  xfade_dur))
        fps       = int(getattr(cfg,   "OUTPUT_FPS",            fps))

    # Clamp xfade to be shorter than slot
    xfade_dur = min(xfade_dur, slot_dur * 0.45)
    effective_slot = slot_dur - xfade_dur          # how far each slot advances

    # ── Shuffle images and build slot list ───────────────────────────
    rng = random.Random(seed)
    paths = list(image_paths)
    if shuffle:
        rng.shuffle(paths)

    n_img = len(paths)
    # How many slots cover total_duration (with a couple extra to be safe)
    n_slots = max(int(math.ceil(total_duration / effective_slot)) + 2, n_img)
    # Cycle through images
    slots = [paths[i % n_img] for i in range(n_slots)]

    log.info("[Slideshow] %d images → %d slots  slot=%.1fs  xfade=%.1fs  dur=%.0fs",
             n_img, n_slots, slot_dur, xfade_dur, total_duration)

    # ── Check image files exist ──────────────────────────────────────
    valid_slots = [p for p in slots if os.path.exists(p)]
    if not valid_slots:
        log.error("[Slideshow] None of the image paths exist on disk!")
        return ""
    if len(valid_slots) < len(slots):
        log.warning("[Slideshow] %d/%d images missing, cycling valid ones",
                    len(slots) - len(valid_slots), len(slots))
        slots = [valid_slots[i % len(valid_slots)] for i in range(n_slots)]

    # Assign Ken Burns presets and xfade transitions
    kb_presets   = [_KB_PRESETS[i % len(_KB_PRESETS)] for i in range(n_slots)]
    xfade_trans  = [rng.choice(_XFADE_TRANSITIONS) for _ in range(n_slots - 1)]

    # ── Build ffmpeg command ─────────────────────────────────────────
    # Each slot is loaded as a looped still image for slot_dur + xfade_dur
    # so the xfade filter has enough frames to work with.
    input_dur = slot_dur + xfade_dur + 0.5   # small safety margin
    d_frames  = int(slot_dur * fps)           # zoompan duration in frames

    cmd = ["ffmpeg", "-y"]

    # Inputs
    for path in slots:
        cmd += ["-loop", "1", "-r", str(fps),
                "-t", f"{input_dur:.3f}", "-i", path]

    # Filter complex
    filters = []

    # Step 1: scale + crop + zoompan for every slot
    for i, (path, (z_expr, x_expr, y_expr)) in enumerate(zip(slots, kb_presets)):
        vf = (
            f"[{i}:v]"
            f"scale={video_w}:{video_h}:force_original_aspect_ratio=increase:flags=bilinear,"
            f"crop={video_w}:{video_h},"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}'"
            f":d={d_frames}:s={video_w}x{video_h}:fps={fps},"
            f"format=yuv420p"
            f"[kv{i}]"
        )
        filters.append(vf)

    # Step 2: chain xfade transitions
    if n_slots == 1:
        filters.append(f"[kv0]copy[out]")
    else:
        prev_label = "kv0"
        for i in range(1, n_slots):
            offset = i * effective_slot
            # Clamp offset: must be > 0 and leave room before total_duration
            offset = max(0.1, offset)
            transition = xfade_trans[i - 1]
            out_label  = "out" if i == n_slots - 1 else f"xf{i}"
            filters.append(
                f"[{prev_label}][kv{i}]"
                f"xfade=transition={transition}:duration={xfade_dur:.3f}:offset={offset:.3f}"
                f"[{out_label}]"
            )
            prev_label = out_label

    filter_complex = ";".join(filters)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t",   f"{total_duration:.3f}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf",    "20",
        "-r",   str(fps),
        output_path,
    ]

    log.info("[Slideshow] Rendering slideshow: %d slots  output=%s", n_slots, output_path)
    log.debug("[Slideshow] ffmpeg filter_complex length: %d chars", len(filter_complex))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # zoompan can fail on some ffmpeg builds — try without it
        log.warning("[Slideshow] zoompan render failed — retrying with simple xfade only\n%s",
                    result.stderr[-600:])
        return _build_simple_xfade(slots, output_path, total_duration,
                                    video_w, video_h, fps, slot_dur,
                                    xfade_dur, xfade_trans, cfg)

    sz = os.path.getsize(output_path) // (1024 * 1024)
    log.info("[Slideshow] ✅ Done — %s  (%d MB)", output_path, sz)
    return output_path


def _build_simple_xfade(
    slots, output_path, total_duration, video_w, video_h,
    fps, slot_dur, xfade_dur, xfade_trans, cfg
) -> str:
    """
    Fallback: xfade without zoompan.  Works on all ffmpeg builds.
    Images are scaled/cropped but no Ken Burns effect.
    """
    log.info("[Slideshow] Fallback: simple xfade (no Ken Burns)")
    effective_slot = slot_dur - xfade_dur
    input_dur      = slot_dur + xfade_dur + 0.5

    cmd = ["ffmpeg", "-y"]
    for path in slots:
        cmd += ["-loop", "1", "-r", str(fps),
                "-t", f"{input_dur:.3f}", "-i", path]

    filters = []
    for i in range(len(slots)):
        filters.append(
            f"[{i}:v]scale={video_w}:{video_h}:force_original_aspect_ratio=increase:flags=bilinear,"
            f"crop={video_w}:{video_h},format=yuv420p[sv{i}]"
        )

    if len(slots) == 1:
        filters.append("[sv0]copy[out]")
    else:
        prev = "sv0"
        for i in range(1, len(slots)):
            offset     = i * effective_slot
            transition = xfade_trans[i - 1] if i - 1 < len(xfade_trans) else "fade"
            out_label  = "out" if i == len(slots) - 1 else f"sf{i}"
            filters.append(
                f"[{prev}][sv{i}]xfade=transition={transition}:"
                f"duration={xfade_dur:.3f}:offset={max(0.1,offset):.3f}[{out_label}]"
            )
            prev = out_label

    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[out]",
        "-t",   f"{total_duration:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-r",   str(fps),
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("[Slideshow] Simple xfade also failed:\n%s", result.stderr[-400:])
        return ""

    log.info("[Slideshow] Fallback slideshow done → %s", output_path)
    return output_path


def resolve_image_dir(cfg) -> list:
    """
    Find all usable images from the config's STORY_BG_DIR or STORY_BG_IMAGES.
    Returns sorted list of absolute paths to .jpg/.jpeg/.png/.webp files.
    """
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG"}

    # Explicit list first
    explicit = getattr(cfg, "STORY_BG_IMAGES", [])
    if explicit:
        paths = [p for p in explicit if os.path.exists(p)]
        if paths:
            log.info("[Slideshow] Using %d explicit images from STORY_BG_IMAGES", len(paths))
            return paths

    # Single image
    single = getattr(cfg, "STORY_BG_IMAGE", "")
    if single and os.path.exists(single):
        log.info("[Slideshow] Single image: %s", single)
        return [single]

    # Directory scan
    bg_dir = getattr(cfg, "STORY_BG_DIR", "background")
    if os.path.isdir(bg_dir):
        paths = sorted([
            os.path.join(bg_dir, f)
            for f in os.listdir(bg_dir)
            if os.path.splitext(f)[1] in IMAGE_EXTS
        ])
        log.info("[Slideshow] Found %d images in %s", len(paths), bg_dir)
        return paths

    log.warning("[Slideshow] No images found (checked STORY_BG_IMAGES, STORY_BG_IMAGE, STORY_BG_DIR=%r)",
                bg_dir)
    return []
