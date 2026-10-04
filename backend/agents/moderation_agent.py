"""
Moderation Agent — Analyzes video frames and audio transcripts for safety.
Uses GPT-4o Vision for visual content and GPT-4o for audio text analysis.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from backend.agents.audio_agent import AudioResult
from backend.agents.ingestion_agent import IngestionResult
from backend.config import settings
from backend.models.schemas import ModerationResult
from backend.utils.file_utils import encode_image_to_base64

logger = logging.getLogger(__name__)

MODERATION_SYSTEM_PROMPT = """You are a STRICT and UNBIASED content moderator for a global media ratings board.
Your job is to identify ANY safety violations, offensive language, or explicit content.
You MUST flag all profanity, slurs, and insults, regardless of artistic context or intended meaning.
Be extremely literal: if an offensive word exists in the transcript, it is a violation.
Return your analysis in valid JSON format."""


MODERATION_VISUAL_PROMPT = """Analyze these frames from a video for content safety.
For each frame, assess:
1. Nudity (0-1 score, where 0 is none and 1 is full nudity)
2. Sexually Explicit Content (0-1 score, where 0 is none, 0.3-0.5 is mild like kissing, and 1 is explicit sexual acts)
3. Violence (0-1 score, where 0 is none and 1 is extreme violence/blood)
4. Safe/Unsafe (boolean: true if safe, false if unsafe. Kissing is considered "Safe" but should have a mild score)


Return the maximum scores and a general safety assessment for the entire set of frames.
Return JSON:
{{
  "nudity_max": float,
  "sexually_explicit_max": float,
  "violence_max": float,
  "visual_safe": boolean,
  "visual_summary": "string"
}}"""


MODERATION_AUDIO_PROMPT = """Analyze this audio transcript for content safety.
Transcript: {transcript}

CRITICAL INSTRUCTIONS:
1. Scan the entire transcript for profanity, slurs, swear words, and insults.
2. If ANY such words are found, set "abusive_language" to true.
3. Be extremely strict. Do not ignore "mild" swear words.
4. In "audio_summary", explicitly list the offensive words found.

Assess:
1. Abusive language (ANY profanity, slurs, or insults)
2. Sexual content (explicit descriptions, verbal harassment)
3. Threats (violence, self-harm, hate speech)

