"""Shared pytest fixtures for the review-tool test suite."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def make_scored_review():
    """Factory for minimal ScoredReview dicts used in aggregate tests."""
    _EMPTY_RATIONALE = {d: "" for d in ("service", "attributes", "outcome", "occasion", "descriptive_depth")}

    def _make(
        bucket: str,
        confidence: str,
        *,
        service: int = 0,
        attributes: int = 0,
        outcome: int = 0,
        occasion: int = 0,
        depth: int = 0,
        rid: str = "r_001",
    ) -> dict[str, Any]:
        return {
            "review_id": rid,
            "text": "placeholder text for testing",
            "labels": {
                "service": service,
                "attributes": attributes,
                "outcome": outcome,
                "occasion": occasion,
                "descriptive_depth": depth,
            },
            "relevance": True,
            "confidence": confidence,
            "bucket": bucket,
            "rationale": _EMPTY_RATIONALE.copy(),
        }

    return _make
