"""Tests for review_tool.aggregate — pure arithmetic over classified reviews."""

from __future__ import annotations

import pytest

from review_tool.aggregate import aggregate
from review_tool.classify import DIMENSIONS

# ---------------------------------------------------------------------------
# Error / guard cases
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_empty_list_raises() -> None:
    with pytest.raises(ValueError, match="no scored reviews"):
        aggregate([])


# ---------------------------------------------------------------------------
# Single-review corpus
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_single_review_bucket1(make_scored_review) -> None:
    stats = aggregate([make_scored_review("service_attribute_matchable", "high", service=2, depth=1, rid="r_001")])
    assert stats["total_reviews"] == 1
    assert stats["by_bucket"]["service_attribute_matchable"] == 1
    assert stats["by_bucket"]["trust_quality_matchable"] == 0
    assert stats["by_bucket"]["low_retrievability"] == 0
    assert stats["ai_visibility_pct"] == 100.0


@pytest.mark.fast
def test_single_review_bucket2(make_scored_review) -> None:
    stats = aggregate([make_scored_review("trust_quality_matchable", "medium", depth=1, rid="r_001")])
    assert stats["by_bucket"]["trust_quality_matchable"] == 1
    assert stats["ai_visibility_pct"] == 100.0


@pytest.mark.fast
def test_single_review_bucket3(make_scored_review) -> None:
    stats = aggregate([make_scored_review("low_retrievability", "low", rid="r_001")])
    assert stats["by_bucket"]["low_retrievability"] == 1
    assert stats["ai_visibility_pct"] == 0.0


# ---------------------------------------------------------------------------
# Homogeneous corpora
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_all_bucket1_corpus(make_scored_review) -> None:
    reviews = [
        make_scored_review("service_attribute_matchable", "high", service=2, rid=f"r_{i:03d}")
        for i in range(1, 6)
    ]
    stats = aggregate(reviews)
    assert stats["total_reviews"] == 5
    assert stats["by_bucket"]["service_attribute_matchable"] == 5
    assert stats["by_bucket"]["trust_quality_matchable"] == 0
    assert stats["by_bucket"]["low_retrievability"] == 0
    assert stats["ai_visibility_pct"] == 100.0


@pytest.mark.fast
def test_all_bucket3_corpus(make_scored_review) -> None:
    reviews = [
        make_scored_review("low_retrievability", "low", rid=f"r_{i:03d}")
        for i in range(1, 6)
    ]
    stats = aggregate(reviews)
    assert stats["total_reviews"] == 5
    assert stats["by_bucket"]["service_attribute_matchable"] == 0
    assert stats["by_bucket"]["trust_quality_matchable"] == 0
    assert stats["by_bucket"]["low_retrievability"] == 5
    assert stats["ai_visibility_pct"] == 0.0


# ---------------------------------------------------------------------------
# Mixed corpus — arithmetic verification
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_mixed_bucket_counts(make_scored_review) -> None:
    reviews = [
        make_scored_review("service_attribute_matchable", "high", service=2, rid="r_001"),
        make_scored_review("service_attribute_matchable", "high", service=2, rid="r_002"),
        make_scored_review("trust_quality_matchable",     "medium", depth=1, rid="r_003"),
        make_scored_review("low_retrievability",          "low",             rid="r_004"),
        make_scored_review("low_retrievability",          "high",            rid="r_005"),
    ]
    stats = aggregate(reviews)
    assert stats["total_reviews"] == 5
    assert stats["by_bucket"]["service_attribute_matchable"] == 2
    assert stats["by_bucket"]["trust_quality_matchable"] == 1
    assert stats["by_bucket"]["low_retrievability"] == 2


@pytest.mark.fast
def test_ai_visibility_pct_formula(make_scored_review) -> None:
    # 2 bucket-1 + 1 bucket-2 out of 5 total → (3/5)*100 = 60.0
    reviews = [
        make_scored_review("service_attribute_matchable", "high", service=2, rid="r_001"),
        make_scored_review("service_attribute_matchable", "high", service=2, rid="r_002"),
        make_scored_review("trust_quality_matchable",     "high", depth=1,   rid="r_003"),
        make_scored_review("low_retrievability",          "high",            rid="r_004"),
        make_scored_review("low_retrievability",          "high",            rid="r_005"),
    ]
    stats = aggregate(reviews)
    expected_pct = round((2 + 1) / 5 * 100, 1)
    assert stats["ai_visibility_pct"] == expected_pct


@pytest.mark.fast
def test_ai_visibility_pct_zero_when_all_bucket3(make_scored_review) -> None:
    reviews = [make_scored_review("low_retrievability", "high", rid=f"r_{i:03d}") for i in range(1, 4)]
    assert aggregate(reviews)["ai_visibility_pct"] == 0.0


@pytest.mark.fast
def test_ai_visibility_pct_100_when_no_bucket3(make_scored_review) -> None:
    reviews = [
        make_scored_review("service_attribute_matchable", "high", service=2, rid="r_001"),
        make_scored_review("trust_quality_matchable",     "high", depth=1,   rid="r_002"),
    ]
    assert aggregate(reviews)["ai_visibility_pct"] == 100.0


