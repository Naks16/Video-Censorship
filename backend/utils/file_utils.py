"""
Temporary file and directory management utilities.
Handles creation, cleanup, and path resolution for the temp workspace.
"""
from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import List

from backend.config import settings

logger = logging.getLogger(__name__)


def create_task_dir(task_id: str) -> Path:
    """Create a isolated working directory for a single extraction task."""
    task_dir = settings.temp_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "frames").mkdir(exist_ok=True)
    return task_dir


def cleanup_task_dir(task_id: str) -> None:
    """Remove all temporary files for a completed (or failed) task."""
    task_dir = settings.temp_dir / task_id
    if task_dir.exists():
        try:
            shutil.rmtree(task_dir)
            logger.info(f"Cleaned up temp dir for task {task_id}")
        except Exception as e:
            logger.warning(f"Cleanup failed for task {task_id}: {e}")


def video_path(task_dir: Path) -> Path:
    return task_dir / "video.mp4"


def audio_path(task_dir: Path) -> Path:
    return task_dir / "audio.mp3"


def frames_dir(task_dir: Path) -> Path:
    return task_dir / "frames"


def list_frame_paths(task_dir: Path) -> List[Path]:
    """Return sorted list of extracted frame image paths."""
    fd = frames_dir(task_dir)
    return sorted(fd.glob("frame_*.jpg"))


def generate_task_id() -> str:
    return uuid.uuid4().hex[:12]


def bytes_to_mb(b: int) -> float:
    return round(b / (1024 * 1024), 2)


def is_ffmpeg_available() -> bool:
    """Check if ffmpeg is available in the system PATH."""
    return shutil.which("ffmpeg") is not None


def is_ffprobe_available() -> bool:
    """Check if ffprobe is available in the system PATH."""
    return shutil.which("ffprobe") is not None


def get_video_metadata(video_path: Path) -> dict:
    """Extract technical metadata from a local video file using ffprobe or cv2."""
    import subprocess
    import json
    import cv2

    metadata = {
        "duration": 0.0,
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "video_codec": "",
        "audio_codec": "",
        "file_format": video_path.suffix.lstrip("."),
    }

    # Try ffprobe first (more detailed)
    if is_ffprobe_available():
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", str(video_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)

            # Format info
            fmt = data.get("format", {})
            metadata["duration"] = float(fmt.get("duration", 0.0))

            # Stream info
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    metadata["width"] = int(stream.get("width", 0))
                    metadata["height"] = int(stream.get("height", 0))
                    metadata["video_codec"] = stream.get("codec_name", "")
                    # Extract FPS if available
                    r_fps = stream.get("r_frame_rate", "0/0")
                    if "/" in r_fps:
                        num, den = map(int, r_fps.split("/"))
                        if den != 0:
                            metadata["fps"] = num / den
                elif stream.get("codec_type") == "audio":
                    metadata["audio_codec"] = stream.get("codec_name", "")

            return metadata
        except Exception as e:
            logger.warning(f"ffprobe extraction failed for {video_path}: {e}")

    # Fallback to OpenCV
    try:
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            metadata["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            metadata["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            metadata["fps"] = float(cap.get(cv2.CAP_PROP_FPS))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if metadata["fps"] > 0:
                metadata["duration"] = frame_count / metadata["fps"]
            cap.release()
    except Exception as e:
        logger.warning(f"OpenCV fallback extraction failed for {video_path}: {e}")

    return metadata


def encode_image_to_base64(image_path: Path) -> str:
    """Encode an image file to a base64 string for OpenAI Vision API."""
    import base64
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
