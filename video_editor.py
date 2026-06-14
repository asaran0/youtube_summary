"""
video_editor.py — Cut, assemble, and export the summary video.

Pipeline inside this module:
    1.  Cut the selected chunks from the original video.
    2.  Concatenate them with short cross-fade transitions.
    3.  Resize / pad to the target resolution (YouTube 16:9 or Reel 9:16).
    4.  Overlay animated topic banners (from banner_maker.py).
    5.  Export a "raw" summary video (without burned-in subtitles yet).
        The subtitle burn happens afterwards in subtitle_handler.py.
"""

import os
import subprocess

import config
from utils import get_logger, ensure_dirs

log = get_logger("video_editor")

# Transition duration between clips (seconds)
TRANSITION_DUR = 0.4


# ─────────────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────────────

def compile_video(
    source_video_path: str,
    selected_chunks:   list[dict],
    banner_clips:      list,           # moviepy clips from banner_maker
    is_reel:           bool,
    output_path:       str,
) -> None:
    """
    Build and export the summary video.

    Steps:
        a) Cut individual clips using ffmpeg (fast, no re-encode).
        b) Concatenate with ffmpeg concat demuxer.
        c) Resize to target resolution.
        d) Overlay banners using moviepy CompositeVideoClip.
        e) Write final file.
    """
    ensure_dirs(config.TEMP_DIR, config.OUTPUT_DIR)

    # Target resolution
    target_w, target_h = (
        (config.REEL_WIDTH, config.REEL_HEIGHT)
        if is_reel
        else (config.YOUTUBE_WIDTH, config.YOUTUBE_HEIGHT)
    )
    log.info("Target resolution: %d × %d", target_w, target_h)

    # ── Step 1: cut individual chunk clips ──────────────────────────────
    clip_paths = _cut_chunks(source_video_path, selected_chunks)
    log.info("Cut %d clips", len(clip_paths))

    # ── Step 2: concatenate clips ───────────────────────────────────────
    concat_path = os.path.join(config.TEMP_DIR, "concat_raw.mp4")
    _ffmpeg_concat(clip_paths, concat_path)
    log.info("Concatenated → %s", concat_path)

    # ── Step 3: resize / letterbox / pillarbox to target resolution ─────
    resized_path = os.path.join(config.TEMP_DIR, "resized.mp4")
    _ffmpeg_resize(concat_path, resized_path, target_w, target_h)
    log.info("Resized → %s", resized_path)

    # ── Step 4: overlay banners (moviepy) ───────────────────────────────
    if banner_clips:
        _overlay_banners(resized_path, banner_clips, output_path)
    else:
        # No banners – just copy the resized file
        import shutil
        shutil.copy2(resized_path, output_path)

    log.info("Video compilation complete → %s", output_path)


# ─────────────────────────────────────────────────────────────
#  STEP 1 – CUT CHUNKS
# ─────────────────────────────────────────────────────────────

def _cut_chunks(source: str, chunks: list[dict]) -> list[str]:
    """
    Use ffmpeg stream copy to cut each chunk without re-encoding.
    Very fast and preserves original quality.
    """
    clip_paths = []
    for i, chunk in enumerate(chunks):
        start = chunk["start"]
        end   = chunk["end"]
        dur   = end - start
        if dur < 0.2:
            continue

        out = os.path.join(config.TEMP_DIR, f"clip_{i:04d}.mp4")

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i",  source,
            "-t",  str(dur),
            "-c",  "copy",       # stream copy = no re-encode
            "-avoid_negative_ts", "make_zero",
            out,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(out):
            clip_paths.append(out)
        else:
            log.warning("Failed to cut clip %d (%.1f–%.1f s)", i, start, end)

    return clip_paths


# ─────────────────────────────────────────────────────────────
#  STEP 2 – CONCATENATE
# ─────────────────────────────────────────────────────────────

def _ffmpeg_concat(clip_paths: list[str], output: str) -> None:
    """
    Concatenate clips using ffmpeg concat demuxer.
    This re-encodes to ensure uniform stream parameters.
    """
    # Write a concat list file already have /temp in the file.
    list_file = os.path.join("", "concat_list.txt")
    with open(list_file, "w") as f:
        for p in clip_paths:
            # Escape single quotes in path
            safe_p = p.replace("'", "'\\''")
            f.write(f"file '{safe_p}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f",    "concat",
        "-safe", "0",
        "-i",    list_file,
        # Re-encode to ensure consistent codec/timing
        "-c:v", config.VIDEO_CODEC,
        "-crf", str(config.CRF),
        "-c:a", config.AUDIO_CODEC,
        "-b:a", config.AUDIO_BITRATE,
        "-r",   str(config.OUTPUT_FPS),
        output,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("ffmpeg concat failed:\n%s", result.stderr[-3000:])
        raise RuntimeError("ffmpeg concat step failed")


# ─────────────────────────────────────────────────────────────
#  STEP 3 – RESIZE / PAD
# ─────────────────────────────────────────────────────────────

def _ffmpeg_resize(input_path: str, output: str, w: int, h: int) -> None:
    """
    Scale video to fit inside w×h while preserving aspect ratio.
    Letterbox (horizontal bars) or pillarbox (vertical bars) with black fill.
    """
    # scale2ref: scale to fit, then pad to exact size
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i",   input_path,
        "-vf",  vf,
        "-c:v", config.VIDEO_CODEC,
        "-crf", str(config.CRF),
        "-c:a", "copy",
        output,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("ffmpeg resize failed:\n%s", result.stderr[-2000:])
        raise RuntimeError("ffmpeg resize step failed")


# ─────────────────────────────────────────────────────────────
#  STEP 4 – OVERLAY BANNERS  (moviepy)
# ─────────────────────────────────────────────────────────────

def _overlay_banners(
    input_video: str,
    banner_clips: list,
    output_path:  str,
) -> None:
    """Composite banner clips on top of the video using moviepy."""
    from moviepy.editor import VideoFileClip, CompositeVideoClip

    log.info("Loading video for banner compositing …")
    base = VideoFileClip(input_video)

    all_clips = [base] + banner_clips
    composite = CompositeVideoClip(all_clips)

    log.info("Writing final video with banners …")
    composite.write_videofile(
        output_path,
        fps=config.OUTPUT_FPS,
        codec=config.VIDEO_CODEC,
        audio_codec=config.AUDIO_CODEC,
        bitrate=config.VIDEO_BITRATE,
        audio_bitrate=config.AUDIO_BITRATE,
        logger="bar",            # shows a progress bar
        threads=4,               # use multiple CPU cores
    )
    base.close()
    composite.close()
