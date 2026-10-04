"""
Confidence score calculation helpers.

Confidence is modelled as a simple weighted average of signals:
  - Source reliability (API key present + data returned)
  - Data completeness (non-null, non-empty)
  - LLM-reported confidence (if available)
  - Cross-agent agreement (same value from multiple agents)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_field(
    value: Any,
    llm_confidence: Optional[float] = None,
    sources: int = 1,
    max_sources: int = 3,
) -> float:
    """
    Compute a confidence score for a single field.

    Args:
        value: The extracted value.
        llm_confidence: Confidence reported by the LLM (0–1).
        sources: Number of agents that agreed on this value.
        max_sources: Maximum possible agreeing sources.

    Returns:
        float in [0.0, 1.0]
    """
    if value is None or value == "" or value == []:
        return 0.0

    # Base score: data is present
    base = 0.5

    # Boost for LLM-reported confidence
    if llm_confidence is not None:
        base = (base + clamp(llm_confidence)) / 2

    # Boost for multi-source agreement
    source_ratio = sources / max_sources
    boost = 0.3 * source_ratio

    return clamp(base + boost)


def build_confidence_scores(
    fields: Dict[str, Any],
    llm_scores: Optional[Dict[str, float]] = None,
    agent_agreement: Optional[Dict[str, int]] = None,
) -> Dict[str, float]:
    """
    Build the top-level confidence_scores dict from all available signals.

    Args:
        fields: Dict of field_name → extracted_value.
        llm_scores: Optional LLM-reported per-field confidence.
        agent_agreement: Optional per-field count of agreeing agents.

    Returns:
        Dict[str, float] confidence_scores.
    """
    llm_scores = llm_scores or {}
    agent_agreement = agent_agreement or {}

    scores: Dict[str, float] = {}
    for name, value in fields.items():
        scores[name] = score_field(
            value=value,
            llm_confidence=llm_scores.get(name),
            sources=agent_agreement.get(name, 1),
        )
    return scores


def average_confidence(scores: Dict[str, float]) -> float:
    """Return the mean confidence across all scored fields."""
    if not scores:
        return 0.0
    return round(sum(scores.values()) / len(scores), 4)
