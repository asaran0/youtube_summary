"""
api/schemas.py — Request/response models for the video generation API.
"""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class QAPair(BaseModel):
    question: str = Field(..., min_length=1, description="Question text (Hindi/English/Hinglish)")
    answer: str = Field(..., min_length=1, description="Answer text (Hindi/English/Hinglish)")


class QAVideoRequest(BaseModel):
    """
    Body for POST /api/v1/qa-videos.

    Only `qa_pairs` is mandatory. Every other field is an optional override
    of qa_mode/config.py — if omitted, the value already set in that config
    file is used, exactly like running the CLI with no flags.
    """
    qa_pairs: list[QAPair] = Field(..., min_length=1, description="List of question/answer pairs")
    title: Optional[str] = Field(None, description="Output filename / metadata title")

    # Optional config overrides — mirror main.py's CLI flags
    language: Optional[Literal["hi", "en", "hig"]] = Field(
        None, description="Override LANGUAGE. Defaults to qa_mode/config.py's LANGUAGE if omitted"
    )
    output_mode: Optional[Literal["reel", "full"]] = Field(
        None, description="Override OUTPUT_MODE (vertical reel vs landscape full)"
    )
    tts_backend: Optional[Literal["xtts", "mms", "macos", "kokoro", "indic_parler", "veena"]] = Field(
        None, description="Override TTS_BACKEND"
    )
    voice_sample: Optional[str] = Field(
        None, description="Path to a voice sample WAV (xtts backend only)"
    )
    voice: Optional[str] = Field(None, description="Override macOS TTS voice name")
    keep_temp: bool = Field(False, description="Keep temporary files after processing")

    @field_validator("qa_pairs")
    @classmethod
    def _non_empty_pairs(cls, v):
        if not v:
            raise ValueError("qa_pairs must contain at least one question/answer pair")
        return v


JobStatus = Literal["queued", "running", "done", "failed"]


class JobSubmitResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobResult(BaseModel):
    video_path: str
    srt_path: str
    meta_path: str
    summary_duration: float


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    queue_position: Optional[int] = None
    error: Optional[str] = None
    result: Optional[JobResult] = None


class BatchQAVideoRequest(BaseModel):
    """
    Body for POST /api/v1/qa-videos/batch.

    Provide the questions either as `qa_pairs` (structured) or as `qa_text`
    (raw "Q: ... A: ..." text, same format as a Q&A file) — exactly one of
    the two. They're split into groups of `questions_per_part` and one video
    is generated per group, titled f"{name}_part{n}".
    """
    name: str = Field(..., min_length=1, description="Base name; parts are named '{name}_part1', '{name}_part2', ...")
    questions_per_part: int = Field(..., ge=1, description="Number of questions per output video")

    qa_pairs: Optional[list[QAPair]] = Field(None, description="Structured list of Q/A pairs")
    qa_text: Optional[str] = Field(None, description="Raw 'Q: ... A: ...' text (same format as a Q&A file)")

    # Optional config overrides — same as QAVideoRequest, applied to every part
    language: Optional[Literal["hi", "en", "hig"]] = None
    output_mode: Optional[Literal["reel", "full"]] = None
    tts_backend: Optional[Literal["xtts", "mms", "macos", "kokoro", "indic_parler", "veena"]] = None
    voice_sample: Optional[str] = None
    voice: Optional[str] = None
    keep_temp: bool = False

    @field_validator("qa_text")
    @classmethod
    def _exactly_one_source(cls, v, info):
        pairs = info.data.get("qa_pairs")
        if not pairs and not v:
            raise ValueError("Provide either qa_pairs or qa_text")
        if pairs and v:
            raise ValueError("Provide only one of qa_pairs or qa_text, not both")
        return v


class BatchPartStatus(BaseModel):
    job_id: str
    part_number: int
    title: str
    status: JobStatus
    error: Optional[str] = None
    result: Optional[JobResult] = None


class BatchSubmitResponse(BaseModel):
    batch_id: str
    name: str
    total_questions: int
    questions_per_part: int
    parts: list[JobSubmitResponse]


class BatchStatusResponse(BaseModel):
    batch_id: str
    name: str
    total_questions: int
    questions_per_part: int
    parts: list[BatchPartStatus]
    overall_status: JobStatus
