"""
Aggregator Agent — Merges outputs from all 5 agents into the final
TrailerMetadata schema. Resolves conflicts, removes duplicates, and
computes aggregate confidence scores.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.agents.audio_agent import AudioResult
from backend.agents.ingestion_agent import IngestionResult
from backend.agents.metadata_agent import MetadataResult
from backend.agents.moderation_agent import ModerationResult as ModerationAgentResult
from backend.agents.nlp_agent import NLPResult
from backend.agents.vision_agent import VisionResult
from backend.models.schemas import (
    AudienceClassification,
    BasicIdentification,
    ContentDescriptors,
    CreativeCredits,
    DistributionMarketing,
    EngagementMetadata,
    SceneDetection,
    SearchDiscovery,
    TechnicalMetadata,
    TrailerMetadata,
    TrailerScore,
    TrailerSpecific,
    TranscriptSegment,
    ModerationResult,
)
from backend.utils.confidence import build_confidence_scores

logger = logging.getLogger(__name__)


class AggregatorAgent:
    """
    Combines all agent results and normalizes into the TrailerMetadata schema.
    Applies priority rules where agents may disagree:
        language:    Whisper > YouTube API > LLM inference > yt-dlp tags
        movie_name:  LLM (metadata_agent) > cleaned title
        genre:       LLM (nlp_agent) > heuristic
        year:        metadata_agent > regex > description year
    """

    def __init__(self) -> None:
        self.name = "aggregator"

    def run(
        self,
        task_id: str,
        url: str,
        ingestion: IngestionResult,
        audio: AudioResult,
        vision: VisionResult,
        nlp: NLPResult,
        metadata: MetadataResult,
        moderation: Optional[ModerationResult],
        start_time: float,
    ) -> TrailerMetadata:
        logger.info(f"[Aggregator] Building final metadata for task {task_id}")

        result = TrailerMetadata(task_id=task_id, youtube_url=url)

        # ── 1. Basic Identification ───────────────────────────────────────────
        result.basic_identification = BasicIdentification(
            trailer_title=ingestion.title or None,
            movie_name=metadata.movie_name,
            release_year=metadata.release_year,
            languages=self._resolve_languages(audio, ingestion),
            country_of_origin=nlp.country_of_origin,
        )

        # ── 2. Creative Credits ───────────────────────────────────────────────
        result.creative_credits = CreativeCredits(
            director=metadata.director,
            main_cast=_dedup(metadata.main_cast),
            producers=_dedup(metadata.producers),
            production_company=metadata.production_company,
            screenwriter=metadata.screenwriter,
            music_composer=metadata.music_composer,
        )

        # ── 3. Content Descriptors ────────────────────────────────────────────
        result.content_descriptors = ContentDescriptors(
            genres=_dedup(nlp.genres),
            subgenre=nlp.subgenre,
            plot_summary=nlp.plot_summary,
            themes=_dedup(nlp.themes),
            tone=nlp.tone,
        )

        # ── 4. Trailer-Specific ───────────────────────────────────────────────
        result.trailer_specific = TrailerSpecific(
            trailer_type=metadata.trailer_type,
            trailer_number=metadata.trailer_number,
            duration=ingestion.duration or None,
            trailer_release_date=ingestion.upload_date or None,
            version=metadata.version,
        )

        # ── 5. Technical Metadata ─────────────────────────────────────────────
        result.technical_metadata = TechnicalMetadata(
            resolution=ingestion.resolution or None,
            aspect_ratio=ingestion.aspect_ratio or None,
            frame_rate=ingestion.frame_rate or None,
            audio_format=ingestion.audio_codec or None,
            file_format=ingestion.file_format or None,
        )

        # ── 6. Search & Discovery ─────────────────────────────────────────────
        all_keywords = _dedup(
            metadata.keywords + ingestion.tags[:15]
        )
        result.search_discovery = SearchDiscovery(
            keywords=all_keywords[:20],
            hashtags=_dedup(metadata.campaign_tags)[:15],
            franchise_name=metadata.franchise_name,
            related_movies=_dedup(metadata.related_movies),
        )

        # ── 7. Audience & Classification ─────────────────────────────────────
        result.audience_classification = AudienceClassification(
            age_rating=nlp.age_rating,
            content_warnings=_dedup(nlp.content_warnings),
            target_audience=nlp.target_audience,
        )

        # ── 8. Distribution & Marketing ───────────────────────────────────────
        result.distribution_marketing = DistributionMarketing(
            studio=metadata.studio,
            distributor=metadata.distributor,
            official_links=_dedup(metadata.official_links)[:5],
            social_handles=_dedup(metadata.social_handles)[:10],
            campaign_tags=_dedup(metadata.campaign_tags)[:10],
        )

        # ── 9. Engagement Metadata ────────────────────────────────────────────
        result.engagement_metadata = EngagementMetadata(
            thumbnail_url=ingestion.thumbnail_url or None,
            description=ingestion.description or None,
            captions=ingestion.captions,
            upload_date=ingestion.upload_date or None,
            views=ingestion.views or None,
            likes=ingestion.likes or None,
        )

        # ── Transcript Segments ───────────────────────────────────────────────
        result.transcript_segments = [
            TranscriptSegment(
                start=seg["start"], end=seg["end"], text=seg["text"]
            )
            for seg in audio.segments[:50]  # cap at 50 segments
        ]

        # ── Scene Detections ──────────────────────────────────────────────────
        result.detected_scenes = [
            SceneDetection(
                scene_type=scene["scene"], confidence=scene["confidence"]
            )
            for scene in vision.top_scenes
        ]

        # ── Confidence Scores ─────────────────────────────────────────────────
        result.confidence_scores = self._build_confidence(
            ingestion, audio, vision, nlp, metadata
        )

        # ── Trailer Score (bonus) ─────────────────────────────────────────────
        result.trailer_score = self._compute_trailer_score(
            ingestion, audio, vision, nlp
        )

        # ── Moderation Result ─────────────────────────────────────────────────
        result.moderation = moderation

        # ── Errors ───────────────────────────────────────────────────────────
        all_errors = (
            ingestion.errors + audio.errors + vision.errors
            + nlp.errors + metadata.errors
        )
        result.errors = list(dict.fromkeys(all_errors))  # unique, preserve order

        result.processing_time_seconds = round(time.time() - start_time, 2)
        logger.info(
            f"[Aggregator] Done — confidence avg: "
            f"{sum(result.confidence_scores.values()) / max(len(result.confidence_scores), 1):.2f}"
        )
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_languages(
        audio: AudioResult, ingestion: IngestionResult
    ) -> List[str]:
        """Priority: Whisper detection > yt-dlp tags."""
        langs = list(dict.fromkeys(audio.detected_languages))
        if not langs and audio.language:
            langs = [audio.language]
        # Supplement from yt-dlp if still empty
        if not langs and ingestion.tags:
            lang_tags = [
                t.capitalize()
                for t in ingestion.tags
                if t.lower() in {
                    "hindi", "tamil", "telugu", "malayalam", "kannada",
                    "marathi", "gujarati", "punjabi", "bengali", "english",
                }
            ]
            langs = lang_tags[:3]
        return langs or []

    @staticmethod
    def _build_confidence(
        ingestion: IngestionResult,
        audio: AudioResult,
        vision: VisionResult,
        nlp: NLPResult,
        metadata: MetadataResult,
    ) -> Dict[str, float]:
        scores: Dict[str, float] = {}

        # Language confidence from Whisper
        scores["language"] = round(audio.language_confidence, 4)
        scores["transcript"] = round(audio.transcription_confidence, 4)

        # NLP confidence
        for k, v in (nlp.confidence or {}).items():
            scores[k] = round(float(v), 4)

        # Metadata confidence
        for k, v in (metadata.confidence or {}).items():
            if k not in scores:
                scores[k] = round(float(v), 4)

        # Vision confidence
        scores["scene_detection"] = round(vision.overall_confidence, 4)

        # Engagement data confidence (data directly from API/yt-dlp)
        scores["engagement"] = 0.95 if ingestion.views else 0.5

        return {k: v for k, v in scores.items() if v > 0}

    @staticmethod
    def _compute_trailer_score(
        ingestion: IngestionResult,
        audio: AudioResult,
        vision: VisionResult,
        nlp: NLPResult,
    ) -> TrailerScore:
        """
        Compute engagement-potential score (0–100).
        Factors: views/likes ratio, transcript richness, scene variety,
                 genre excitement, audio confidence.
        """
        excitement = 0.0
        clarity = 0.0
        emotional = 0.0
        quality = 0.0

        # Excitement: action scenes detected
        action_scenes = [
            s for s in vision.top_scenes
            if any(kw in s["scene"].lower() for kw in ["action", "fight", "chase", "battle"])
        ]
        excitement = min(1.0, len(action_scenes) * 0.25 + vision.overall_confidence * 0.5)

        # Clarity: transcript length + confidence
        if audio.transcript:
            word_count = len(audio.transcript.split())
            clarity = min(1.0, word_count / 200) * 0.6 + audio.transcription_confidence * 0.4

        # Emotional: genre mix
        emotional_genres = {"Drama", "Romance", "Thriller", "Horror"}
        overlap = len(set(nlp.genres) & emotional_genres)
        emotional = min(1.0, overlap * 0.3 + (0.5 if nlp.tone else 0.0))

        # Production quality: video resolution
        quality = 0.7
        if ingestion.resolution:
            h = int(ingestion.resolution.split("x")[-1]) if "x" in ingestion.resolution else 0
            quality = min(1.0, h / 1080) * 0.8 + 0.2

        overall = (excitement + clarity + emotional + quality) / 4

        return TrailerScore(
            overall_score=round(overall * 100, 1),
            excitement_score=round(excitement * 100, 1),
            clarity_score=round(clarity * 100, 1),
            emotional_impact=round(emotional * 100, 1),
            production_quality=round(quality * 100, 1),
            score_explanation=(
                f"Score based on {len(vision.top_scenes)} detected scenes, "
                f"{'rich' if clarity > 0.5 else 'limited'} transcript, "
                f"and {ingestion.resolution or 'unknown'} resolution."
            ),
        )


def _dedup(items: List[Any]) -> List[Any]:
    """Remove duplicates while preserving order."""
    seen = set()
    result = []
    for item in items:
        key = str(item).lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result
