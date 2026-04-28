"""Dev-split labeler evaluation against the gold set.

Runs the actual scorer against every review in the dev split of
tests/fixtures/review_retrievability_gold_v3.json, then asserts that
bucket agreement meets the floor threshold.

Run with:
    pytest -m slow

Skipped by default (no API key, or no -m slow flag).
Saves predictions to outputs/labels_dev.json for offline analysis:
    python tests/evaluate.py --gold tests/fixtures/review_retrievability_gold_v3.json \
                             --predictions outputs/labels_dev.json --split dev
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent
_FIXTURES = Path(__file__).parent / "fixtures"
_GOLD_FILE = _FIXTURES / "review_retrievability_gold_v3.json"
_OUTPUTS = _ROOT / "outputs"
_PREDICTIONS_FILE = _OUTPUTS / "labels_dev.json"

# Floor threshold — established from the first run (2026-04-27 session 2.4).
# Observed: 79.6% (78/98). Floor set 5 pp below to absorb LLM variance.
# Raise this as prompt quality improves; never lower it.
_BUCKET_AGREEMENT_FLOOR = 0.75

# Hand-crafted profile covering the gold set's bakery / café / dessert vertical.
_BAKERY_PROFILE = {
    "business_type": "bakery / café / dessert",
    "inferred_services": [
        "croissants", "macarons", "coffee", "cakes", "pastries",
        "ice cream", "donuts", "tarts", "cookies", "lattes",
    ],
    "inferred_attributes": [
        "cozy atmosphere", "French-inspired", "popular on weekends",
        "artisan", "handmade", "locally sourced", "gluten-free options",
    ],
    "inferred_customer_contexts": [
        "morning coffee", "date night", "birthday celebration",
        "tourist visit", "after-dinner dessert", "late-night snack",
    ],
    "confidence": "medium",
    "notes": "Hand-crafted profile for dev-split evaluation.",
}


def _require_api_key() -> None:
    """Skip the test if ANTHROPIC_API_KEY is not set in the environment."""
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env", override=False)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set — skipping LLM evaluation test.")


@pytest.mark.slow
def test_labeler_dev_split_bucket_agreement():
    """Score all dev-split gold reviews and assert bucket agreement >= floor.

    Saves scored predictions to outputs/labels_dev.json so the full
    evaluate.py report can be reproduced offline.
    """
    _require_api_key()

    from review_tool.scorer import score_review
    from tests.evaluate import evaluate

    # Load gold set and filter to dev split.
    gold = json.loads(_GOLD_FILE.read_text(encoding="utf-8"))
    dev_reviews = [r for r in gold["reviews"] if r.get("split") == "dev"]
    assert len(dev_reviews) > 0, "No dev-split reviews found in gold set."

    print(f"\nScoring {len(dev_reviews)} dev-split reviews...", file=sys.stderr)

    predictions: list[dict] = []
    for i, r in enumerate(dev_reviews, start=1):
        review = {
            "review_id": r["review_id"],
            "text": r["text"],
            "rating": r.get("rating"),
            "date": None,
        }
        scored = score_review(review, _BAKERY_PROFILE)
        predictions.append({
            "review_id": scored["review_id"],
            "labels": scored["labels"],
            "relevance": scored["relevance"],
            "confidence": scored["confidence"],
        })
        if i % 10 == 0:
            print(f"  scored {i}/{len(dev_reviews)}", file=sys.stderr)

    # Persist predictions so evaluate.py can be re-run independently.
    _OUTPUTS.mkdir(parents=True, exist_ok=True)
    _PREDICTIONS_FILE.write_text(
        json.dumps(predictions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nPredictions saved to {_PREDICTIONS_FILE}", file=sys.stderr)

    # Evaluate and assert floor.
    result = evaluate(gold, predictions, split_filter="dev")
    assert result is not None, "evaluate() returned None — check for gold/prediction overlap errors."

    bucket_agreement = result["bucket_agreement"]
    assert bucket_agreement >= _BUCKET_AGREEMENT_FLOOR, (
        f"Bucket agreement {bucket_agreement:.1%} is below floor {_BUCKET_AGREEMENT_FLOOR:.1%}. "
        f"Run: python tests/evaluate.py --gold tests/fixtures/review_retrievability_gold_v3.json "
        f"--predictions outputs/labels_dev.json --split dev"
    )
