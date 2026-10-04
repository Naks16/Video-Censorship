"""
Pydantic v2 schemas for the full metadata output and API contracts.
Each metadata category is its own model for clean separation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Category sub-models
# ─────────────────────────────────────────────────────────────────────────────

class BasicIdentification(BaseModel):
    trailer_title: Optional[str] = None
    movie_name: Optional[str] = None
    release_year: Optional[int] = None
    languages: List[str] = []
    country_of_origin: Optional[str] = None


class CreativeCredits(BaseModel):
    director: Optional[str] = None
    main_cast: List[str] = []
    producers: List[str] = []
    production_company: Optional[str] = None
    screenwriter: Optional[str] = None
    music_composer: Optional[str] = None


class ContentDescriptors(BaseModel):
    genres: List[str] = []
    subgenre: Optional[str] = None
    plot_summary: Optional[str] = None
    themes: List[str] = []
    tone: Optional[str] = None


class TrailerSpecific(BaseModel):
    trailer_type: Optional[str] = None      # Teaser | Official Trailer | Final Trailer
    trailer_number: Optional[int] = None
    duration: Optional[float] = None        # seconds
    trailer_release_date: Optional[str] = None
    version: Optional[str] = None           # Dubbed | Subtitled | IMAX


class TechnicalMetadata(BaseModel):
    resolution: Optional[str] = None
    aspect_ratio: Optional[str] = None
    frame_rate: Optional[float] = None
    audio_format: Optional[str] = None
    file_format: Optional[str] = None


class SearchDiscovery(BaseModel):
    keywords: List[str] = []
    hashtags: List[str] = []
    franchise_name: Optional[str] = None
    related_movies: List[str] = []


class AudienceClassification(BaseModel):
    age_rating: Optional[str] = None        # U | U/A | A | PG-13 | R
    content_warnings: List[str] = []
    target_audience: Optional[str] = None


class DistributionMarketing(BaseModel):
    studio: Optional[str] = None
    distributor: Optional[str] = None
    official_links: List[str] = []
    social_handles: List[str] = []
    campaign_tags: List[str] = []


class EngagementMetadata(BaseModel):
    thumbnail_url: Optional[str] = None
    description: Optional[str] = None
    captions: Optional[str] = None
    upload_date: Optional[str] = None
    views: Optional[int] = None
    likes: Optional[int] = None


# ─────────────────────────────────────────────────────────────────────────────
# Supporting models
# ─────────────────────────────────────────────────────────────────────────────

class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class SceneDetection(BaseModel):
    scene_type: str
    confidence: float
    timestamp: Optional[float] = None


class TrailerScore(BaseModel):
    """Bonus: engagement-potential ranking."""
    overall_score: float = 0.0          # 0–100
    excitement_score: float = 0.0
    clarity_score: float = 0.0
    emotional_impact: float = 0.0
    production_quality: float = 0.0
    score_explanation: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Root output model
# ─────────────────────────────────────────────────────────────────────────────

class TrailerMetadata(BaseModel):
    task_id: str
    youtube_url: str

    basic_identification: BasicIdentification = Field(
        default_factory=BasicIdentification
    )
    creative_credits: CreativeCredits = Field(default_factory=CreativeCredits)
    content_descriptors: ContentDescriptors = Field(
        default_factory=ContentDescriptors
    )
    trailer_specific: TrailerSpecific = Field(default_factory=TrailerSpecific)
    technical_metadata: TechnicalMetadata = Field(
        default_factory=TechnicalMetadata
    )
    search_discovery: SearchDiscovery = Field(default_factory=SearchDiscovery)
    audience_classification: AudienceClassification = Field(
        default_factory=AudienceClassification
    )
    distribution_marketing: DistributionMarketing = Field(
        default_factory=DistributionMarketing
    )
    engagement_metadata: EngagementMetadata = Field(
        default_factory=EngagementMetadata
    )

    transcript_segments: List[TranscriptSegment] = []
    detected_scenes: List[SceneDetection] = []
    trailer_score: Optional[TrailerScore] = None
    moderation: Optional[ModerationResult] = None
    confidence_scores: Dict[str, float] = {}
    processing_time_seconds: float = 0.0
    errors: List[str] = []


# ─────────────────────────────────────────────────────────────────────────────
# API request / response models
# ─────────────────────────────────────────────────────────────────────────────

class ExtractionRequest(BaseModel):
    url: str = Field(..., description="YouTube trailer URL")


class BatchExtractionRequest(BaseModel):
    urls: List[str] = Field(..., description="List of YouTube trailer URLs")


class TaskStatus(BaseModel):
    task_id: str
    status: str     # pending | processing | completed | failed
    current_stage: Optional[str] = None
    progress: int = 0   # 0–100
    error: Optional[str] = None


class AnalyticsResponse(BaseModel):
    total_processed: int = 0
    genre_distribution: Dict[str, int] = {}
    language_distribution: Dict[str, int] = {}
    avg_confidence: Dict[str, float] = {}
    trailer_type_breakdown: Dict[str, int] = {}
    moderation_stats: Dict[str, int] = Field(default_factory=lambda: {"low": 0, "medium": 0, "high": 0})



class ModerationResult(BaseModel):
    explicit_content: bool
    sexually_explicit_content: bool
    nudity_score: float
    violence_score: float
    abusive_language: bool
    audio_abusive_language: bool = False
    audio_sexual_content: bool = False
    audio_threats: bool = False
    severity: str  # low | medium | high
    summary: str

