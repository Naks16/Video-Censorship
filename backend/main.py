"""
FastAPI application — entry point for the trailer metadata extraction API.

Endpoints:
  POST /api/extract          — Submit a YouTube URL, returns task_id
  GET  /api/status/{id}      — Poll task status
  GET  /api/result/{id}      — Get completed metadata JSON
  GET  /api/stream/{id}      — SSE stream of task progress
  POST /api/batch            — Submit multiple URLs
  GET  /api/export/{id}      — Download result as .json file
  GET  /api/analytics        — Aggregated stats across all processed videos
  GET  /api/health           — Health check
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from backend.agents.aggregator_agent import AggregatorAgent
from backend.agents.audio_agent import AudioAgent, get_whisper_model
from backend.agents.ingestion_agent import IngestionAgent
from backend.agents.metadata_agent import MetadataAgent
from backend.agents.nlp_agent import NLPAgent
from backend.agents.vision_agent import VisionAgent, get_clip_model
from backend.agents.moderation_agent import ModerationAgent
from backend.config import settings
from backend.models.schemas import (
    AnalyticsResponse,
    BatchExtractionRequest,
    ExtractionRequest,
    TaskStatus,
    TrailerMetadata,
    ModerationResult,
)
from backend.utils.file_utils import cleanup_task_dir, generate_task_id, video_path as get_vpath

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── In-memory task store ──────────────────────────────────────────────────────
# Format: { task_id: { status, current_stage, progress, result, error } }
_tasks: Dict[str, Dict[str, Any]] = {}
_analytics: Dict[str, Any] = {
    "genre_distribution": {},
    "language_distribution": {},
    "trailer_type_breakdown": {},
    "total_processed": 0,
    "avg_confidence": {},
    "moderation_stats": {"low": 0, "medium": 0, "high": 0},
}


# ── Lifespan: pre-load heavy models to avoid cold-start latency per request ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Pre-loading AI models...")
    try:
        await asyncio.to_thread(get_whisper_model, settings.whisper_model)
        logger.info("Whisper model ready")
    except Exception as e:
        logger.warning(f"Whisper pre-load failed (will retry on first request): {e}")

    try:
        await asyncio.to_thread(get_clip_model, settings.clip_model)
        logger.info("CLIP model ready")
    except Exception as e:
        logger.warning(f"CLIP pre-load failed (will retry on first request): {e}")

    yield  # App runs here

    logger.info("Shutting down — cleaning up temp files")
    settings.temp_dir.mkdir(exist_ok=True)


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="YouTube Trailer Metadata Extractor",
    description="AI-powered multi-agent pipeline for structured trailer metadata extraction",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "whisper_model": settings.whisper_model,
        "openai_configured": settings.has_openai,
        "youtube_api_configured": settings.has_youtube_api,
    }


@app.post("/api/extract", response_model=TaskStatus, status_code=202)
async def extract(req: ExtractionRequest, bg: BackgroundTasks):
    """Submit a YouTube URL for extraction. Returns task_id immediately."""
    task_id = generate_task_id()
    _tasks[task_id] = {
        "status": "pending",
        "current_stage": "Queued",
        "progress": 0,
        "result": None,
        "error": None,
    }
    bg.add_task(_run_pipeline, task_id, url=req.url)
    return TaskStatus(task_id=task_id, status="pending", current_stage="Queued", progress=0)


@app.post("/api/batch", status_code=202)
async def batch_extract(req: BatchExtractionRequest, bg: BackgroundTasks):
    """Submit multiple URLs for batch extraction."""
    if len(req.urls) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 URLs per batch")

    task_ids = []
    for url in req.urls:
        task_id = generate_task_id()
        _tasks[task_id] = {
            "status": "pending",
            "current_stage": "Queued",
            "progress": 0,
            "result": None,
            "error": None,
        }
        bg.add_task(_run_pipeline, task_id, url=url)
        task_ids.append(task_id)

    return {"task_ids": task_ids, "count": len(task_ids)}


@app.post("/api/upload", response_model=TaskStatus, status_code=202)
async def upload_file(bg: BackgroundTasks, file: UploadFile = File(...)):
    """Upload a local video file for metadata extraction."""
    if not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")

    task_id = generate_task_id()
    task_dir = settings.temp_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    
    local_path = get_vpath(task_dir)
    try:
        with local_path.open("wb") as buffer:
            import shutil
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        file.file.close()

    _tasks[task_id] = {
        "status": "pending",
        "current_stage": "Queued",
        "progress": 0,
        "result": None,
        "error": None,
    }
    bg.add_task(_run_pipeline, task_id, local_path=local_path)
    return TaskStatus(task_id=task_id, status="pending", current_stage="Queued", progress=0)


@app.post("/api/moderate", response_model=TaskStatus, status_code=202)
async def moderate_video(bg: BackgroundTasks, file: UploadFile = File(...)):
    """Upload a local video file for content moderation analysis."""
    if not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")

    task_id = generate_task_id()
    task_dir = settings.temp_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    
    local_path = get_vpath(task_dir)
    try:
        with local_path.open("wb") as buffer:
            import shutil
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        file.file.close()

    _tasks[task_id] = {
        "status": "pending",
        "current_stage": "Queued",
        "progress": 0,
        "result": None,
        "error": None,
    }
    bg.add_task(_run_moderation_pipeline, task_id, local_path=local_path)
    return TaskStatus(task_id=task_id, status="pending", current_stage="Queued", progress=0)


@app.get("/api/status/{task_id}", response_model=TaskStatus)
async def get_status(task_id: str):
    task = _get_task_or_404(task_id)
    return TaskStatus(
        task_id=task_id,
        status=task["status"],
        current_stage=task.get("current_stage"),
        progress=task.get("progress", 0),
        error=task.get("error"),
    )


@app.get("/api/result/{task_id}")
async def get_result(task_id: str):
    task = _get_task_or_404(task_id)
    if task["status"] != "completed":
        raise HTTPException(
            status_code=202,
            detail=f"Task is {task['status']}. Current stage: {task.get('current_stage')}",
        )
    return task["result"]


@app.get("/api/stream/{task_id}")
async def stream_status(task_id: str):
    """Server-Sent Events stream — emits task status updates until done."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return StreamingResponse(
        _sse_generator(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/export/{task_id}")
async def export_result(task_id: str):
    """Download the extracted metadata as a .json file."""
    task = _get_task_or_404(task_id)
    if task["status"] != "completed":
        raise HTTPException(status_code=202, detail="Task not complete yet")

    result = task["result"]
    filename = f"trailer_metadata_{task_id}.json"
    json_bytes = json.dumps(result, indent=2, ensure_ascii=False).encode("utf-8")

    return StreamingResponse(
        iter([json_bytes]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/analytics", response_model=AnalyticsResponse)
async def analytics():
    """Return aggregated stats across all processed videos."""
    return AnalyticsResponse(
        total_processed=_analytics["total_processed"],
        genre_distribution=_analytics["genre_distribution"],
        language_distribution=_analytics["language_distribution"],
        avg_confidence=_analytics["avg_confidence"],
        trailer_type_breakdown=_analytics["trailer_type_breakdown"],
        moderation_stats=_analytics["moderation_stats"],
    )



# ── Pipeline runner ───────────────────────────────────────────────────────────

STAGES = [
    ("Video Ingestion", 15),
    ("Audio Transcription", 35),
    ("Vision Analysis", 55),
    ("NLP Processing", 75),
    ("Moderation Analysis", 85),
    ("Metadata Extraction", 90),
    ("Aggregating Results", 96),
]


async def _run_pipeline(
    task_id: str, 
    url: Optional[str] = None, 
    local_path: Optional[Path] = None
) -> None:
    """
    Executes the full 6-stage agent pipeline for a single URL.
    Updates _tasks[task_id] throughout so the SSE stream can relay progress.
    """
    start = time.time()
    task = _tasks[task_id]

    def update(stage: str, progress: int) -> None:
        task["status"] = "processing"
        task["current_stage"] = stage
        task["progress"] = progress
        logger.info(f"[Pipeline/{task_id}] {stage} ({progress}%)")

    try:
        # Stage 1: Ingestion
        update(STAGES[0][0], STAGES[0][1])
        if local_path:
            ingestion = await IngestionAgent().run_local(local_path, task_id)
            url_for_agg = local_path.name
        else:
            ingestion = await IngestionAgent().run(url, task_id)
            url_for_agg = url

        # Stage 2: Audio (async to thread — Whisper is CPU-bound)
        update(STAGES[1][0], STAGES[1][1])
        audio = await AudioAgent(settings.whisper_model).run(ingestion)

        # Stage 3: Vision (async to thread — CLIP is compute-bound)
        update(STAGES[2][0], STAGES[2][1])
        vision = await VisionAgent().run(ingestion)

        # Stage 4: NLP (async — awaits OpenAI API call)
        update(STAGES[3][0], STAGES[3][1])
        nlp = await NLPAgent().run(ingestion, audio, vision)

        # Stage 5: Moderation
        update(STAGES[4][0], STAGES[4][1])
        moderation = await ModerationAgent().run(ingestion, audio)

        # Stage 6: Metadata (async — awaits OpenAI API call)
        update(STAGES[5][0], STAGES[5][1])
        metadata = await MetadataAgent().run(ingestion, audio, vision)

        # Stage 7: Aggregation (sync, fast)
        update(STAGES[6][0], STAGES[6][1])
        final: TrailerMetadata = AggregatorAgent().run(
            task_id=task_id,
            url=url_for_agg,
            ingestion=ingestion,
            audio=audio,
            vision=vision,
            nlp=nlp,
            metadata=metadata,
            moderation=moderation,
            start_time=start,
        )

        task["status"] = "completed"
        task["current_stage"] = "Done"
        task["progress"] = 100
        task["result"] = final.model_dump(mode="json")
        _update_analytics(final)

    except Exception as e:
        logger.exception(f"[Pipeline/{task_id}] Fatal error: {e}")
        task["status"] = "failed"
        task["error"] = str(e)
        task["progress"] = 0
    finally:
        # Cleanup temp directory after processing (regardless of success/fail)
        await asyncio.to_thread(cleanup_task_dir, task_id)


MODERATION_STAGES = [
    ("Video Ingestion", 20),
    ("Audio Transcription", 50),
    ("Moderation Analysis", 90),
]


async def _run_moderation_pipeline(
    task_id: str, 
    local_path: Path
) -> None:
    """
    Executes the moderation pipeline: Ingestion -> Audio -> Moderation.
    """
    task = _tasks[task_id]

    def update(stage: str, progress: int) -> None:
        task["status"] = "processing"
        task["current_stage"] = stage
        task["progress"] = progress
        logger.info(f"[ModerationPipeline/{task_id}] {stage} ({progress}%)")

    try:
        # Stage 1: Ingestion
        update(MODERATION_STAGES[0][0], MODERATION_STAGES[0][1])
        ingestion = await IngestionAgent().run_local(local_path, task_id)

        # Stage 2: Audio
        update(MODERATION_STAGES[1][0], MODERATION_STAGES[1][1])
        audio = await AudioAgent(settings.whisper_model).run(ingestion)

        # Stage 3: Moderation
        update(MODERATION_STAGES[2][0], MODERATION_STAGES[2][1])
        moderation = await ModerationAgent().run(ingestion, audio)

        task["status"] = "completed"
        task["current_stage"] = "Done"
        task["progress"] = 100
        task["result"] = moderation.model_dump(mode="json")

    except Exception as e:
        logger.exception(f"[ModerationPipeline/{task_id}] Fatal error: {e}")
        task["status"] = "failed"
        task["error"] = str(e)
        task["progress"] = 0
    finally:
        await asyncio.to_thread(cleanup_task_dir, task_id)


async def _sse_generator(task_id: str) -> AsyncGenerator[str, None]:
    """Yields SSE data strings until task is completed or failed."""
    while True:
        task = _tasks.get(task_id, {})
        payload = {
            "task_id": task_id,
            "status": task.get("status", "unknown"),
            "current_stage": task.get("current_stage"),
            "progress": task.get("progress", 0),
            "error": task.get("error"),
        }
        yield f"data: {json.dumps(payload)}\n\n"

        if task.get("status") in ("completed", "failed"):
            break
        await asyncio.sleep(0.8)


def _get_task_or_404(task_id: str) -> Dict[str, Any]:
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return _tasks[task_id]


def _update_analytics(result: TrailerMetadata) -> None:
    """Update in-memory analytics with data from a completed extraction."""
    _analytics["total_processed"] += 1

    for genre in result.content_descriptors.genres:
        _analytics["genre_distribution"][genre] = (
            _analytics["genre_distribution"].get(genre, 0) + 1
        )

    for lang in result.basic_identification.languages:
        _analytics["language_distribution"][lang] = (
            _analytics["language_distribution"].get(lang, 0) + 1
        )

    tt = result.trailer_specific.trailer_type
    if tt:
        _analytics["trailer_type_breakdown"][tt] = (
            _analytics["trailer_type_breakdown"].get(tt, 0) + 1
        )

    # Running average confidence
    for k, v in result.confidence_scores.items():
        existing = _analytics["avg_confidence"].get(k, v)
        n = _analytics["total_processed"]
        _analytics["avg_confidence"][k] = round((existing * (n - 1) + v) / n, 4)

    # Moderation stats
    if result.moderation:
        sev = result.moderation.severity
        _analytics["moderation_stats"][sev] = _analytics["moderation_stats"].get(sev, 0) + 1



# ── Dev entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        reload_dirs=["backend"],
    )
