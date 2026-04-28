"""Stage 3: Per-review scoring via the labeler LLM.

Loads the labeling prompt from prompts/review_scorer.md (system block + few-shot
examples), calls Haiku once per review at temperature=0, and applies the
deterministic bucket rule from classify.bucket_from_labels() to assign each
review to a retrievability bucket.

The labeler returns ONLY dimension scores, relevance, confidence, and rationale.
The bucket is computed downstream — never decided by the LLM.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Callable

from review_tool import llm_client
from review_tool.aggregate import DimensionScores, Rationale, ScoredReview
from review_tool.classify import DIMENSIONS, bucket_from_labels
from review_tool.ingest import Review
from review_tool.llm_client import LLMValidationError

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_SCHEMAS_DIR = Path(__file__).parent / "schemas"

_MAX_REVIEW_WORDS = 1500

# First fenced block under the "## System prompt" heading.
_SYSTEM_FENCE_RE = re.compile(
    r"##\s*System prompt\s*\n+```[a-z]*\n(.*?)\n```",
    re.DOTALL,
)
# Everything between the "## Few-shot examples" heading and the next "## " heading.
_FEW_SHOT_RE = re.compile(
    r"##\s*Few-shot examples\s*\n(.*?)(?=\n##\s|\Z)",
    re.DOTALL,
)
# Standalone triple-backtick lines (the prompt file has one stray closing fence).
_STRAY_FENCE_RE = re.compile(r"(?m)^\s*```\s*$\n?")


# ---------------------------------------------------------------------------
# Prompt and schema loading (cached after first read)
# ---------------------------------------------------------------------------

_system_prompt_cache: str | None = None
_schema_cache: dict | None = None


def _load_system_prompt() -> str:
    """Return the concatenated system prompt: locked rubric block + few-shot examples."""
    text = (_PROMPTS_DIR / "review_scorer.md").read_text(encoding="utf-8")

    sys_match = _SYSTEM_FENCE_RE.search(text)
    if sys_match is None:
        raise RuntimeError(
            "review_scorer.md is missing the '## System prompt' fenced code block."
        )
    examples_match = _FEW_SHOT_RE.search(text)
    if examples_match is None:
        raise RuntimeError(
            "review_scorer.md is missing the '## Few-shot examples' section."
        )

    system_block = sys_match.group(1).strip()
    examples_block = _STRAY_FENCE_RE.sub("", examples_match.group(1)).strip()

    return f"{system_block}\n\n## Few-shot examples\n\n{examples_block}"


def _load_schema() -> dict:
    return json.loads(
        (_SCHEMAS_DIR / "review_labeler_output.json").read_text(encoding="utf-8")
    )


def _get_system_prompt() -> str:
    global _system_prompt_cache
    if _system_prompt_cache is None:
        _system_prompt_cache = _load_system_prompt()
    return _system_prompt_cache


def _get_schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = _load_schema()
    return _schema_cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _maybe_truncate(review_id: str, text: str) -> str:
    """Truncate review text that exceeds the token-safe word limit.

    Very long reviews (academic papers, copy-pasted articles) can exceed the
    model's context window when combined with the system prompt and profile JSON.
    Truncating to 1500 words avoids a BadRequestError mid-corpus.
    """
    words = text.split()
    if len(words) > _MAX_REVIEW_WORDS:
        logger.warning(
            "Review %s is %d words — truncating to %d words before scoring.",
            review_id,
            len(words),
            _MAX_REVIEW_WORDS,
        )
        return " ".join(words[:_MAX_REVIEW_WORDS])
    return text


# ---------------------------------------------------------------------------
# User-message construction
# ---------------------------------------------------------------------------

def _build_user_message(review_text: str, business_profile: dict) -> str:
    """Match the user-message template in review_scorer.md."""
    profile_json = json.dumps(business_profile, indent=2, ensure_ascii=False)
    return (
        f"Business profile for context:\n"
        f"{profile_json}\n\n"
        f"Score this review:\n\n"
        f'"{review_text}"'
    )


# ---------------------------------------------------------------------------
# Fallback for permanent labeler failure on a single review
# ---------------------------------------------------------------------------

def _fallback_scored_review(review: Review) -> ScoredReview:
    """Build a degraded ScoredReview when the labeler fails after retries.

    All-zero labels, confidence='low', and rationale entries that record the
    failure. The deterministic bucket rule maps this to 'low_retrievability'.
    """
    zero_labels: DimensionScores = {d: 0 for d in DIMENSIONS}  # type: ignore[typeddict-item]
    fail_msg = "scoring failed — fallback to default labels"
    rationale: Rationale = {d: fail_msg for d in DIMENSIONS}  # type: ignore[typeddict-item]
    return ScoredReview(
        review_id=review["review_id"],
        text=review["text"],
        rating=review.get("rating"),
        date=review.get("date"),
        labels=zero_labels,
        relevance=True,
        confidence="low",
        bucket=bucket_from_labels(dict(zero_labels), relevance=True),
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_review(
    review: Review,
    business_profile: dict,
    model: str = "claude-haiku-4-5-20251001",
) -> ScoredReview:
    """Score a single review and return a ScoredReview with the bucket assigned.

    The labeler returns only dimension scores, relevance, confidence, and rationale.
    The bucket is computed here from the locked rule in classify.bucket_from_labels().
    Off-topic reviews (relevance=False) still get scored; the bucket override is
    handled inside bucket_from_labels.

    Raises:
        LLMValidationError: model output failed schema validation after one retry.
        LLMAuthError: API key missing or invalid.
        RuntimeError: rate limit or timeout exceeded after backoff retries.
    """
    system_prompt = _get_system_prompt()
    schema = _get_schema()
    safe_text = _maybe_truncate(review["review_id"], review["text"])
    user_message = _build_user_message(safe_text, business_profile)

    output = llm_client.call_with_validation(
        system_prompt=system_prompt,
        user_message=user_message,
        schema=schema,
        model=model,
        temperature=0,
    )

    labels: DimensionScores = output["labels"]
    relevance: bool = output["relevance"]
    bucket = bucket_from_labels(dict(labels), relevance=relevance)

    return ScoredReview(
        review_id=review["review_id"],
        text=review["text"],
        rating=review.get("rating"),
        date=review.get("date"),
        labels=labels,
        relevance=relevance,
        confidence=output["confidence"],
        bucket=bucket,
        rationale=output["rationale"],
    )


def score_corpus(
    reviews: list[Review],
    business_profile: dict,
    model: str = "claude-haiku-4-5-20251001",
    progress_callback: Callable[[int, int, ScoredReview], None] | None = None,
) -> list[ScoredReview]:
    """Score every review in the corpus, recovering from per-review labeler failures.

    On LLMValidationError for one review (after the wrapper's automatic retry),
    logs the failure and substitutes the fallback all-zero ScoredReview, then
    continues with the rest of the corpus. Auth errors and infrastructure
    failures (RuntimeError from rate-limit / timeout exhaustion) are NOT caught —
    they abort the run because they can't be recovered from per-review.

    progress_callback, if provided, is invoked as `(index, total, scored_review)`
    after each review. `index` is 1-based.
    """
    total = len(reviews)
    logger.info("Scoring %d review(s) with model=%s.", total, model)

    out: list[ScoredReview] = []
    failures = 0
    for i, review in enumerate(reviews, start=1):
        try:
            sr = score_review(review, business_profile, model=model)
        except LLMValidationError as exc:
            failures += 1
            logger.error(
                "Review %s (%d/%d): labeler failed after retry — using fallback. %s",
                review["review_id"],
                i,
                total,
                exc,
            )
            sr = _fallback_scored_review(review)

        out.append(sr)
        if progress_callback is not None:
            progress_callback(i, total, sr)

    if failures:
        logger.warning(
            "Labeler fell back to default for %d/%d review(s).", failures, total
        )
    return out
