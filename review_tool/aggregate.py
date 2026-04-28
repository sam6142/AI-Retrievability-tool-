"""Stage 5: Pure arithmetic aggregation over classified reviews.

Defines ScoredReview (produced by scorer.py) and CorpusStats (returned here).
scorer.py imports ScoredReview from this module to avoid a shared types file
outside the spec layout.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from review_tool.classify import DIMENSIONS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

class DimensionScores(TypedDict):
    service: int
    attributes: int
    outcome: int
    occasion: int
    descriptive_depth: int


class Rationale(TypedDict):
    service: str
    attributes: str
    outcome: str
    occasion: str
    descriptive_depth: str


class _ScoredReviewRequired(TypedDict):
    review_id: str
    text: str
    labels: DimensionScores
    relevance: bool
    confidence: str
    bucket: str
    rationale: Rationale


class ScoredReview(_ScoredReviewRequired, total=False):
    rating: int | None
    date: str | None


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

class ByBucket(TypedDict):
    service_attribute_matchable: int
    trust_quality_matchable: int
    low_retrievability: int


class DimensionCoverage(TypedDict):
    service: float
    attributes: float
    outcome: float
    occasion: float
    descriptive_depth: float


class ConfidenceDistribution(TypedDict):
    high: int
    medium: int
    low: int


class CorpusStats(TypedDict):
    total_reviews: int
    by_bucket: ByBucket
    ai_visibility_pct: float
    dimension_coverage_pct: DimensionCoverage
    weakest_dimension: str
    confidence_distribution: ConfidenceDistribution


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate(scored_reviews: list[ScoredReview]) -> CorpusStats:
    """Compute corpus-level stats from a list of scored and classified reviews.

    Raises ValueError if the list is empty.
    All arithmetic — no I/O, no LLM calls.
    """
    total = len(scored_reviews)
    if total == 0:
        raise ValueError("Cannot aggregate: no scored reviews provided.")

    by_bucket: dict[str, int] = {
        "service_attribute_matchable": 0,
        "trust_quality_matchable": 0,
        "low_retrievability": 0,
    }
    dim_ge1: dict[str, int] = {d: 0 for d in DIMENSIONS}
    confidence_dist: dict[str, int] = {"high": 0, "medium": 0, "low": 0}

    for r in scored_reviews:
        bucket = r["bucket"]
        if bucket not in by_bucket:
            logger.warning("Unknown bucket value %r on review %s — counting as low_retrievability.", bucket, r.get("review_id", "?"))
            bucket = "low_retrievability"
        by_bucket[bucket] += 1

        conf = r["confidence"]
        if conf in confidence_dist:
            confidence_dist[conf] += 1
        else:
            logger.warning("Unknown confidence value %r on review %s — ignoring.", conf, r.get("review_id", "?"))

        labels = r["labels"]
        for dim in DIMENSIONS:
            if labels.get(dim, 0) >= 1:
                dim_ge1[dim] += 1

    ai_visibility_pct = round(
        (by_bucket["service_attribute_matchable"] + by_bucket["trust_quality_matchable"])
        / total
        * 100,
        1,
    )

    dim_coverage: dict[str, float] = {
        d: round(dim_ge1[d] / total * 100, 1) for d in DIMENSIONS
    }

    # Tiebreaker: DIMENSIONS order (deterministic — same order as SPEC rubric)
    weakest = min(DIMENSIONS, key=lambda d: dim_coverage[d])

    return CorpusStats(
        total_reviews=total,
        by_bucket=ByBucket(
            service_attribute_matchable=by_bucket["service_attribute_matchable"],
            trust_quality_matchable=by_bucket["trust_quality_matchable"],
            low_retrievability=by_bucket["low_retrievability"],
        ),
        ai_visibility_pct=ai_visibility_pct,
        dimension_coverage_pct=DimensionCoverage(
            service=dim_coverage["service"],
            attributes=dim_coverage["attributes"],
            outcome=dim_coverage["outcome"],
            occasion=dim_coverage["occasion"],
            descriptive_depth=dim_coverage["descriptive_depth"],
        ),
        weakest_dimension=weakest,
        confidence_distribution=ConfidenceDistribution(
            high=confidence_dist["high"],
            medium=confidence_dist["medium"],
            low=confidence_dist["low"],
        ),
    )
