"""
api/main.py — FastAPI backend for the Hindi/English/Hinglish video generator.

Run from the project root (so `qa_mode`, `core`, `utils` import correctly):

    uvicorn api.main:app --reload --port 8000

Then:
    POST /api/v1/qa-videos        submit a list of Q/A pairs -> job_id
    GET  /api/v1/qa-videos/{id}   poll status / get result paths
    GET  /api/v1/qa-videos/{id}/video   download the finished mp4
    GET  /api/v1/qa-videos/{id}/srt     download the subtitle file
    GET  /api/v1/qa-videos/{id}/meta    download the metadata json
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from api.jobs import manager
from api.schemas import (
    QAVideoRequest, JobSubmitResponse, JobStatusResponse, JobResult,
    BatchQAVideoRequest, BatchSubmitResponse, BatchStatusResponse,
    BatchPartStatus,
)
from qa_mode.loader import parse_qa_text

app = FastAPI(
    title="Hindi/English/Hinglish Video Generator API",
    description="Submit a list of question/answer pairs and language config; "
                 "get back a narrated slideshow video.",
    version="1.0.0",
)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


def _build_overrides(language=None, output_mode=None, tts_backend=None,
                      voice_sample=None, voice=None) -> dict:
    overrides = {
        "language": language,
        "output_mode": output_mode,
        "tts_backend": tts_backend,
        "macos_tts_voice": voice,
    }
    if voice_sample:
        overrides["xtts_voice_sample"] = voice_sample
    return overrides


@app.post("/api/v1/qa-videos", response_model=JobSubmitResponse, status_code=202)
def create_qa_video(req: QAVideoRequest):
    """
    Submit a list of Q/A pairs for video generation.

    Everything besides `qa_pairs` is optional — omitted fields fall back to
    whatever is set in qa_mode/config.py (language, output mode, TTS backend,
    styling, fonts, ffmpeg settings, etc). This mirrors the CLI's
    `python main.py --mode qa --file ... [--language ...] [--tts-backend ...]`.
    """
    pairs = [(p.question, p.answer) for p in req.qa_pairs]
    overrides = _build_overrides(req.language, req.output_mode, req.tts_backend,
                                  req.voice_sample, req.voice)

    job = manager.submit(
        qa_pairs=pairs,
        title=req.title or "interview_prep",
        overrides=overrides,
        keep_temp=req.keep_temp,
    )
    return JobSubmitResponse(job_id=job.job_id, status=job.status)


def _batch_to_submit_response(batch) -> BatchSubmitResponse:
    parts = []
    for jid in batch.job_ids:
        job = manager.get(jid)
        parts.append(JobSubmitResponse(job_id=job.job_id, status=job.status))
    return BatchSubmitResponse(
        batch_id=batch.batch_id, name=batch.name,
        total_questions=batch.total_questions,
        questions_per_part=batch.questions_per_part,
        parts=parts,
    )


@app.post("/api/v1/qa-videos/batch", response_model=BatchSubmitResponse, status_code=202)
def create_qa_video_batch(req: BatchQAVideoRequest):
    """
    Submit a name + question list (or raw Q&A text) + questions_per_part.
    The questions are split into consecutive groups of `questions_per_part`
    and one video is generated per group, named '{name}_part1', '{name}_part2',
    etc, until all questions are consumed. Each part is queued as its own job
    and processed in order.
    """
    if req.qa_pairs:
        pairs = [(p.question, p.answer) for p in req.qa_pairs]
    else:
        try:
            pairs = parse_qa_text(req.qa_text)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    overrides = _build_overrides(req.language, req.output_mode, req.tts_backend,
                                  req.voice_sample, req.voice)

    batch = manager.submit_batch(
        qa_pairs=pairs, name=req.name, questions_per_part=req.questions_per_part,
        overrides=overrides, keep_temp=req.keep_temp,
    )
    return _batch_to_submit_response(batch)


@app.post("/api/v1/qa-videos/batch/upload", response_model=BatchSubmitResponse, status_code=202)
async def create_qa_video_batch_from_file(
    file: UploadFile = File(..., description="Q&A text file: 'Q: ...' / 'A: ...' pairs"),
    name: str = Form(...),
    questions_per_part: int = Form(..., ge=1),
    language: str | None = Form(None),
    output_mode: str | None = Form(None),
    tts_backend: str | None = Form(None),
    voice_sample: str | None = Form(None),
    voice: str | None = Form(None),
    keep_temp: bool = Form(False),
):
    """Same as POST /api/v1/qa-videos/batch, but the questions come from an
    uploaded .txt file (the same 'Q: ... A: ...' format the CLI's --file expects)
    instead of a JSON body."""
    raw = (await file.read()).decode("utf-8")
    try:
        pairs = parse_qa_text(raw)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    overrides = _build_overrides(language, output_mode, tts_backend, voice_sample, voice)

    batch = manager.submit_batch(
        qa_pairs=pairs, name=name, questions_per_part=questions_per_part,
        overrides=overrides, keep_temp=keep_temp,
    )
    return _batch_to_submit_response(batch)


@app.get("/api/v1/qa-videos/batch/{batch_id}", response_model=BatchStatusResponse)
def get_batch(batch_id: str):
    batch = manager.get_batch(batch_id)
    if batch is None:
        raise HTTPException(404, f"Unknown batch_id: {batch_id}")

    parts = []
    statuses = []
    for jid in batch.job_ids:
        job = manager.get(jid)
        result = JobResult(**job.result) if job.status == "done" and job.result else None
        parts.append(BatchPartStatus(
            job_id=job.job_id, part_number=job.part_number, title=job.title,
            status=job.status, error=job.error, result=result,
        ))
        statuses.append(job.status)

    if "failed" in statuses:
        overall = "failed"
    elif all(s == "done" for s in statuses):
        overall = "done"
    elif any(s == "running" for s in statuses):
        overall = "running"
    else:
        overall = "queued"

    return BatchStatusResponse(
        batch_id=batch.batch_id, name=batch.name,
        total_questions=batch.total_questions,
        questions_per_part=batch.questions_per_part,
        parts=parts, overall_status=overall,
    )


@app.get("/api/v1/qa-videos/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str):
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(404, f"Unknown job_id: {job_id}")

    result = None
    if job.status == "done" and job.result:
        result = JobResult(**job.result)

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        queue_position=manager.queue_position(job_id) if job.status == "queued" else None,
        error=job.error,
        result=result,
    )


def _require_done(job_id: str):
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(404, f"Unknown job_id: {job_id}")
    if job.status == "failed":
        raise HTTPException(500, f"Job failed: {job.error}")
    if job.status != "done":
        raise HTTPException(409, f"Job is not finished yet (status={job.status})")
    return job


@app.get("/api/v1/qa-videos/{job_id}/video")
def download_video(job_id: str):
    job = _require_done(job_id)
    path = job.result["video_path"]
    if not os.path.exists(path):
        raise HTTPException(410, "Video file no longer exists on disk")
    return FileResponse(path, media_type="video/mp4", filename=os.path.basename(path))


@app.get("/api/v1/qa-videos/{job_id}/srt")
def download_srt(job_id: str):
    job = _require_done(job_id)
    path = job.result["srt_path"]
    if not os.path.exists(path):
        raise HTTPException(410, "Subtitle file no longer exists on disk")
    return FileResponse(path, media_type="text/plain", filename=os.path.basename(path))


@app.get("/api/v1/qa-videos/{job_id}/meta")
def download_meta(job_id: str):
    job = _require_done(job_id)
    path = job.result["meta_path"]
    if not os.path.exists(path):
        raise HTTPException(410, "Metadata file no longer exists on disk")
    return FileResponse(path, media_type="application/json", filename=os.path.basename(path))
