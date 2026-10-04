"""
Ingestion Agent — Downloads YouTube video, extracts audio + frames,
and collects all available metadata via yt-dlp and optionally YouTube API.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import yt_dlp  # type: ignore

from backend.config import settings
from backend.utils import file_utils
from backend.utils.youtube_api import extract_video_id, fetch_youtube_metadata

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    task_id: str
    task_dir: Path
    video_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    frame_paths: List[Path] = field(default_factory=list)

    # Raw YouTube metadata (merged from yt-dlp + API)
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    upload_date: str = ""
    duration: float = 0.0          # seconds
    views: int = 0
    likes: int = 0
    thumbnail_url: str = ""
    channel: str = ""
    captions: Optional[str] = None
    video_id: str = ""

    # Technical info from yt-dlp
    resolution: str = ""
    aspect_ratio: str = ""
    frame_rate: float = 0.0
    audio_codec: str = ""
    video_codec: str = ""
    file_format: str = ""

    errors: List[str] = field(default_factory=list)


class IngestionAgent:
    """
    Downloads the YouTube trailer, extracts frames and audio,
    and gathers metadata from yt-dlp + YouTube Data API.
    """

    def __init__(self) -> None:
        self.name = "ingestion"

    async def run(self, url: str, task_id: str) -> IngestionResult:
        task_dir = file_utils.create_task_dir(task_id)
        result = IngestionResult(task_id=task_id, task_dir=task_dir)
        result.video_id = extract_video_id(url) or ""

        logger.info(f"[Ingestion] Starting for URL: {url}")

        # 1. Download video + collect yt-dlp metadata
        await self._download(url, result)

        # 2. Optionally enrich with YouTube Data API
        if settings.has_youtube_api and result.video_id:
            api_data = await fetch_youtube_metadata(
                result.video_id, settings.youtube_api_key
            )
            self._merge_api_data(result, api_data)

        # 3. Extract frames
        if result.video_path and result.video_path.exists():
            result.frame_paths = await asyncio.to_thread(
                self._extract_frames, result.video_path, result.task_dir
            )

        logger.info(
            f"[Ingestion] Done — {len(result.frame_paths)} frames, "
            f"video={result.video_path is not None}"
        )
        return result

    async def run_local(self, file_path: Path, task_id: str) -> IngestionResult:
        """Process a locally uploaded video file."""
        task_dir = file_utils.create_task_dir(task_id)
        result = IngestionResult(task_id=task_id, task_dir=task_dir)
        
        # Move the uploaded file if it's not already in the task directory
        vpath = file_utils.video_path(task_dir)
        if file_path.absolute() != vpath.absolute():
            import shutil
            shutil.copy(file_path, vpath)
        
        result.video_path = vpath
        result.title = file_path.name
        result.file_format = file_path.suffix.lstrip(".")

        logger.info(f"[Ingestion] Processing local file: {file_path}")

        # 1. Extract technical metadata
        meta = file_utils.get_video_metadata(vpath)
        result.duration = meta["duration"]
        result.resolution = f"{meta['width']}x{meta['height']}"
        if meta["width"] and meta["height"]:
            gcd = _gcd(meta["width"], meta["height"])
            result.aspect_ratio = f"{meta['width']//gcd}:{meta['height']//gcd}"
        result.frame_rate = meta["fps"]
        result.video_codec = meta["video_codec"]
        result.audio_codec = meta["audio_codec"]

        # 2. Extract frames
        result.frame_paths = await asyncio.to_thread(
            self._extract_frames, result.video_path, result.task_dir
        )

        logger.info(f"[Ingestion] Local processing done — {len(result.frame_paths)} frames")
        return result

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _download(self, url: str, result: IngestionResult) -> None:
        """Use yt-dlp to download the video and collect metadata."""
        vpath = file_utils.video_path(result.task_dir)
        apath = result.task_dir / "audio.mp3"

        has_ffmpeg = file_utils.is_ffmpeg_available()
        if not has_ffmpeg:
            logger.warning("[Ingestion] ffmpeg not found — using fallback format (no audio extraction)")
            result.errors.append("ffmpeg not installed — audio transcription and high-quality merging disabled")

        ydl_opts: Dict[str, Any] = {
            "outtmpl": str(vpath.with_suffix("")),
            "quiet": True,
            "no_warnings": True,
            "writeautomaticsub": False,
            "writethumbnail": False,
        }

        if has_ffmpeg:
            ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            ydl_opts["merge_output_format"] = "mp4"
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",
                },
            ]
            ydl_opts["postprocessor_args"] = ["-ac", "1"]  # mono for Whisper
        else:
            # Fallback: single file that doesn't need merging
            ydl_opts["format"] = "best[ext=mp4]/best"

        try:
            info = await asyncio.to_thread(self._run_ydl, url, ydl_opts)
            if info:
                self._populate_from_info(result, info, vpath, apath)
        except Exception as e:
            logger.error(f"[Ingestion] yt-dlp download error: {e}")
            result.errors.append(f"Download failed: {e}")

            # Fallback: metadata-only (no video file)
            meta_opts: Dict[str, Any] = {
                "quiet": True,
                "skip_download": True,
                "no_warnings": True,
            }
            try:
                info = await asyncio.to_thread(self._run_ydl, url, meta_opts)
                if info:
                    self._populate_from_info(result, info, None, None)
            except Exception as e2:
                logger.error(f"[Ingestion] Metadata-only fallback also failed: {e2}")
                result.errors.append(f"Metadata extraction failed: {e2}")

    @staticmethod
    def _run_ydl(url: str, opts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=not opts.get("skip_download", False))

    def _populate_from_info(
        self,
        result: IngestionResult,
        info: Dict[str, Any],
        vpath: Optional[Path],
        apath: Optional[Path],
    ) -> None:
        result.title = info.get("title", "")
        result.description = info.get("description", "") or ""
        result.tags = info.get("tags") or []
        result.views = int(info.get("view_count") or 0)
        result.likes = int(info.get("like_count") or 0)
        result.thumbnail_url = info.get("thumbnail", "")
        result.channel = info.get("uploader", "") or info.get("channel", "")
        result.duration = float(info.get("duration") or 0)

        raw_date = info.get("upload_date", "")
        if raw_date and len(raw_date) == 8:
            result.upload_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        else:
            result.upload_date = raw_date

        # Technical format info (from the best selected format)
        fmt = info.get("requested_formats", [{}])
        vfmt = next((f for f in fmt if f.get("vcodec") and f["vcodec"] != "none"), {})
        afmt = next((f for f in fmt if f.get("acodec") and f["acodec"] != "none"), {})

        width = vfmt.get("width") or info.get("width")
        height = vfmt.get("height") or info.get("height")
        if width and height:
            result.resolution = f"{width}x{height}"
            gcd = _gcd(int(width), int(height))
            result.aspect_ratio = f"{int(width)//gcd}:{int(height)//gcd}"

        result.frame_rate = float(vfmt.get("fps") or info.get("fps") or 0)
        result.audio_codec = afmt.get("acodec", "") or info.get("acodec", "")
        result.video_codec = vfmt.get("vcodec", "") or info.get("vcodec", "")
        result.file_format = info.get("ext", "mp4")

        # Set paths after download
        if vpath:
            actual = vpath.with_suffix(".mp4")
            if actual.exists():
                result.video_path = actual
        if apath:
            # yt-dlp renames the audio file
            for ext in (".mp3", ".m4a", ".webm", ".opus"):
                candidate = result.task_dir / f"video{ext}"
                if candidate.exists():
                    result.audio_path = candidate
                    break

    def _merge_api_data(self, result: IngestionResult, api_data: Dict[str, Any]) -> None:
        """Overlay YouTube API data on top of yt-dlp data — API is more authoritative."""
        if not api_data:
            return
        result.views = api_data.get("views") or result.views
        result.likes = api_data.get("likes") or result.likes
        result.thumbnail_url = api_data.get("thumbnail_url") or result.thumbnail_url
        result.description = api_data.get("description") or result.description
        result.captions = api_data.get("captions")
        # API tags can augment yt-dlp tags
        api_tags = api_data.get("tags") or []
        combined = list(dict.fromkeys(result.tags + api_tags))
        result.tags = combined

    def _extract_frames(self, video_path: Path, task_dir: Path) -> List[Path]:
        """Extract one frame every `frame_interval_seconds` using OpenCV."""
        frames_path = file_utils.frames_dir(task_dir)
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            logger.error(f"[Ingestion] Cannot open video: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        interval = int(fps * settings.frame_interval_seconds)
        max_frames = settings.max_frames

        saved: List[Path] = []
        frame_idx = 0
        saved_count = 0

        while cap.isOpened() and saved_count < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % interval == 0:
                out_path = frames_path / f"frame_{saved_count:04d}.jpg"
                cv2.imwrite(str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                saved.append(out_path)
                saved_count += 1
            frame_idx += 1

        cap.release()
        logger.info(f"[Ingestion] Extracted {len(saved)} frames from {total_frames} total")
        return saved


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a
