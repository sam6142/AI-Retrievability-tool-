"""Tests for review_tool.classify — the locked bucket rule.

Exhaustive parametrized coverage (243 score combos × 2 relevance = 486 cases)
plus named tests for the specific cases called out in SPEC.md §7.
"""

from __future__ import annotations

import itertools

import pytest

from review_tool.classify import bucket_from_labels

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expected_bucket(service: int, attributes: int, depth: int, relevance: bool) -> str:
    """Mirror of the locked rule — used to compute expected values in parametrize."""
    if not relevance:
        return "low_retrievability"
    if service >= 2 or attributes >= 2:
        return "service_attribute_matchable"
    if depth >= 1:
        return "trust_quality_matchable"
    return "low_retrievability"


def _labels(service: int, attributes: int, outcome: int, occasion: int, depth: int) -> dict[str, int]:
    return {
        "service": service,
        "attributes": attributes,
        "outcome": outcome,
        "occasion": occasion,
        "descriptive_depth": depth,
    }


# ---------------------------------------------------------------------------
# Exhaustive parametrized test — all 243 score combos × 2 relevance = 486 cases
# ---------------------------------------------------------------------------

_ALL_COMBOS = [
    (s, a, o, oc, d, rel)
    for s, a, o, oc, d in itertools.product(range(3), repeat=5)
    for rel in (True, False)
]


@pytest.mark.fast
@pytest.mark.parametrize("service,attributes,outcome,occasion,depth,relevance", _ALL_COMBOS)
def test_bucket_exhaustive(
    service: int,
    attributes: int,
    outcome: int,
    occasion: int,
    depth: int,
    relevance: bool,
) -> None:
    result = bucket_from_labels(_labels(service, attributes, outcome, occasion, depth), relevance=relevance)
    expected = _expected_bucket(service, attributes, depth, relevance)
    assert result == expected, (
        f"service={service} attributes={attributes} outcome={outcome} "
        f"occasion={occasion} depth={depth} relevance={relevance} "
        f"→ got {result!r}, expected {expected!r}"
    )


# ---------------------------------------------------------------------------
# Named tests for specific cases from SPEC.md §7
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_service_2_alone_is_bucket1() -> None:
    assert bucket_from_labels(_labels(2, 0, 0, 0, 0)) == "service_attribute_matchable"


@pytest.mark.fast
def test_attributes_2_alone_is_bucket1() -> None:
    assert bucket_from_labels(_labels(0, 2, 0, 0, 0)) == "service_attribute_matchable"


@pytest.mark.fast
def test_both_service2_attributes2_is_bucket1() -> None:
    assert bucket_from_labels(_labels(2, 2, 2, 2, 2)) == "service_attribute_matchable"


@pytest.mark.fast
def test_service_1_alone_is_not_bucket1() -> None:
    result = bucket_from_labels(_labels(1, 0, 0, 0, 0))
    assert result != "service_attribute_matchable"


@pytest.mark.fast
def test_service_1_with_depth1_is_bucket2() -> None:
    assert bucket_from_labels(_labels(1, 0, 0, 0, 1)) == "trust_quality_matchable"


@pytest.mark.fast
def test_service_1_no_depth_is_bucket3() -> None:
    assert bucket_from_labels(_labels(1, 0, 0, 0, 0)) == "low_retrievability"


@pytest.mark.fast
def test_depth1_no_service_no_attributes_is_bucket2() -> None:
    assert bucket_from_labels(_labels(0, 0, 2, 2, 1)) == "trust_quality_matchable"


@pytest.mark.fast
def test_all_zeros_is_bucket3() -> None:
    assert bucket_from_labels(_labels(0, 0, 0, 0, 0)) == "low_retrievability"


@pytest.mark.fast
def test_outcome_and_occasion_irrelevant_to_bucket_rule() -> None:
    # outcome and occasion do not appear in the bucket rule; high scores alone don't promote
    assert bucket_from_labels(_labels(0, 0, 2, 2, 0)) == "low_retrievability"


@pytest.mark.fast
def test_relevance_false_overrides_high_scores() -> None:
    assert (
        bucket_from_labels(_labels(2, 2, 2, 2, 2), relevance=False)
        == "low_retrievability"
    )


@pytest.mark.fast
def test_relevance_false_all_zeros() -> None:
    assert bucket_from_labels(_labels(0, 0, 0, 0, 0), relevance=False) == "low_retrievability"


@pytest.mark.fast
def test_relevance_defaults_to_true() -> None:
    # calling without relevance kwarg should behave as relevance=True
    assert bucket_from_labels(_labels(2, 0, 0, 0, 0)) == "service_attribute_matchable"


@pytest.mark.fast
def test_depth2_no_service_no_attributes_is_bucket2() -> None:
    assert bucket_from_labels(_labels(0, 0, 0, 0, 2)) == "trust_quality_matchable"


@pytest.mark.fast
def test_bucket_values_are_canonical_strings() -> None:
    b1 = bucket_from_labels(_labels(2, 0, 0, 0, 0))
    b2 = bucket_from_labels(_labels(0, 0, 0, 0, 1))
    b3 = bucket_from_labels(_labels(0, 0, 0, 0, 0))
    assert b1 == "service_attribute_matchable"
    assert b2 == "trust_quality_matchable"
    assert b3 == "low_retrievability"
