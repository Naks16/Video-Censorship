"""
Audio Agent — Uses OpenAI Whisper (base model) for:
  - Speech-to-text transcription with word-level timestamps
  - Automatic language detection
  - Confidence estimation based on avg log-probability
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from backend.agents.ingestion_agent import IngestionResult

logger = logging.getLogger(__name__)

# ── Whisper model is loaded once and cached on the app object ─────────────────
_whisper_model = None


def get_whisper_model(size: str = "base"):
    """Lazy load + cache the Whisper model (module-level singleton)."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper

            logger.info(f"[Audio] Loading Whisper model: {size}")
            _whisper_model = whisper.load_model(size)
            logger.info("[Audio] Whisper model loaded successfully")
        except ImportError:
            logger.error("[Audio] openai-whisper not installed")
            raise
    return _whisper_model


@dataclass
class AudioResult:
    transcript: str = ""
    language: str = ""
    language_confidence: float = 0.0
    segments: List[dict] = field(default_factory=list)
    detected_languages: List[str] = field(default_factory=list)
    avg_log_prob: float = 0.0
    transcription_confidence: float = 0.0
    errors: List[str] = field(default_factory=list)


# Language code → display name map (covering all major Indian + world languages)
LANGUAGE_NAMES = {
    "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "ml": "Malayalam",
    "kn": "Kannada", "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi",
    "bn": "Bengali", "or": "Odia", "as": "Assamese", "ur": "Urdu",
    "sa": "Sanskrit", "en": "English", "fr": "French", "es": "Spanish",
    "de": "German", "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
    "ar": "Arabic", "pt": "Portuguese", "ru": "Russian", "it": "Italian",
}


class AudioAgent:
    """
    Transcribes audio from the downloaded video and detects spoken language(s).
    Whisper's `base` model is used per user config for speed/accuracy balance.
    """

    def __init__(self, model_size: str = "base") -> None:
        self.model_size = model_size
        self.name = "audio"

    async def run(self, ingestion: IngestionResult) -> AudioResult:
        result = AudioResult()

        # Determine audio source: prefer extracted mp3, fall back to video file
        audio_source = ingestion.audio_path or ingestion.video_path

        from backend.utils import file_utils
        if not file_utils.is_ffmpeg_available():
            msg = "[Audio] Transcription skipped: ffmpeg not installed"
            logger.warning(msg)
            result.errors.append(msg)
            return result

        if not audio_source or not audio_source.exists():
            msg = "[Audio] No audio source found for transcription"
            logger.warning(msg)
            result.errors.append(msg)
            return result

        logger.info(f"[Audio] Transcribing: {audio_source.name}")

        try:
            result = await asyncio.to_thread(
                self._transcribe, audio_source, result
            )
        except Exception as e:
            logger.error(f"[Audio] Transcription failed: {e}")
            result.errors.append(str(e))

        return result

    def _transcribe(self, audio_path: Path, result: AudioResult) -> AudioResult:
        import whisper

        model = get_whisper_model(self.model_size)

        # Whisper accepts any ffmpeg-decodable file (mp3, mp4, m4a, webm, etc.)
        transcription = model.transcribe(
            str(audio_path),
            task="transcribe",
            verbose=False,
            word_timestamps=True,
            condition_on_previous_text=True,
        )

        # Full transcript text
        result.transcript = transcription.get("text", "").strip()

        # Language detection
        lang_code = transcription.get("language", "")
        result.language = LANGUAGE_NAMES.get(lang_code, lang_code.upper())

        # Segments with timestamps
        raw_segments = transcription.get("segments", [])
        result.segments = [
            {
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
                "avg_logprob": round(seg.get("avg_logprob", 0.0), 4),
            }
            for seg in raw_segments
        ]

        # Confidence from average log-probability (Whisper's own metric)
        # avg_logprob is typically in [-2.0, 0.0]; map to [0, 1]
        if result.segments:
            avg_lp = sum(s["avg_logprob"] for s in result.segments) / len(result.segments)
            result.avg_log_prob = round(avg_lp, 4)
            # Simple linear map: -1.5 → 0, 0.0 → 1.0 (clamp)
            conf = min(1.0, max(0.0, (avg_lp + 1.5) / 1.5))
            result.transcription_confidence = round(conf, 4)
            result.language_confidence = round(conf * 0.95, 4)  # slight discount

        # Try to detect multiple languages in different segments
        unique_langs = set()
        try:
            for seg in raw_segments:
                seg_lang = seg.get("language")
                if seg_lang:
                    unique_langs.add(LANGUAGE_NAMES.get(seg_lang, seg_lang.upper()))
        except Exception:
            pass
        result.detected_languages = list(unique_langs) or ([result.language] if result.language else [])

        logger.info(
            f"[Audio] Transcribed {len(result.segments)} segments, "
            f"language={result.language}, confidence={result.transcription_confidence}"
        )
        return result