# ---------------------------------------------------------------------------
# Dimension coverage
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_dimension_coverage_all_zeros(make_scored_review) -> None:
    reviews = [make_scored_review("low_retrievability", "high", rid=f"r_{i:03d}") for i in range(1, 4)]
    cov = aggregate(reviews)["dimension_coverage_pct"]
    for dim in DIMENSIONS:
        assert cov[dim] == 0.0, f"expected 0.0 for {dim}, got {cov[dim]}"


@pytest.mark.fast
def test_dimension_coverage_partial(make_scored_review) -> None:
    # 2 reviews with service=1, 1 without → coverage = 2/3 * 100 ≈ 66.7
    reviews = [
        make_scored_review("trust_quality_matchable", "high", service=1, depth=1, rid="r_001"),
        make_scored_review("trust_quality_matchable", "high", service=1, depth=1, rid="r_002"),
        make_scored_review("low_retrievability",      "high",                     rid="r_003"),
    ]
    cov = aggregate(reviews)["dimension_coverage_pct"]
    assert cov["service"] == round(2 / 3 * 100, 1)
    assert cov["descriptive_depth"] == round(2 / 3 * 100, 1)
    assert cov["attributes"] == 0.0


@pytest.mark.fast
def test_dimension_coverage_full(make_scored_review) -> None:
    reviews = [
        make_scored_review(
            "service_attribute_matchable", "high",
            service=2, attributes=2, outcome=1, occasion=1, depth=2,
            rid=f"r_{i:03d}",
        )
        for i in range(1, 4)
    ]
    cov = aggregate(reviews)["dimension_coverage_pct"]
    for dim in DIMENSIONS:
        assert cov[dim] == 100.0, f"expected 100.0 for {dim}, got {cov[dim]}"


# ---------------------------------------------------------------------------
# Weakest dimension
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_weakest_dimension_clear_winner(make_scored_review) -> None:
    # outcome=0 on every review; all others ≥1 → outcome is unambiguously weakest
    reviews = [
        make_scored_review(
            "service_attribute_matchable", "high",
            service=2, attributes=2, outcome=0, occasion=1, depth=1,
            rid=f"r_{i:03d}",
        )
        for i in range(1, 4)
    ]
    assert aggregate(reviews)["weakest_dimension"] == "outcome"


@pytest.mark.fast
def test_weakest_dimension_tiebreaker_uses_spec_order(make_scored_review) -> None:
    # service=0, attributes=0 on all; occasion=1, depth=1 → tie between service and attributes
    # tiebreaker: service comes first in SPEC rubric order → service wins
    reviews = [
        make_scored_review(
            "trust_quality_matchable", "high",
            service=0, attributes=0, outcome=1, occasion=1, depth=1,
            rid=f"r_{i:03d}",
        )
        for i in range(1, 3)
    ]
    assert aggregate(reviews)["weakest_dimension"] == "service"


@pytest.mark.fast
def test_weakest_dimension_is_valid_dimension(make_scored_review) -> None:
    reviews = [
        make_scored_review("service_attribute_matchable", "high", service=2, depth=1, rid="r_001"),
        make_scored_review("low_retrievability",          "low",                      rid="r_002"),
    ]
    result = aggregate(reviews)["weakest_dimension"]
    assert result in DIMENSIONS


# ---------------------------------------------------------------------------
# Confidence distribution
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_confidence_distribution(make_scored_review) -> None:
    reviews = [
        make_scored_review("service_attribute_matchable", "high",   service=2, rid="r_001"),
        make_scored_review("trust_quality_matchable",     "high",   depth=1,   rid="r_002"),
        make_scored_review("trust_quality_matchable",     "medium", depth=1,   rid="r_003"),
        make_scored_review("low_retrievability",          "low",               rid="r_004"),
        make_scored_review("low_retrievability",          "low",               rid="r_005"),
    ]
    dist = aggregate(reviews)["confidence_distribution"]
    assert dist["high"] == 2
    assert dist["medium"] == 1
    assert dist["low"] == 2


@pytest.mark.fast
def test_confidence_distribution_all_zeros_when_no_matching(make_scored_review) -> None:
    # Buckets with 0 reviews still appear in the distribution as 0
    reviews = [make_scored_review("service_attribute_matchable", "high", service=2, rid="r_001")]
    dist = aggregate(reviews)["confidence_distribution"]
    assert dist["medium"] == 0
    assert dist["low"] == 0


# ---------------------------------------------------------------------------
# by_bucket zero counts are explicit
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_empty_buckets_are_zero_not_absent(make_scored_review) -> None:
    reviews = [make_scored_review("service_attribute_matchable", "high", service=2, rid="r_001")]
    stats = aggregate(reviews)
    assert "trust_quality_matchable" in stats["by_bucket"]
    assert "low_retrievability" in stats["by_bucket"]
    assert stats["by_bucket"]["trust_quality_matchable"] == 0
    assert stats["by_bucket"]["low_retrievability"] == 0
