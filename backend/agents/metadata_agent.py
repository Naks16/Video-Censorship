"""
Metadata Agent — Uses LLM + regex to extract structural identification fields:
movie name, release year, trailer type, cast/crew, studio, distributor,
franchise, hashtags, social handles, and official links.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import base64
from backend.agents.audio_agent import AudioResult
from backend.agents.ingestion_agent import IngestionResult
from backend.agents.vision_agent import VisionResult
from backend.config import settings

logger = logging.getLogger(__name__)

METADATA_SYSTEM_PROMPT = """You are an expert at extracting structured information from YouTube movie trailer titles and descriptions. You have extensive knowledge of Indian and international film industry naming conventions, studios, and production houses.

Extract all available metadata and return it as valid JSON. Set fields to null if not found — never guess."""

METADATA_USER_TEMPLATE = """Extract structured metadata from this YouTube movie trailer.

**Title:** {title}
**Channel:** {channel}
**Upload Date:** {upload_date}
**Duration:** {duration:.0f} seconds
**Tags:** {tags}

**Audio Transcript (Whisper):**
{transcript}

**Full Description:**
{description}

Return ONLY valid JSON:
{{
  "movie_name": "clean title without 'Official Trailer', 'Teaser', etc.",
  "release_year": year as integer or null,
  "director": "director name or null",
  "main_cast": ["actor names"],
  "producers": ["producer names"],
  "production_company": "production house name or null",
  "screenwriter": "writer name or null",
  "music_composer": "music director / composer name or null",
  "studio": "studio name or null",
  "distributor": "distribution company or null",
  "trailer_type": "one of: Teaser / Official Trailer / Final Trailer / Theatrical Trailer / Lyrical Video / Motion Poster",
  "trailer_number": trailer number as integer or null,
  "version": "e.g. Hindi Dubbed / English Subtitled / IMAX / 4K or null",
  "franchise_name": "franchise / series name or null",
  "social_handles": ["@username list from description"],
  "campaign_tags": ["#hashtag list"],
  "official_links": ["https:// links mentioned"],
  "related_movies": ["similar films mentioned"],
  "keywords": ["5–10 searchable keywords"],
  "confidence": {{
    "movie_name": 0.0,
    "director": 0.0,
    "main_cast": 0.0,
    "trailer_type": 0.0
  }}
}}"""


# ── Common Indian studio/distributor names for regex fallback ─────────────────
KNOWN_STUDIOS = [
    "Yash Raj Films", "Dharma Productions", "Red Chillies", "Excel Entertainment",
    "T-Series", "Maddock Films", "Pen Studios", "Lyca Productions", "AGS Entertainment",
    "Mythri Movie Makers", "Sri Venkateswara Creations", "Hombale Films",
    "KVN Productions", "PVP Cinema", "Geetha Arts", "UV Creations",
    "Sun Pictures", "Kalaippuli S. Thanu", "Dream Warrior Pictures",
    "Paramount Pictures", "Warner Bros", "Universal Pictures", "Sony Pictures",
    "Walt Disney", "Netflix", "Amazon Prime", "Apple Original Films",
    "20th Century Studios",
]

TRAILER_TYPE_PATTERNS = [
    (r"\bteaser\b", "Teaser"),
    (r"\bofficial trailer\b", "Official Trailer"),
    (r"\bfinal trailer\b", "Final Trailer"),
    (r"\btheatrical trailer\b", "Theatrical Trailer"),
    (r"\btrailer\s*[#]?\s*(\d+)\b", "Official Trailer"),
    (r"\btrailer\b", "Official Trailer"),
    (r"\bmotion poster\b", "Motion Poster"),
    (r"\blyric(?:al)?\s+video\b", "Lyrical Video"),
]

YEAR_PATTERN = re.compile(r"\b(19[89]\d|20[012]\d)\b")
HASHTAG_PATTERN = re.compile(r"#\w+")
HANDLE_PATTERN = re.compile(r"@\w+")
URL_PATTERN = re.compile(r"https?://\S+")


@dataclass
class MetadataResult:
    movie_name: Optional[str] = None
    release_year: Optional[int] = None
    director: Optional[str] = None
    main_cast: List[str] = field(default_factory=list)
    producers: List[str] = field(default_factory=list)
    production_company: Optional[str] = None
    screenwriter: Optional[str] = None
    music_composer: Optional[str] = None
    studio: Optional[str] = None
    distributor: Optional[str] = None
    trailer_type: Optional[str] = None
    trailer_number: Optional[int] = None
    version: Optional[str] = None
    franchise_name: Optional[str] = None
    social_handles: List[str] = field(default_factory=list)
    campaign_tags: List[str] = field(default_factory=list)
    official_links: List[str] = field(default_factory=list)
    related_movies: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    confidence: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class MetadataAgent:
    """
    Extracts movie identification and distribution metadata.
    Uses GPT-4o when available, regex/heuristics always as fallback.
    """

    def __init__(self) -> None:
        self.name = "metadata"

    async def run(
        self,
        ingestion: IngestionResult,
        audio: Optional[AudioResult] = None,
        vision: Optional[VisionResult] = None,
    ) -> MetadataResult:
        result = MetadataResult()

        if settings.has_openai:
            result = await self._gpt_extract(ingestion, audio, vision, result)
        else:
            logger.warning("[Metadata] No OpenAI key — using regex extraction only")

        # Always run regex to fill gaps
        result = self._regex_extract(ingestion, result)
        return result

    # ── GPT-4o extraction ─────────────────────────────────────────────────────

    async def _gpt_extract(
        self,
        ingestion: IngestionResult,
        audio: Optional[AudioResult],
        vision: Optional[VisionResult],
        result: MetadataResult,
    ) -> MetadataResult:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openai_api_key)
            tags_str = ", ".join(ingestion.tags[:30]) if ingestion.tags else "None"
            transcript = (audio.transcript or "Not available")[:4000] if audio else "Not available"

            user_msg = METADATA_USER_TEMPLATE.format(
                title=ingestion.title,
                channel=ingestion.channel,
                upload_date=ingestion.upload_date,
                duration=ingestion.duration,
                tags=tags_str,
                transcript=transcript,
                description=(ingestion.description or "")[:4000],
            )

            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": METADATA_SYSTEM_PROMPT},
            ]

            # If vision data is available, pick the last 3 frames for credit extraction
            content: List[Dict[str, Any]] = [{"type": "text", "text": user_msg}]
            
            if ingestion.frame_paths:
                # Trailers usually have credits at the very end. 
                # Pick 3 frames from the last 15% of the video.
                last_frames = ingestion.frame_paths[-3:]
                for fp in last_frames:
                    if fp.exists():
                        b64 = _encode_image(fp)
                        if b64:
                            content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                            })
                
                if len(content) > 1:
                    logger.info(f"[Metadata] Sending {len(content)-1} frames to GPT-4o Vision for credits")
                    content.append({
                        "type": "text", 
                        "text": "\n\nI have also attached frames from the end of the trailer. Please look for 'billing blocks' or credit text on screen to extract the director, cast, producers, etc."
                    })

            messages.append({"role": "user", "content": content})

            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1024,
            )

            raw = response.choices[0].message.content or "{}"
            data = json.loads(raw)
            self._populate(result, data)
            logger.info(f"[Metadata] GPT extraction — movie: {result.movie_name}")

        except Exception as e:
            logger.error(f"[Metadata] GPT extraction failed: {e}")
            result.errors.append(str(e))

        return result

    # ── Regex / heuristic extraction ──────────────────────────────────────────

    def _regex_extract(
        self, ingestion: IngestionResult, result: MetadataResult
    ) -> MetadataResult:
        title = ingestion.title or ""
        description = ingestion.description or ""
        combined = f"{title}\n{description}"

        # Movie name from title if GPT didn't get it
        if not result.movie_name:
            result.movie_name = _clean_title(title)
            result.confidence["movie_name"] = 0.55

        # Trailer type from title
        if not result.trailer_type:
            result.trailer_type = _detect_trailer_type(title.lower())
            if result.trailer_type:
                result.confidence["trailer_type"] = 0.8

        # Trailer number
        if not result.trailer_number:
            m = re.search(r"trailer\s*[#]?\s*(\d+)", title, re.IGNORECASE)
            if m:
                result.trailer_number = int(m.group(1))

        # Release year from title or description
        if not result.release_year:
            years = YEAR_PATTERN.findall(combined)
            if years:
                result.release_year = int(years[0])

        # Hashtags
        existing_tags = set(result.campaign_tags)
        tags = HASHTAG_PATTERN.findall(combined)
        for tag in tags:
            if tag not in existing_tags:
                result.campaign_tags.append(tag)
        result.campaign_tags = result.campaign_tags[:20]

        # Social handles
        existing_handles = set(result.social_handles)
        handles = HANDLE_PATTERN.findall(description)
        for h in handles:
            if h not in existing_handles:
                result.social_handles.append(h)

        # Official links
        if not result.official_links:
            result.official_links = URL_PATTERN.findall(description)[:10]

        # Studio from known list
        if not result.studio:
            for studio in KNOWN_STUDIOS:
                if studio.lower() in combined.lower():
                    result.studio = studio
                    break

        # Keywords from tags if available
        if not result.keywords and ingestion.tags:
            result.keywords = ingestion.tags[:10]

        return result

    @staticmethod
    def _populate(result: MetadataResult, data: Dict[str, Any]) -> None:
        result.movie_name = data.get("movie_name")
        result.release_year = data.get("release_year")
        result.director = data.get("director")
        result.main_cast = data.get("main_cast") or []
        result.producers = data.get("producers") or []
        result.production_company = data.get("production_company")
        result.screenwriter = data.get("screenwriter")
        result.music_composer = data.get("music_composer")
        result.studio = data.get("studio")
        result.distributor = data.get("distributor")
        result.trailer_type = data.get("trailer_type")
        result.trailer_number = data.get("trailer_number")
        result.version = data.get("version")
        result.franchise_name = data.get("franchise_name")
        result.social_handles = data.get("social_handles") or []
        result.campaign_tags = data.get("campaign_tags") or []
        result.official_links = data.get("official_links") or []
        result.related_movies = data.get("related_movies") or []
        result.keywords = data.get("keywords") or []
        result.confidence = data.get("confidence") or {}


def _clean_title(title: str) -> str:
    """Remove trailer type suffixes from the title to get the movie name."""
    patterns = [
        r"\s*\|?\s*(Official|Theatrical|Final|Teaser)\s+(Trailer|Video|Announcement|Motion Poster).*",
        r"\s*[-|]\s*(Official|Theatrical|Final|Teaser).*",
        r"\s*#\w+",
        r"\s*\|\s*.*?$",
        r"\s*(Official\s+)?Trailer.*",
        r"\s+Teaser.*",
    ]
    cleaned = title.strip()
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned or title


def _detect_trailer_type(title_lower: str) -> Optional[str]:
    for pattern, ttype in TRAILER_TYPE_PATTERNS:
        if re.search(pattern, title_lower, re.IGNORECASE):
            return ttype
    return None


def _encode_image(image_path: Path) -> Optional[str]:
    """Encode an image file to base64 string."""
    try:
        from pathlib import Path
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"[Metadata] Image encoding failed: {e}")
        return None
