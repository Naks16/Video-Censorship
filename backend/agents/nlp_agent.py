"""
NLP Agent — Uses GPT-4o (or falls back to heuristics when no API key) to
analyze the transcript and YouTube description and extract content descriptors:
genre, subgenre, plot summary, themes, tone, age rating, content warnings,
target audience, and country of origin.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.agents.audio_agent import AudioResult
from backend.agents.ingestion_agent import IngestionResult
from backend.agents.vision_agent import VisionResult
from backend.config import settings

logger = logging.getLogger(__name__)

NLP_SYSTEM_PROMPT = """You are an expert film critic and metadata analyst specializing in Indian and international cinema, with deep knowledge of Bollywood, Tollywood, Kollywood, Mollywood, Sandalwood, and other regional Indian film industries.

Your task is to analyze movie trailer information (title, description, transcript, and detected visual scenes) and return structured metadata as valid JSON.

Be accurate, culturally sensitive, and specific. If data is insufficient for a field, set it to null.
Confidence scores should reflect how certain you are based on available evidence (0.0–1.0)."""

NLP_USER_TEMPLATE = """Analyze the following movie trailer and extract structured metadata.

**YouTube Title:** {title}

**YouTube Description:**
{description}

**Audio Transcript (from Whisper):**
{transcript}

**Detected Visual Scenes (from CLIP):**
{scenes}

**Detected Spoken Language:** {language}

Return ONLY a valid JSON object with this exact structure:
{{
  "genres": ["list of 1–4 genres from: Action, Drama, Thriller, Romance, Comedy, Horror, Sci-Fi, Fantasy, Biography, Documentary, Historical, Musical, Mystery, Adventure, Crime, Superhero, Mythological, Sports, Political"],
  "subgenre": "most specific subgenre (e.g., 'Romantic Thriller', 'Period Drama', 'Family Comedy')",
  "plot_summary": "2–3 sentence summary based on trailer content",
  "themes": ["3–5 major thematic elements e.g. 'revenge', 'family bonds', 'corruption', 'love triangle'"],
  "tone": "overall tone: Dark / Intense / Uplifting / Romantic / Comedic / Suspenseful / Epic",
  "age_rating": "most appropriate: U / U/A / A / PG / PG-13 / R (use Indian CBFC ratings for Indian films)",
  "content_warnings": ["applicable warnings: Violence, Strong Language, Sexual Content, Drug Use, etc."],
  "target_audience": "description of primary audience (e.g., 'Young adults 18–35, fans of action films')",
  "country_of_origin": "most likely country",
  "confidence": {{
    "genres": 0.0,
    "plot_summary": 0.0,
    "themes": 0.0,
    "age_rating": 0.0,
    "tone": 0.0
  }}
}}"""


@dataclass
class NLPResult:
    genres: List[str] = field(default_factory=list)
    subgenre: Optional[str] = None
    plot_summary: Optional[str] = None
    themes: List[str] = field(default_factory=list)
    tone: Optional[str] = None
    age_rating: Optional[str] = None
    content_warnings: List[str] = field(default_factory=list)
    target_audience: Optional[str] = None
    country_of_origin: Optional[str] = None
    confidence: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class NLPAgent:
    """
    Sends transcript + description to GPT-4o for content classification.
    Falls back to heuristic genre detection when no API key is available.
    """

    def __init__(self) -> None:
        self.name = "nlp"

    async def run(
        self,
        ingestion: IngestionResult,
        audio: AudioResult,
        vision: VisionResult,
    ) -> NLPResult:
        result = NLPResult()

        scenes_str = ", ".join(
            f"{s['scene']} ({s['confidence']:.0%})" for s in vision.top_scenes
        ) or "Not detected"

        # Truncate transcript and description to fit context window
        transcript = (audio.transcript or "")[:4000]
        description = (ingestion.description or "")[:3000]

        if settings.has_openai:
            result = await self._gpt_extract(
                ingestion.title, description, transcript, scenes_str,
                audio.language, result
            )
        else:
            logger.warning("[NLP] No OpenAI API key — using heuristic extraction")
            result = self._heuristic_extract(
                ingestion.title, description, transcript, audio.language, result
            )

        return result

    # ── GPT-4o extraction ─────────────────────────────────────────────────────

    async def _gpt_extract(
        self,
        title: str,
        description: str,
        transcript: str,
        scenes: str,
        language: str,
        result: NLPResult,
    ) -> NLPResult:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openai_api_key)

            user_msg = NLP_USER_TEMPLATE.format(
                title=title,
                description=description or "Not available",
                transcript=transcript or "Not available",
                scenes=scenes,
                language=language or "Unknown",
            )

            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": NLP_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=1024,
            )

            raw = response.choices[0].message.content or "{}"
            data = json.loads(raw)
            self._populate(result, data)
            logger.info(f"[NLP] GPT extraction complete — genres: {result.genres}")

        except Exception as e:
            logger.error(f"[NLP] GPT extraction failed: {e}")
            result.errors.append(str(e))
            # Fall back to heuristics
            result = self._heuristic_extract("", "", transcript, language, result)

        return result

    # ── Heuristic fallback ────────────────────────────────────────────────────

    def _heuristic_extract(
        self,
        title: str,
        description: str,
        transcript: str,
        language: str,
        result: NLPResult,
    ) -> NLPResult:
        text = f"{title} {description} {transcript}".lower()

        genre_keywords: Dict[str, List[str]] = {
            "Action": ["action", "fight", "blast", "war", "combat", "battle", "explosion"],
            "Romance": ["love", "romance", "pyaar", "ishq", "kadhal", "prema"],
            "Thriller": ["thriller", "suspense", "mystery", "dark", "intense"],
            "Drama": ["drama", "emotion", "struggle", "family", "life"],
            "Comedy": ["comedy", "funny", "fun", "laugh", "hilarious", "padam"],
            "Horror": ["horror", "scary", "terror", "ghost", "haunted"],
            "Crime": ["crime", "police", "detective", "murder", "criminal"],
            "Musical": ["song", "music", "dance", "singer"],
            "Biographical": ["biopic", "life story", "real story", "based on"],
        }

        for genre, keywords in genre_keywords.items():
            if any(kw in text for kw in keywords):
                result.genres.append(genre)

        if not result.genres:
            result.genres = ["Drama"]

        # Age rating heuristic
        if any(w in text for w in ["violence", "blood", "adult", "mature"]):
            result.age_rating = "U/A"
        elif any(w in text for w in ["family", "kids", "children"]):
            result.age_rating = "U"
        else:
            result.age_rating = "U/A"

        result.confidence = {
            "genres": 0.45,
            "plot_summary": 0.0,
            "themes": 0.3,
            "age_rating": 0.4,
            "tone": 0.3,
        }
        result.errors.append("Heuristic extraction used — OpenAI API key not configured")
        return result

    @staticmethod
    def _populate(result: NLPResult, data: Dict[str, Any]) -> None:
        result.genres = data.get("genres") or []
        result.subgenre = data.get("subgenre")
        result.plot_summary = data.get("plot_summary")
        result.themes = data.get("themes") or []
        result.tone = data.get("tone")
        result.age_rating = data.get("age_rating")
        result.content_warnings = data.get("content_warnings") or []
        result.target_audience = data.get("target_audience")
        result.country_of_origin = data.get("country_of_origin")
        result.confidence = data.get("confidence") or {}
