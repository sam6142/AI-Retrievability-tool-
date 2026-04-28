"""Stage 4: Deterministic bucket assignment from dimension labels.

This module is the SINGLE source of truth for the bucket rule (SPEC.md §7, Stage 4).
Do not duplicate the logic — import bucket_from_labels() everywhere it is needed.
"""

from __future__ import annotations

BUCKETS = (
    "service_attribute_matchable",
    "trust_quality_matchable",
    "low_retrievability",
)

DIMENSIONS = ("service", "attributes", "outcome", "occasion", "descriptive_depth")


def bucket_from_labels(labels: dict[str, int], relevance: bool = True) -> str:
    """Return the retrieval bucket for a single review.

    Off-topic reviews (relevance=False) always map to low_retrievability regardless
    of dimension scores. Otherwise the locked bucket rule from SPEC.md applies:

        service≥2 OR attributes≥2  →  service_attribute_matchable
        elif descriptive_depth≥1   →  trust_quality_matchable
        else                       →  low_retrievability
    """
    if not relevance:
        return "low_retrievability"
    if labels.get("service", 0) >= 2 or labels.get("attributes", 0) >= 2:
        return "service_attribute_matchable"
    if labels.get("descriptive_depth", 0) >= 1:
        return "trust_quality_matchable"
    return "low_retrievability"