Return JSON:
{{
  "abusive_language": boolean,
  "sexual_content": boolean,
  "threats": boolean,
  "audio_safe": boolean,
  "audio_summary": "string listing offensive words and explaining the violation"
}}"""



# A basic list of common profanity/slurs for the safety net (English + common transliterated Hindi)
EXPLICIT_WORDS = [
    r"\bfuck\w*\b", r"\bshit\w*\b", r"\bbitch\w*\b", r"\basshole\b", r"\bcunt\b",
    r"\bchutiya\w*\b", r"\bgandu\b", r"\bbehenchod\b", r"\bmadarchod\b", r"\blauda\b",
    r"\bharaami\b", r"\bsala\b", r"\bgaand\b"
]


class ModerationAgent:
    """
    Analyzes video and audio for explicit content, nudity, violence, and abusive language.
    """

    def __init__(self) -> None:
        self.name = "moderation"

    async def run(
        self, 
        ingestion: IngestionResult, 
        audio: AudioResult
    ) -> ModerationResult:
        """
        Runs the full moderation analysis on frames and transcript.
        """
        logger.info("[Moderation] Starting analysis...")
        
        visual_data = await self._analyze_visual(ingestion.frame_paths)
        audio_data = await self._analyze_audio(audio.transcript)
        
        # Aggregate results
        nudity_score = visual_data.get("nudity_max", 0.0)
        sexually_explicit_score = visual_data.get("sexually_explicit_max", 0.0)
        violence_score = visual_data.get("violence_max", 0.0)
        
        abusive_language_llm = audio_data.get("abusive_language", False)
        sexual_audio = audio_data.get("sexual_content", False)
        threats_audio = audio_data.get("threats", False)
        
        # Regex safety net
        abusive_language_regex = self._contains_explicit_profanity(audio.transcript)
        abusive_language = abusive_language_llm or abusive_language_regex
        
        if abusive_language_regex and not abusive_language_llm:
            logger.info("[Moderation] Regex caught abusive language that LLM missed.")

        
        # Final decision logic
        explicit_content = (
            nudity_score > 0.5 or 
            sexually_explicit_score > 0.3 or 
            sexual_audio or 
            not visual_data.get("visual_safe", True)
        )
        
        sexually_explicit_content = (
            sexually_explicit_score > 0.3 or 
            sexual_audio
        )
        
        # Severity calculation
        max_score = max(nudity_score, sexually_explicit_score, violence_score)
        if max_score > 0.8 or threats_audio:
            severity = "high"
        elif max_score >= 0.3 or abusive_language or sexual_audio:
            severity = "medium"
        else:
            severity = "low"

            
        summary = f"Visual: {visual_data.get('visual_summary')}. Audio: {audio_data.get('audio_summary')}."
        if abusive_language_regex and "abusive" not in summary.lower():
             summary += " (Note: Regex-based safety net detected explicit language)."

        
        return ModerationResult(
            explicit_content=explicit_content,
            sexually_explicit_content=sexually_explicit_content,
            nudity_score=nudity_score,
            violence_score=violence_score,
            abusive_language=abusive_language,
            audio_abusive_language=abusive_language,
            audio_sexual_content=sexual_audio,
            audio_threats=threats_audio,
            severity=severity,
            summary=summary
        )

    async def _analyze_visual(self, frame_paths: List[Path]) -> Dict[str, Any]:
        """Send frames to GPT-4o Vision for safety analysis."""
        if not settings.has_openai or not frame_paths:
            return {"nudity_max": 0.0, "sexually_explicit_max": 0.0, "violence_max": 0.0, "visual_safe": True, "visual_summary": "No visual analysis performed."}

        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            
            # Sample frames (max 10 to keep within token/latency limits)
            sampled = frame_paths[::max(1, len(frame_paths) // 10)][:10]
            
            content: List[Dict[str, Any]] = [{"type": "text", "text": MODERATION_VISUAL_PROMPT}]
            
            for fp in sampled:
                if fp.exists():
                    b64 = encode_image_to_base64(fp)
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                    })

            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": MODERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": content}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=500
            )
            
            res_content = response.choices[0].message.content or "{}"
            # Strip markdown code blocks if present
            if "```json" in res_content:
                res_content = res_content.split("```json")[1].split("```")[0].strip()
            elif "```" in res_content:
                res_content = res_content.split("```")[1].split("```")[0].strip()
            
            return json.loads(res_content)
        except Exception as e:
            raw_res = response.choices[0].message.content if 'response' in locals() else 'N/A'
            logger.error(f"[Moderation] Visual AI JSON Parsing Failed. Error: {type(e).__name__}: {e}")
            logger.error(f"[Moderation] Raw Visual AI Content: {raw_res}")
            return {"nudity_max": 0.0, "sexually_explicit_max": 0.0, "violence_max": 0.0, "visual_safe": True, "visual_summary": f"AI Parsing Error: {e}"}



    async def _analyze_audio(self, transcript: str) -> Dict[str, Any]:
        """Send transcript to LLM for safety analysis."""
        if not settings.has_openai or not transcript:
            return {"abusive_language": False, "sexual_content": False, "threats": False, "audio_safe": True, "audio_summary": "No audio analysis performed."}

        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": MODERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": MODERATION_AUDIO_PROMPT.format(transcript=transcript[:6000])}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=500
            )
            
            res_content = response.choices[0].message.content or "{}"
            # Strip markdown code blocks if present
            if "```json" in res_content:
                res_content = res_content.split("```json")[1].split("```")[0].strip()
            elif "```" in res_content:
                res_content = res_content.split("```")[1].split("```")[0].strip()

            return json.loads(res_content)
        except Exception as e:
            raw_res = response.choices[0].message.content if 'response' in locals() else 'N/A'
            logger.error(f"[Moderation] Audio AI JSON Parsing Failed. Error: {type(e).__name__}: {e}")
            logger.error(f"[Moderation] Raw Audio AI Content: {raw_res}")
            return {"abusive_language": False, "sexual_content": False, "threats": False, "audio_safe": True, "audio_summary": f"AI Parsing Error: {e}"}



    def _contains_explicit_profanity(self, transcript: str) -> bool:
        """Fallback regex check for common slurs/profanity."""
        import re
        if not transcript:
            return False
        
        combined_pattern = "|".join(EXPLICIT_WORDS)
        return bool(re.search(combined_pattern, transcript, re.IGNORECASE))

